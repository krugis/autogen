#!/bin/bash
# scenario_finalize.sh
# Extracts the FINAL ANSWER from the console log, normalizes it,
# and compares against expected_answer.txt to emit the pass/fail marker.

CONSOLE_LOG="console_log.txt"
EXPECTED_FILE="expected_answer.txt"

if [ ! -f "$CONSOLE_LOG" ] || [ ! -f "$EXPECTED_FILE" ]; then
    echo "MISSING FILES !#!# (console_log or expected_answer not found)"
    exit 0
fi

# Extract the last FINAL ANSWER line (in case the model emits multiple)
FINAL_ANSWER=$(grep "FINAL ANSWER:" "$CONSOLE_LOG" | tail -1 | sed 's/.*FINAL ANSWER:[[:space:]]*//' | tr -d '\r' | xargs)
EXPECTED=$(cat "$EXPECTED_FILE" | tr -d '\r' | xargs)

if [ -z "$FINAL_ANSWER" ]; then
    echo "NO FINAL ANSWER FOUND !#!#"
    exit 0
fi

# Normalize: lowercase, strip punctuation for loose comparison
NORM_GIVEN=$(echo "$FINAL_ANSWER" | tr '[:upper:]' '[:lower:]' | sed 's/[[:punct:]]//g' | tr -s ' ' | xargs)
NORM_EXPECTED=$(echo "$EXPECTED" | tr '[:upper:]' '[:lower:]' | sed 's/[[:punct:]]//g' | tr -s ' ' | xargs)

echo "FINAL_ANSWER_EXTRACTED: $FINAL_ANSWER !#!#"
echo "EXPECTED_ANSWER: $EXPECTED !#!#"

if [ "$NORM_GIVEN" = "$NORM_EXPECTED" ]; then
    echo ALL TESTS PASSED !#!#
else
    echo TESTS FAILED !#!#
    echo "  Given   : $FINAL_ANSWER"
    echo "  Expected: $EXPECTED"
fi
