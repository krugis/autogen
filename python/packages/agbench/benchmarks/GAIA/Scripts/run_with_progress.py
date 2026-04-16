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


@dataclass
class RunSnapshot:
    completed_instances: int
    completed_tasks: int
    running_instances: int
    total_tokens: int
    success_markers: int


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


def snapshot_results(results_root: Path, repeat: int) -> RunSnapshot:
    completed_instances = 0
    running_instances = 0
    total_tokens = 0
    success_markers = 0
    completed_by_task: dict[str, int] = defaultdict(int)

    for instance_dir in find_instance_dirs(results_root):
        task_id = instance_dir.parent.name
        console_file = instance_dir / "console_log.txt"
        if not console_file.exists():
            running_instances += 1
            continue

        try:
            text = console_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            running_instances += 1
            continue

        if COMPLETED_MARKER in text:
            completed_instances += 1
            completed_by_task[task_id] += 1
            total_tokens += read_total_tokens(instance_dir)
            if "ALL TESTS PASSED !#!#" in text:
                success_markers += 1
        else:
            running_instances += 1

    completed_tasks = sum(1 for n in completed_by_task.values() if n >= max(1, repeat))

    return RunSnapshot(
        completed_instances=completed_instances,
        completed_tasks=completed_tasks,
        running_instances=running_instances,
        total_tokens=total_tokens,
        success_markers=success_markers,
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
    if args.subsample is not None:
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

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def pump_stdout() -> None:
        if proc.stdout is None:
            return
        for line in proc.stdout:
            output_lines.append(line.rstrip("\n"))

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

    with Live(refresh_per_second=max(1, int(1.0 / max(0.2, args.refresh_seconds))), console=console, transient=False) as live:
        while True:
            snap = snapshot_results(results_root, int(args.repeat))
            elapsed = time.time() - start_time

            completed_tasks = min(snap.completed_tasks, expected_task_total)
            progress.update(task_id, completed=completed_tasks)

            task_throughput = (completed_tasks / elapsed) * 3600.0 if elapsed > 0 else 0.0
            instance_throughput = (snap.completed_instances / elapsed) * 3600.0 if elapsed > 0 else 0.0
            avg_tokens_per_instance = (
                snap.total_tokens / snap.completed_instances if snap.completed_instances > 0 else 0.0
            )
            avg_tokens_per_task = (snap.total_tokens / completed_tasks) if completed_tasks > 0 else 0.0
            eta = (
                ((expected_task_total - completed_tasks) / (completed_tasks / elapsed))
                if completed_tasks > 0 and expected_task_total > completed_tasks
                else None
            )

            stats = Table.grid(expand=True)
            stats.add_column(justify="left")
            stats.add_column(justify="right")
            stats.add_row("Scenario", scenario_stem)
            stats.add_row("Expected Tasks", str(expected_task_total))
            stats.add_row("Expected Instances", str(expected_instance_total))
            stats.add_row("Completed Tasks", str(completed_tasks))
            stats.add_row("Completed Instances", str(snap.completed_instances))
            stats.add_row("Running Instances", str(snap.running_instances))
            stats.add_row("Success Markers", str(snap.success_markers))
            stats.add_row("Elapsed", format_seconds(elapsed))
            stats.add_row("ETA", format_seconds(eta))
            stats.add_row("Task Throughput", f"{task_throughput:.2f} tasks/hour")
            stats.add_row("Instance Throughput", f"{instance_throughput:.2f} instances/hour")
            stats.add_row("Total Tokens", f"{snap.total_tokens:,}")
            stats.add_row("Avg Tokens/Completed Task", f"{avg_tokens_per_task:,.1f}")
            stats.add_row("Avg Tokens/Completed Instance", f"{avg_tokens_per_instance:,.1f}")

            logs = "\n".join(output_lines) if output_lines else "(waiting for output...)"
            layout = Table.grid(expand=True)
            layout.add_row(Panel(progress, title="Progress", border_style="cyan"))
            layout.add_row(Panel(stats, title="Run Stats", border_style="green"))
            layout.add_row(Panel(logs, title="Live Log Tail", border_style="magenta"))
            live.update(layout)

            if proc.poll() is not None:
                # Final refresh after process exits.
                snap = snapshot_results(results_root, int(args.repeat))
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

            time.sleep(max(0.2, args.refresh_seconds))

    reader.join(timeout=1.0)
    return int(proc.returncode or 0)


if __name__ == "__main__":
    raise SystemExit(main())
