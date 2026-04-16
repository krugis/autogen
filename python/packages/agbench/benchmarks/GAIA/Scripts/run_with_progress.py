#!/usr/bin/env python3
"""Run agbench with a live Rich progress console.

Features:
- Progress bar with ETA
- Completed / total task instances
- Throughput (tasks/hour)
- Total tokens consumed (from metrics.json)
- Rolling log tail from agbench output

This script is intentionally benchmark-local and targets GAIA task files.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from collections import defaultdict
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    from rich.table import Table
except ImportError:
    print("Rich is required. Install with: /home/atemin/autogen/.venv/bin/pip install rich", file=sys.stderr)
    sys.exit(1)

COMPLETED_MARKER = "SCENARIO.PY COMPLETE !#!#"
RUNNING_SCENARIO_RE = re.compile(r"Running scenario .*?/([0-9a-f\-]{36})/(\d+)")


@dataclass
class RunSnapshot:
    completed_instances: int
    completed_tasks: int
    running_instances: int
    total_tokens: int
    success_markers: int
    discovered_instances: int
    running_details: list[tuple[str, float, int]]
    completed_keys: set[str]
    all_keys: set[str]


def count_jsonl_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def find_instance_dirs(results_root: Path) -> Iterable[Path]:
    if not results_root.exists():
        return []

    dirs: list[Path] = []
    for task_id_dir in results_root.iterdir():
        if not task_id_dir.is_dir():
            continue
        for trial_dir in task_id_dir.iterdir():
            if trial_dir.is_dir() and trial_dir.name.isdigit():
                dirs.append(trial_dir)
    return dirs


def read_total_tokens(instance_dir: Path) -> int:
    metrics_file = instance_dir / "metrics.json"
    if metrics_file.exists():
        try:
            with metrics_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            value = data.get("total_tokens")
            return int(value) if value is not None else 0
        except Exception:
            return 0

    # Fallback to console log regex if metrics.json does not exist.
    console_file = instance_dir / "console_log.txt"
    if not console_file.exists():
        return 0

    try:
        text = console_file.read_text(encoding="utf-8", errors="ignore")
        m_prompt = re.search(r"PROMPT_TOKENS:\s*(\d+)\s*!#!#", text)
        m_completion = re.search(r"COMPLETION_TOKENS:\s*(\d+)\s*!#!#", text)
        if m_prompt and m_completion:
            return int(m_prompt.group(1)) + int(m_completion.group(1))
    except Exception:
        pass

    return 0


def snapshot_results(
    results_root: Path,
    repeat: int,
    run_start_time: float = 0.0,
    stream_tokens: int = 0,
) -> RunSnapshot:
    completed_instances = 0
    running_instances = 0
    total_tokens = 0
    success_markers = 0
    completed_by_task: dict[str, int] = defaultdict(int)
    running_details: list[tuple[str, float, int]] = []
    completed_keys: set[str] = set()
    all_keys: set[str] = set()
    has_metrics_tokens = False

    for instance_dir in find_instance_dirs(results_root):
        task_id = instance_dir.parent.name
        instance_key = f"{task_id}/{instance_dir.name}"
        console_file = instance_dir / "console_log.txt"

        if not console_file.exists():
            all_keys.add(instance_key)
            running_instances += 1
            running_details.append((instance_key, time.time(), 0))
            continue

        stat = console_file.stat()
        mtime = stat.st_mtime
        size = int(stat.st_size)

        # Skip leftover instance dirs from a previous run.
        if run_start_time > 0 and mtime < run_start_time - 60:
            continue

        try:
            text = console_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            all_keys.add(instance_key)
            running_instances += 1
            running_details.append((instance_key, time.time(), 0))
            continue

        all_keys.add(instance_key)

        if COMPLETED_MARKER in text:
            completed_instances += 1
            completed_by_task[task_id] += 1
            tok = read_total_tokens(instance_dir)
            total_tokens += tok
            if tok > 0:
                has_metrics_tokens = True
            completed_keys.add(instance_key)
            if "ALL TESTS PASSED !#!#" in text:
                success_markers += 1
        else:
            running_instances += 1
            running_details.append((instance_key, mtime, size))

    completed_tasks = sum(1 for n in completed_by_task.values() if n >= max(1, repeat))

    # Use stream token accumulation for running instances when metrics.json not yet available.
    if not has_metrics_tokens and stream_tokens > 0:
        total_tokens = stream_tokens

    return RunSnapshot(
        completed_instances=completed_instances,
        completed_tasks=completed_tasks,
        running_instances=running_instances,
        total_tokens=total_tokens,
        success_markers=success_markers,
        discovered_instances=len(all_keys),
        running_details=running_details,
        completed_keys=completed_keys,
        all_keys=all_keys,
    )


def format_seconds(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds):
        return "--"
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_agbench_command(args: argparse.Namespace) -> list[str]:
    cmd = [args.agbench_bin, "run", str(args.scenario)]

    if args.repeat is not None:
        cmd += ["-r", str(args.repeat)]
    # Only pass -s if explicitly non-default (agbench forbids -s and -p together).
    if args.subsample is not None and str(args.subsample) not in ("1.0", "1"):
        cmd += ["-s", str(args.subsample)]
    if args.parallel is not None:
        cmd += ["-p", str(args.parallel)]
    if args.env is not None:
        cmd += ["-e", str(args.env)]
    if args.config is not None:
        cmd += ["-c", str(args.config)]
    if args.docker_image is not None:
        cmd += ["-d", str(args.docker_image)]
    if args.native:
        cmd += ["--native"]

    return cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run agbench with a Rich progress console")
    parser.add_argument("scenario", type=Path, help="Path to the JSONL scenario file")
    parser.add_argument("--agbench-bin", default="/home/atemin/autogen/.venv/bin/agbench", help="Path to agbench binary")
    parser.add_argument("-r", "--repeat", type=int, default=1, help="Repeat count")
    parser.add_argument("-s", "--subsample", default="1.0", help="Subsample passed to agbench (default 1.0)")
    parser.add_argument("-p", "--parallel", type=int, default=1, help="Parallel workers")
    parser.add_argument("-e", "--env", default=None, help="Env file for agbench run")
    parser.add_argument("-c", "--config", default=None, help="Config file for agbench run")
    parser.add_argument("-d", "--docker-image", default=None, help="Docker image for agbench run")
    parser.add_argument("--native", action="store_true", help="Run natively")
    parser.add_argument("--refresh-seconds", type=float, default=1.0, help="Dashboard refresh interval")
    parser.add_argument("--log-tail-lines", type=int, default=10, help="Number of stdout lines to show")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenario = args.scenario.resolve()

    if not scenario.exists():
        print(f"Scenario file not found: {scenario}", file=sys.stderr)
        return 2

    scenario_stem = scenario.stem
    expected_tasks = count_jsonl_lines(scenario)
    expected_task_total = expected_tasks

    # For integer subsamples, expected_total differs from full file.
    # For decimal subsamples, use nearest integer estimate.
    try:
        if isinstance(args.subsample, str) and args.subsample.isdigit():
            expected_task_total = int(args.subsample)
        else:
            f = float(args.subsample)
            if 0 < f <= 1.0:
                expected_task_total = max(1, int(round(expected_tasks * f)))
    except Exception:
        pass

    expected_instance_total = expected_task_total * int(args.repeat)

    results_root = Path.cwd() / "Results" / scenario_stem

    cmd = build_agbench_command(args)
    console = Console()
    output_lines: deque[str] = deque(maxlen=max(1, args.log_tail_lines))
    output_lock = threading.Lock()

    # Runtime signal tracking
    instance_start_ts: dict[str, float] = {}
    completed_duration_s: list[float] = []
    lines_seen = 0
    lines_seen_last = 0
    last_line_ts = time.time()
    last_progress_event = "runner started"
    last_progress_event_ts = time.time()
    # Accumulate tokens from stdout stream before metrics.json is written.
    _stream_prompt_tokens: list[int] = [0]
    _stream_completion_tokens: list[int] = [0]
    _stream_tokens_lock = threading.Lock()
    _STREAM_PROMPT_RE = re.compile(r"PROMPT_TOKENS:\s*(\d+)\s*!#!#")
    _STREAM_COMPLETION_RE = re.compile(r"COMPLETION_TOKENS:\s*(\d+)\s*!#!#")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def pump_stdout() -> None:
        nonlocal lines_seen, last_line_ts, last_progress_event, last_progress_event_ts
        if proc.stdout is None:
            return
        for line in proc.stdout:
            raw = line.rstrip("\n")
            now = time.time()
            with output_lock:
                output_lines.append(raw)
                lines_seen += 1
                last_line_ts = now

            m = RUNNING_SCENARIO_RE.search(raw)
            if m:
                key = f"{m.group(1)}/{m.group(2)}"
                instance_start_ts.setdefault(key, now)
                last_progress_event = f"started {key}"
                last_progress_event_ts = now

            mp = _STREAM_PROMPT_RE.search(raw)
            if mp:
                with _stream_tokens_lock:
                    _stream_prompt_tokens[0] += int(mp.group(1))

            mc = _STREAM_COMPLETION_RE.search(raw)
            if mc:
                with _stream_tokens_lock:
                    _stream_completion_tokens[0] += int(mc.group(1))

    reader = threading.Thread(target=pump_stdout, daemon=True)
    reader.start()

    start_time = time.time()

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        TextColumn("[bold]{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        expand=True,
    )
    task_id = progress.add_task("GAIA Eval (Tasks)", total=max(1, expected_task_total), completed=0)

    refresh = max(0.2, args.refresh_seconds)

    with Live(refresh_per_second=max(1, int(1.0 / refresh)), console=console, transient=False) as live:
        try:
            while True:
                with _stream_tokens_lock:
                    _stok = _stream_prompt_tokens[0] + _stream_completion_tokens[0]
                snap = snapshot_results(results_root, int(args.repeat), run_start_time=start_time, stream_tokens=_stok)
                now = time.time()
                elapsed = now - start_time

                # Backfill instance start times for discovered instances.
                for k in snap.all_keys:
                    instance_start_ts.setdefault(k, now)

                # Harvest durations for instances that completed this tick.
                for k in snap.completed_keys:
                    if k in instance_start_ts:
                        dur = max(0.0, now - instance_start_ts[k])
                        # Avoid re-appending same completion.
                        if not completed_duration_s or abs(completed_duration_s[-1] - dur) > 1e-9:
                            pass
                # Use a set to avoid duplicate duration append across ticks.
                if not hasattr(main, "_completed_seen"):
                    setattr(main, "_completed_seen", set())
                completed_seen: set[str] = getattr(main, "_completed_seen")
                new_completed = snap.completed_keys - completed_seen
                for k in new_completed:
                    started = instance_start_ts.get(k, now)
                    completed_duration_s.append(max(0.0, now - started))
                    last_progress_event = f"completed {k}"
                    last_progress_event_ts = now
                completed_seen.update(new_completed)

                completed_tasks = min(snap.completed_tasks, expected_task_total)
                progress.update(task_id, completed=completed_tasks)

                task_throughput = (completed_tasks / elapsed) * 3600.0 if elapsed > 0 else 0.0
                instance_throughput = (snap.completed_instances / elapsed) * 3600.0 if elapsed > 0 else 0.0
                avg_tokens_per_instance = (
                    snap.total_tokens / snap.completed_instances if snap.completed_instances > 0 else 0.0
                )
                avg_tokens_per_task = (snap.total_tokens / completed_tasks) if completed_tasks > 0 else 0.0

                # More informative ETA:
                # 1) If we have completed instances, use observed instance rate.
                # 2) Otherwise bootstrap from running-instance age.
                remaining_instances = max(0, expected_instance_total - snap.completed_instances)
                eta_instances = None
                if snap.completed_instances > 0 and elapsed > 0:
                    inst_rate = snap.completed_instances / elapsed
                    if inst_rate > 0:
                        eta_instances = remaining_instances / inst_rate
                elif snap.running_instances > 0:
                    ages = []
                    for key, _mtime, _size in snap.running_details:
                        started = instance_start_ts.get(key, start_time)
                        ages.append(max(1.0, now - started))
                    avg_running_age = (sum(ages) / len(ages)) if ages else elapsed
                    # Conservative bootstrap: completion tends to be after current age.
                    bootstrap_instance_duration = max(180.0, avg_running_age * 1.6)
                    eta_instances = (remaining_instances / max(1, snap.running_instances)) * bootstrap_instance_duration

                eta_tasks = (eta_instances / max(1, int(args.repeat))) if eta_instances is not None else None

                with output_lock:
                    logs = "\n".join(output_lines) if output_lines else "(waiting for output...)"
                    line_rate = (lines_seen - lines_seen_last) / refresh
                    lines_seen_last = lines_seen

                # Active instances table.
                active = Table(show_header=True, header_style="bold", expand=True)
                active.add_column("Instance", overflow="fold")
                active.add_column("Elapsed", justify="right")
                active.add_column("Last Log Update", justify="right")
                active.add_column("Log Size", justify="right")
                for key, mtime, size in sorted(snap.running_details, key=lambda x: x[1], reverse=True)[:8]:
                    started = instance_start_ts.get(key, start_time)
                    active.add_row(
                        key,
                        format_seconds(now - started),
                        f"{int(now - mtime)}s ago",
                        f"{size/1024:.1f} KB",
                    )
                if snap.running_instances == 0:
                    active.add_row("(none)", "--", "--", "--")

                stats = Table.grid(expand=True)
                stats.add_column(justify="left")
                stats.add_column(justify="right")
                stats.add_row("Scenario", scenario_stem)
                stats.add_row("Expected Tasks", str(expected_task_total))
                stats.add_row("Expected Instances", str(expected_instance_total))
                stats.add_row("Discovered Instances", str(snap.discovered_instances))
                stats.add_row("Completed Tasks", str(completed_tasks))
                stats.add_row("Completed Instances", str(snap.completed_instances))
                stats.add_row("Running Instances", str(snap.running_instances))
                stats.add_row("Success Markers", str(snap.success_markers))
                stats.add_row("Elapsed", format_seconds(elapsed))
                stats.add_row("ETA (Tasks)", format_seconds(eta_tasks))
                stats.add_row("ETA (Instances)", format_seconds(eta_instances))
                stats.add_row("Task Throughput", f"{task_throughput:.2f} tasks/hour")
                stats.add_row("Instance Throughput", f"{instance_throughput:.2f} instances/hour")
                stats.add_row("Log Line Rate", f"{line_rate:.2f} lines/s")
                stats.add_row("Last Log Line", f"{int(now - last_line_ts)}s ago")
                stats.add_row("Last Progress Event", f"{last_progress_event} ({int(now - last_progress_event_ts)}s ago)")
                stats.add_row("Total Tokens", f"{snap.total_tokens:,}")
                stats.add_row("Avg Tokens/Completed Task", f"{avg_tokens_per_task:,.1f}")
                stats.add_row("Avg Tokens/Completed Instance", f"{avg_tokens_per_instance:,.1f}")

                layout = Table.grid(expand=True)
                layout.add_row(Panel(progress, title="Progress", border_style="cyan"))
                layout.add_row(Panel(stats, title="Run Stats", border_style="green"))
                layout.add_row(Panel(active, title="Active Instances", border_style="yellow"))
                layout.add_row(Panel(logs, title="Live Log Tail", border_style="magenta"))
                live.update(layout)

                if proc.poll() is not None:
                    # Final refresh after process exits.
                    with _stream_tokens_lock:
                        _stok = _stream_prompt_tokens[0] + _stream_completion_tokens[0]
                    snap = snapshot_results(results_root, int(args.repeat), run_start_time=start_time, stream_tokens=_stok)
                    completed_tasks = min(snap.completed_tasks, expected_task_total)
                    progress.update(task_id, completed=completed_tasks)
                    elapsed = time.time() - start_time
                    task_throughput = (completed_tasks / elapsed) * 3600.0 if elapsed > 0 else 0.0
                    avg_tokens_per_task = (snap.total_tokens / completed_tasks) if completed_tasks > 0 else 0.0
                    avg_tokens_per_instance = (
                        snap.total_tokens / snap.completed_instances if snap.completed_instances > 0 else 0.0
                    )

                    final_stats = Table.grid(expand=True)
                    final_stats.add_column(justify="left")
                    final_stats.add_column(justify="right")
                    final_stats.add_row("Exit Code", str(proc.returncode))
                    final_stats.add_row("Completed Tasks", f"{completed_tasks}/{expected_task_total}")
                    final_stats.add_row("Completed Instances", f"{snap.completed_instances}/{expected_instance_total}")
                    final_stats.add_row("Elapsed", format_seconds(elapsed))
                    final_stats.add_row("Task Throughput", f"{task_throughput:.2f} tasks/hour")
                    final_stats.add_row("Total Tokens", f"{snap.total_tokens:,}")
                    final_stats.add_row("Avg Tokens/Completed Task", f"{avg_tokens_per_task:,.1f}")
                    final_stats.add_row("Avg Tokens/Completed Instance", f"{avg_tokens_per_instance:,.1f}")

                    final_layout = Table.grid(expand=True)
                    final_layout.add_row(Panel(progress, title="Progress", border_style="cyan"))
                    final_layout.add_row(Panel(final_stats, title="Final Summary", border_style="green"))
                    final_layout.add_row(Panel("\n".join(output_lines) if output_lines else "(no output)", title="Final Log Tail", border_style="magenta"))
                    live.update(final_layout)
                    break

                time.sleep(refresh)
        except KeyboardInterrupt:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            console.print("\n[bold yellow]Interrupted by user.[/bold yellow]")
            return 130

    reader.join(timeout=1.0)
    return int(proc.returncode or 0)


if __name__ == "__main__":
    raise SystemExit(main())
