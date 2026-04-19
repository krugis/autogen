# Gemma 4 26B-A4B Subset16 Eval — Analysis Report

Run ID: run_004__gemma4_26b_a4b__subset16_2x__20260417_220653  
Date: 2026-04-17  
Model: gemma-4-26B-A4B-APEX-I-Mini.gguf  
Server profile: llama.cpp, ctx-size 98304, q4_0 KV cache, same eval parameters as GLM run_003

## 1. Configuration Parity With GLM Run_003

This run was intentionally executed with the same evaluation setup as run_003 so the model comparison is clean.

| Parameter | Gemma run_004 | GLM run_003 |
|---|---|---|
| Task file | subset16 | subset16 |
| Repeats | 2 | 2 |
| Parallel | 1 | 1 |
| MAGENTIC_MAX_TURNS | 4 | 4 |
| MAGENTIC_MAX_STALLS | 2 | 2 |
| Orchestrator max_tokens | 24576 | 24576 |
| Coder max_tokens | 12288 | 12288 |
| Web/File max_tokens | 8192 | 8192 |
| llama.cpp ctx-size | 98304 | 98304 |
| Sampling | temp 1.0, top_p 0.95, min_p 0.01, repeat_penalty 1.0 | same |

Only the model and model family differ by design.

## 2. Overall Results

| Metric | Gemma run_004 | GLM run_003 |
|---|---|---|
| Instances | 32/32 | 32/32 |
| Passed | 11 | 5 |
| Pass rate | 34.4% | 15.6% |
| Failed | 21 | 27 |
| Prompt tokens | 1,973,628 | n/a in metadata |
| Completion tokens | 202,432 | n/a in metadata |
| Total tokens | 2,176,060 | 3,038,898 |
| Avg tokens/instance | 68,001.9 | 94,966 |
| Total runtime | 3,562s (59.4 min) | 20,063s (5:34h) |
| Avg runtime/instance | 111.3s | 626s |
| Total LLM calls | 625 | 484 |
| Avg LLM calls/instance | 19.5 | 15.1 |
| Avg tokens/LLM call | 3,481.7 | 6,278 |

## 3. Level Breakdown

| Level | Gemma passes | Gemma pass rate | GLM pass rate |
|---|---|---|---|
| L1 | 6/10 | 60.0% | 20.0% |
| L2 | 3/16 | 18.8% | 18.8% |
| L3 | 2/6 | 33.3% | 0.0% |

Gemma is materially better on L1 and L3 under the matched configuration. L2 is flat against GLM.

## 4. Attachment Breakdown

| Attachment | Gemma passes | Gemma pass rate |
|---|---|---|
| No file | 6/22 | 27.3% |
| Has file | 5/10 | 50.0% |

File-backed tasks remain substantially easier than browser-only or search-heavy tasks.

## 5. Passed Tasks

Perfect pass across both repeats:
- 11af4e1a — BERT layers question
- dc28cf18 — potatoes/family reasoning
- e961a717 — Asian monarchies with sea access
- e9a2c537 — Rick Riordan library count
- f918266a — attached Python numeric output

Split result:
- 076c8171 — vendor/rent spreadsheet task: failed repeat 0, passed repeat 1

This yields 5 perfectly repeatable passing tasks and 1 split task.

## 6. Failure Categories

| Category | Count | Share of all instances |
|---|---|---|
| WRONG_ANSWER | 18 | 56.2% |
| PASS | 11 | 34.4% |
| NO_FINAL_ANSWER_LEDGER_PARSE | 2 | 6.2% |
| NO_FINAL_ANSWER_OTHER | 1 | 3.1% |

### 6a. Wrong-answer examples
- 0bdb7c40: expected `White; 5876`, got `Hatcher;768` / CAPTCHA-related failure text
- 2a649bb1: expected `3.1.3.1; 1.11.1.7`, got wrong EC-number pairs in both repeats
- 72e110e7: expected `Guatemala`, got `Japan` / `Cannot be determined`
- ad2b4d70: expected `War is not here this is a land of peace`, got `crescent` / `Moon`
- d8152ad6: expected `0.03`, got `0.02` in both repeats

### 6b. No-final-answer failures
- 0a3cd321 repeat 1: LedgerEntry validation failure, missing `answer` fields
- bfcd99e1 repeat 0: LedgerEntry validation failure, missing `instruction_or_question.answer`
- 8b3379c0 repeat 0: model reasoned through the task but never emitted a final answer marker

The previous GLM run had many no-final-answer failures; Gemma largely avoids that problem.

## 7. Speed and Token Efficiency

Gemma is substantially more efficient than GLM under the same eval controls.

| Metric | Gemma run_004 | GLM run_003 | Improvement |
|---|---|---|---|
| Total runtime | 59.4 min | 5:34h | 5.6x faster |
| Avg runtime/instance | 111s | 626s | 5.6x faster |
| Total tokens | 2.18M | 3.04M | 28.4% fewer |
| Avg tokens/instance | 68.0k | 95.0k | 28.4% fewer |
| Avg tokens/LLM call | 3.48k | 6.28k | 44.5% fewer |

Interpretation:
- Gemma makes slightly more LLM calls, but each call is much shorter.
- The shorter call size keeps context accumulation under control.
- This is the main reason wall-clock runtime dropped from 5.6 hours to under 1 hour.

## 8. Comparison Against Gemma run_001 (24k context)

| Metric | Gemma run_001 | Gemma run_004 |
|---|---|---|
| Context | 24k | 98k |
| Pass rate | 18.8% | 34.4% |
| Total runtime | 2:36h | 0:59h |
| Total tokens | 1,715,026 | 2,176,060 |

The 98k-matched Gemma setup is better than the earlier 24k Gemma run on both quality and speed in this benchmark configuration.

## 9. Main Conclusions

1. Gemma is the better model for this benchmark configuration on this machine.
2. The comparison against GLM is now clean because the runtime parameters were matched.
3. Gemma’s dominant remaining failure mode is answer quality, not formatting or parser compatibility.
4. The orchestrator/ledger pipeline is mostly compatible with Gemma; only 2 parser failures remained.
5. This run is a stronger baseline than both run_001 and run_003 for future tuning work.

## 10. Recommended Next Steps

1. Keep Gemma as the default local benchmark model for GAIA subset16 on this RTX 5080 setup.
2. If you want to push pass rate higher, target wrong-answer tasks with prompt or tool-routing changes rather than parser fixes.
3. If you want a faster smoke/full regression suite, this 98k Gemma profile is already viable.

## 11. Archive Path

Absolute path:
`GAIA/EvalRuns/model_eval_archives/run_004__gemma4_26b_a4b__subset16_2x__20260417_220653`
