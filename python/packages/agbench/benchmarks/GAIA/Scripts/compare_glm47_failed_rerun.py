#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


BASE = Path("/home/atemin/autogen/python/packages/agbench/benchmarks/GAIA")
DEFAULT_BASELINE = BASE / "EvalRuns" / "model_eval_archives" / "run_003__glm47_flash_apex_i_mini__subset16_2x__20260417_201549"

LEDGER_RE = re.compile(
    r"(?:Failed to parse ledger information after multiple retries|"
    r"ValidationError:\s*\d+\s+validation error for LedgerEntry|"
    r"instruction_or_question\.answer)",
    re.I,
)
LENGTH_RE = re.compile(r"LengthFinishReason", re.I)
TOOL_RE = re.compile(r"(?:FileNotFoundError|TimeoutError|tool.*error|error.*tool)", re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare GLM failed-case rerun against run_003 baseline")
    parser.add_argument("--task-file", required=True, help="JSONL file containing the failed-task rerun subset")
    parser.add_argument("--rerun-dir", required=True, help="Results directory from the rerun")
    parser.add_argument("--baseline-dir", default=str(DEFAULT_BASELINE), help="Baseline run_003 archive directory")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if no measurable improvement is observed")
    return parser.parse_args()


def load_task_ids(task_file: Path) -> set[str]:
    task_ids: set[str] = set()
    with task_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            task_ids.add(record["id"])
    return task_ids


def normalize_instances_root(path: Path) -> Path:
    if (path / "instances").exists():
        return path / "instances"
    return path


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def mine_rows(root: Path, allowed_task_ids: set[str]) -> list[dict]:
    instances_root = normalize_instances_root(root)
    rows: list[dict] = []

    if not instances_root.exists():
        raise FileNotFoundError(f"Instance directory not found: {instances_root}")

    for task_dir in sorted(instances_root.iterdir()):
        if not task_dir.is_dir() or task_dir.name not in allowed_task_ids:
            continue

        for repeat_dir in sorted(task_dir.iterdir()):
            if not repeat_dir.is_dir() or not repeat_dir.name.isdigit():
                continue

            metrics = read_json(repeat_dir / "metrics.json")
            console_text = ""
            console_path = repeat_dir / "console_log.txt"
            if console_path.exists():
                console_text = console_path.read_text(encoding="utf-8", errors="replace")

            final_answer_found = bool(metrics.get("final_answer_found", False))
            if not final_answer_found and "FINAL_ANSWER_EXTRACTED:" in console_text:
                extracted = re.search(r"FINAL_ANSWER_EXTRACTED:\s*(.+?)(?:\s*!#!#|$)", console_text)
                if extracted and extracted.group(1).strip() and extracted.group(1).strip() != "NO FINAL ANSWER FOUND":
                    final_answer_found = True

            rows.append(
                {
                    "task": task_dir.name,
                    "repeat": int(repeat_dir.name),
                    "passed": "ALL TESTS PASSED" in console_text,
                    "final_answer_found": final_answer_found,
                    "total_tokens": int(metrics.get("total_tokens", 0) or 0),
                    "llm_call_count": int(metrics.get("llm_call_count", 0) or 0),
                    "ledger_parse_errors": int(bool(LEDGER_RE.search(console_text))),
                    "length_finish_errors": int(bool(LENGTH_RE.search(console_text))),
                    "tool_errors": int(bool(TOOL_RE.search(console_text))),
                }
            )

    return rows


def summarize(rows: list[dict]) -> dict:
    per_task: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        per_task[row["task"]].append(row)

    passed = sum(1 for row in rows if row["passed"])
    no_answer = sum(1 for row in rows if not row["final_answer_found"])
    wrong_answer = sum(1 for row in rows if row["final_answer_found"] and not row["passed"])

    return {
        "instances": len(rows),
        "tasks": len(per_task),
        "passed": passed,
        "pass_rate": round((100.0 * passed / len(rows)), 1) if rows else 0.0,
        "no_answer_count": no_answer,
        "no_answer_rate": round((100.0 * no_answer / len(rows)), 1) if rows else 0.0,
        "wrong_answer_count": wrong_answer,
        "ledger_parse_errors": sum(row["ledger_parse_errors"] for row in rows),
        "ledger_parse_error_rate": round((100.0 * sum(row["ledger_parse_errors"] for row in rows) / len(rows)), 1) if rows else 0.0,
        "length_finish_errors": sum(row["length_finish_errors"] for row in rows),
        "length_finish_error_rate": round((100.0 * sum(row["length_finish_errors"] for row in rows) / len(rows)), 1) if rows else 0.0,
        "tool_errors": sum(row["tool_errors"] for row in rows),
        "total_tokens": sum(row["total_tokens"] for row in rows),
        "total_llm_calls": sum(row["llm_call_count"] for row in rows),
        "per_task": {
            task: {
                "passed": sum(1 for row in task_rows if row["passed"]),
                "instances": len(task_rows),
                "no_answer": sum(1 for row in task_rows if not row["final_answer_found"]),
                "ledger": sum(row["ledger_parse_errors"] for row in task_rows),
                "length": sum(row["length_finish_errors"] for row in task_rows),
            }
            for task, task_rows in sorted(per_task.items())
        },
    }


def print_summary(label: str, summary: dict) -> None:
    print(label)
    print(f"  tasks={summary['tasks']} instances={summary['instances']} passed={summary['passed']} pass_rate={summary['pass_rate']}%")
    print(
        f"  no_answer={summary['no_answer_count']} ({summary['no_answer_rate']}%) "
        f"wrong_answer={summary['wrong_answer_count']}"
    )
    print(
        "  ledger_parse_errors={ledger} ({ledger_rate}%) length_finish_errors={length} ({length_rate}%) tool_errors={tool}".format(
            ledger=summary["ledger_parse_errors"],
            ledger_rate=summary["ledger_parse_error_rate"],
            length=summary["length_finish_errors"],
            length_rate=summary["length_finish_error_rate"],
            tool=summary["tool_errors"],
        )
    )
    print(f"  total_tokens={summary['total_tokens']} total_llm_calls={summary['total_llm_calls']}")


def print_task_deltas(baseline: dict, rerun: dict) -> None:
    print("\nPer-task deltas")
    print("  task       baseline_pass  rerun_pass  baseline_no_answer  rerun_no_answer  baseline_ledger  rerun_ledger  baseline_length  rerun_length")
    for task in sorted(baseline["per_task"]):
        base = baseline["per_task"][task]
        new = rerun["per_task"].get(task, {"passed": 0, "instances": 0, "no_answer": 0, "ledger": 0, "length": 0})
        print(
            f"  {task[:8]:<10} {base['passed']:>13}/{base['instances']:<2} {new['passed']:>10}/{new['instances']:<2}"
            f" {base['no_answer']:>18} {new['no_answer']:>16} {base['ledger']:>16} {new['ledger']:>13} {base['length']:>17} {new['length']:>13}"
        )


def strict_failures(baseline: dict, rerun: dict) -> list[str]:
    failures: list[str] = []
    if rerun["ledger_parse_error_rate"] > baseline["ledger_parse_error_rate"]:
        failures.append("ledger parse error rate increased")
    if rerun["length_finish_error_rate"] > baseline["length_finish_error_rate"]:
        failures.append("length-finish error rate increased")
    if rerun["no_answer_rate"] > baseline["no_answer_rate"]:
        failures.append("no-final-answer rate increased")

    improved = (
        rerun["ledger_parse_error_rate"] < baseline["ledger_parse_error_rate"]
        or rerun["length_finish_error_rate"] < baseline["length_finish_error_rate"]
        or rerun["no_answer_rate"] < baseline["no_answer_rate"]
        or rerun["pass_rate"] > baseline["pass_rate"]
    )
    if not improved:
        failures.append("no measurable improvement detected")

    return failures


def main() -> int:
    args = parse_args()
    task_file = Path(args.task_file)
    rerun_dir = Path(args.rerun_dir)
    baseline_dir = Path(args.baseline_dir)

    allowed_task_ids = load_task_ids(task_file)
    baseline_rows = mine_rows(baseline_dir, allowed_task_ids)
    rerun_rows = mine_rows(rerun_dir, allowed_task_ids)

    baseline = summarize(baseline_rows)
    rerun = summarize(rerun_rows)

    print_summary("Baseline run_003 subset", baseline)
    print_summary("Rerun subset", rerun)

    print("\nDelta")
    print(
        f"  pass_rate: {baseline['pass_rate']}% -> {rerun['pass_rate']}% "
        f"({rerun['pass_rate'] - baseline['pass_rate']:+.1f} pp)"
    )
    print(
        f"  no_answer_rate: {baseline['no_answer_rate']}% -> {rerun['no_answer_rate']}% "
        f"({rerun['no_answer_rate'] - baseline['no_answer_rate']:+.1f} pp)"
    )
    print(
        f"  ledger_parse_error_rate: {baseline['ledger_parse_error_rate']}% -> {rerun['ledger_parse_error_rate']}% "
        f"({rerun['ledger_parse_error_rate'] - baseline['ledger_parse_error_rate']:+.1f} pp)"
    )
    print(
        f"  length_finish_error_rate: {baseline['length_finish_error_rate']}% -> {rerun['length_finish_error_rate']}% "
        f"({rerun['length_finish_error_rate'] - baseline['length_finish_error_rate']:+.1f} pp)"
    )

    print_task_deltas(baseline, rerun)

    if args.strict:
        failures = strict_failures(baseline, rerun)
        if failures:
            print("\nSTRICT CHECK FAILED")
            for failure in failures:
                print(f"  - {failure}")
            return 1
        print("\nSTRICT CHECK PASSED")

    return 0


if __name__ == "__main__":
    sys.exit(main())