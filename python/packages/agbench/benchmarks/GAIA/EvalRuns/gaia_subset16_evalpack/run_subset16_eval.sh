#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/atemin/autogen/python/packages/agbench/benchmarks/GAIA"
TASK_FILE="$ROOT/Tasks/gaia_validation_subset16__MagenticOne.jsonl"
RESULT_NAME="gaia_validation_subset16__MagenticOne"
RESULT_DIR="$ROOT/Results/$RESULT_NAME"
PACK_DIR="$ROOT/EvalRuns/gaia_subset16_evalpack"

cd "$ROOT"
rm -rf "$RESULT_DIR"

MAGENTIC_MAX_TURNS="${MAGENTIC_MAX_TURNS:-6}" \
MAGENTIC_MAX_STALLS="${MAGENTIC_MAX_STALLS:-2}" \
/home/atemin/autogen/.venv/bin/python3 Scripts/run_with_progress.py \
  "$TASK_FILE" \
  -r "${REPEAT:-1}" -p "${PARALLEL:-2}" \
  --refresh-seconds "${REFRESH_SECONDS:-0.5}" \
  --log-tail-lines "${LOG_TAIL_LINES:-8}"

mkdir -p "$PACK_DIR/outputs"
cp -a "$RESULT_DIR" "$PACK_DIR/outputs/"

echo "Run complete."
echo "Results: $RESULT_DIR"
echo "Copied to: $PACK_DIR/outputs/$RESULT_NAME"
