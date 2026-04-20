#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/atemin/autogen/python/packages/agbench/benchmarks/GAIA"
TASK_FILE="$ROOT/Tasks/gaia_validation_failed_from_run003__MagenticOne__glm47_fix1.jsonl"
RESULT_DIR="$ROOT/Results/gaia_validation_failed_from_run003__MagenticOne__glm47_fix1"
CONFIG_FILE="${CONFIG_FILE:-$ROOT/config.glm47_flash_fix1_failed_rerun.yaml}"
RUNNER="/home/atemin/autogen/.venv/bin/python3"
REPEATS="${REPEATS:-1}"
P_VALUE="${P_VALUE:-1}"

cd "$ROOT"

rm -rf "$RESULT_DIR"

echo "Using task file: $TASK_FILE"
echo "Using config: $CONFIG_FILE"
echo "Results dir: $RESULT_DIR"
echo "Running rerun of run_003 failed cases with GLM fix profile"
echo "Tasks=$(wc -l < "$TASK_FILE") Repeats=$REPEATS Parallel=$P_VALUE"

MAGENTIC_MAX_TURNS=4 MAGENTIC_MAX_STALLS=2 \
  "$RUNNER" Scripts/run_with_progress.py "$TASK_FILE" \
  -r "$REPEATS" -p "$P_VALUE" \
  -c "$CONFIG_FILE" \
  --refresh-seconds 0.5 \
  --log-tail-lines 8

"$RUNNER" Scripts/compare_glm47_failed_rerun.py \
  --task-file "$TASK_FILE" \
  --rerun-dir "$RESULT_DIR" \
  --strict