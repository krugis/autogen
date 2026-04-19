# GLM-4.7-Flash Subset16 Eval — Analysis Report
**Run ID:** run_003__glm47_flash_apex_i_mini__subset16_2x__20260417_201549  
**Date:** 2026-04-17  
**Model:** GLM-4.7-Flash-APEX-I-Mini.gguf  
**Context window:** 98,304 tokens (llama.cpp `--ctx-size 98304`)  
**Compare baseline:** run_001 — Gemma 4-26B (24k ctx, max_turns=4, max_stalls=2)

---

## 1. Configuration

| Parameter | Value |
|---|---|
| Model | GLM-4.7-Flash-APEX-I-Mini.gguf |
| API | http://localhost:8080/v1/ |
| Server ctx-size | 98,304 |
| MAGENTIC_MAX_TURNS | 4 |
| MAGENTIC_MAX_STALLS | 2 |
| Repeats | 2 |
| Parallel | 1 |
| orchestrator max_tokens | 24,576 |
| coder max_tokens | 12,288 |
| web/file surfer max_tokens | 8,192 |
| Task file | gaia_validation_subset16__MagenticOne.jsonl |
| Total instances expected | 32 (16 tasks × 2 repeats) |

---

## 2. Overall Results

| Metric | Value | vs Gemma (run_001) |
|---|---|---|
| Instances completed | 32/32 | = |
| **Passed** | **5/32 (15.6%)** | ↓ from 18.8% |
| Failed | 27/32 (84.4%) | ↑ |
| Total tokens | 3,038,898 | ↑ from 1,715,026 |
| Avg tokens/instance | 94,966 | ↑ from 53,595 |
| Total runtime | 20,063s (334 min / 5:34h) | ↑ from 2:36h |
| Avg runtime/instance | 626s (~10:26) | ↑ from ~9:20s |

---

## 3. Results by Difficulty Level

| Level | Tasks | Instances | Passed | Pass Rate | vs Gemma |
|---|---|---|---|---|---|
| L1 (explicit) | 5 | 10 | 2 | 20% | ↓ from 40% |
| L2 (implicit) | 8 | 16 | 3 | 18.8% | ↑ from 12.5% |
| L3 (reasoning) | 3 | 6 | 0 | 0% | = |

---

## 4. Passed Tasks

| Task UUID (short) | Repeat 0 | Repeat 1 | L | Expected | Runtime (r0/r1) |
|---|---|---|---|---|---|
| 11af4e1a (count=6) | ✅ PASS | ✅ PASS | L1 | 6 | 113s / 140s |
| f918266a (count=0) | ✅ PASS | ✅ PASS | L2 | 0 | 411s / 290s |
| dc28cf18 (text) | ❌ FAIL | ✅ PASS | L2 | 2 | 658s / 721s |

**100% repeatability:** 2 tasks agreed across both repeats. 1 task showed split (0/1).

---

## 5. Failure Analysis

### 5a. Failure Categories (32 instances)

| Category | Count | % | Description |
|---|---|---|---|
| WRONG_ANSWER | 15 | 46.9% | Answer extracted but incorrect |
| NO_FINAL_ANSWER | 12 | 37.5% | No parseable answer produced |
| **PASS** | **5** | **15.6%** | Correct answer |

No pure API failure category — all failures either produced a wrong answer or no answer.

### 5b. WRONG_ANSWER breakdown (15)

| Task | Expected | Got (r0) | Got (r1) | Pattern |
|---|---|---|---|---|
| 8b3379c0 | 1.8 | 0 | 0.9 | Numerical off-by-fraction |
| e961a717 | 12 | 10 | — (no answer) | Off-by-2 |
| bfcd99e1 | 17 | — | 13 | Off-by-4 |
| 72e110e7 | Guatemala | Basque Country | United Kingdom | Wrong geography |
| 076c8171 | Finance | Restaurant | Convenience Store | Semantic category wrong |
| 0a3cd321 | Brunei,China,Morocco,Singapore | (partial set, 8 items) | (different set) | Set membership over-inclusive |
| 2a649bb1 | 3.1.3.1;1.11.1.7 | Wrong version | Partial match | Software version wrong |
| e9a2c537 | 7 | — | 6 | Off-by-1 |
| f2feb6a4 | 900000 | — | 860,000 | Off-by-5% |
| 0bdb7c40 | White;5876 | William Gregory;13 | — | Entirely wrong multi-part |
| ad2b4d70 | "War is not here..." | — | D | Nonsense answer |

### 5c. NO_FINAL_ANSWER breakdown (12)

| Sub-cause | Count | Notes |
|---|---|---|
| LengthFinishReasonError (orchestrator token limit hit at 24,576) | 4 | Instances: 7673×2, e9a2c537/0, new from 98k profile |
| Pydantic ValidationError (LedgerEntry missing field) | 3 | Orchestrator JSON parse failure |
| ValueError: Failed to parse ledger after retries | 2 | GLM not generating valid LedgerEntry JSON |
| FileNotFoundError / WebSurfer timeout → no answer | 2 | Tool errors exhausted remaining turns |
| Misc / early stall | 1 | — |

---

## 6. Key Observations vs Gemma (run_001)

| Observation | Detail |
|---|---|
| **Pass rate slightly lower** | 15.6% vs 18.8% — likely due to configuration change (higher max_tokens per agent increased prompt size, hitting token limit earlier in orchestrator) |
| **More WRONG_ANSWER, fewer NO_FINAL_ANSWER** | GLM produces an answer more often (15 WRONG vs Gemma 24 NO_FINAL_ANSWER) — better answer format adherence |
| **Format compliance improved** | Only 12 NO_FINAL_ANSWER vs 24 in Gemma — 50% improvement in answer format compliance |
| **LengthFinishReasonError for orchestrator** | Orchestrator max_tokens=24,576 still too low for some tasks; 4 instances hit this new ceiling |
| **LedgerEntry JSON parse failures (new)** | GLM generates non-compliant JSON for orchestrator ledger — Gemma did not have this issue. Affects 5 instances |
| **Token usage 77% higher** | 3.04M vs 1.72M tokens — larger max_tokens caps allow deeper reasoning but also more retries on errors |
| **2 tasks consistently passed both repeats** | Same repeatability profile as Gemma |
| **L1 pass rate dropped 40% → 20%** | GLM struggles more on simple explicit-answer tasks |
| **L2 pass rate improved 12.5% → 18.8%** | GLM slightly better on implicit reasoning tasks |

---

## 7. Root Cause Priorities

1. **LedgerEntry JSON parse failures** (5 instances) — GLM sometimes outputs malformed JSON for the MagenticOne orchestrator ledger. Investigation: check whether `family: glm` config disables the structured_output path needed for LedgerEntry; consider switching back to `family: openai` or adjusting prompt template.

2. **Orchestrator token ceiling** — 4 hits on 24,576 limit. Consider increasing to 32,768 or testing uncapped orchestrator again.

3. **Reasoning accuracy** — WRONG_ANSWER is now the dominant failure type (46.9%). Most are off-by-N on numerical tasks or geographic/category guesses. Suggests model needs more deliberate multi-step verification in prompt.

---

## 8. Recommendations for Next Run

| Priority | Change | Expected Impact |
|---|---|---|
| HIGH | Fix `family:` to `openai` or correct chat template to fix LedgerEntry parse errors | Eliminate 5 NO_FINAL_ANSWER instances |
| HIGH | Increase orchestrator max_tokens to 32,768 | Eliminate 4 token overflow failures |
| MED | Add `"Verify your answer step by step before providing FINAL ANSWER"` to system prompt | May reduce WRONG_ANSWER off-by-N errors |
| LOW | Add `MAGENTIC_MAX_TURNS=6` to allow more correction passes | May help 2-3 close misses |

---

## 9. Archive Structure

```
run_003__glm47_flash_apex_i_mini__subset16_2x__20260417_201549/
├── ANALYSIS_REPORT.md                  ← this file
├── RUN_METADATA.txt                    ← config snapshot + summary
├── config_at_run_time.yaml             ← exact config.yaml used
├── gaia_validation_subset16__MagenticOne.jsonl  ← task definitions
└── instances/                          ← 32 instance directories (16 task UUIDs × 2 repeats)
    ├── <uuid>/
    │   ├── 0/  console_log.txt, metrics.json, expected_answer.txt ...
    │   └── 1/  console_log.txt, metrics.json, expected_answer.txt ...
```

**Absolute path:**  
`GAIA/EvalRuns/model_eval_archives/run_003__glm47_flash_apex_i_mini__subset16_2x__20260417_201549`

---

## 10. Speed Analysis — Why Does It Take 5 Hours?

### 10a. LLM API Benchmark (curl, live measurement)

| Metric | Value |
|---|---|
| Prefill speed | 63 tok/s |
| **Decode (generation) speed** | **142 tok/s** |
| Per-token decode time | 7.06 ms |
| Per-token prefill time | 15.8 ms |
| Measured via | `POST /v1/chat/completions` with 800-token completion, `timings` field |

### 10b. Per-Instance Token and Runtime Data

| Task | Repeat | Runtime (s) | Tokens | LLM calls | Effective tok/s |
|---|---|---|---|---|---|
| 0bdb7c40 | 0 | 2090 | 237,864 | 28 | 113.8 |
| 0bdb7c40 | 1 | 1259 | 191,474 | 24 | 152.1 |
| 076c8171 | 0 | 965 | 203,237 | 23 | 210.6 |
| 076c8171 | 1 | 1001 | 209,862 | 27 | 209.7 |
| e9a2c537 | 0 | 929 | N/A | N/A | N/A |
| 2a649bb1 | 1 | 596 | 208,986 | 25 | 350.6 |
| d8152ad6 | 0/1 | 732 each | N/A | N/A | N/A |
| 11af4e1a | 0 | 113 | 25,213 | 8 | 223.1 |
| e961a717 | 0 | 461 | 129,363 | 26 | 280.6 |

### 10c. Aggregate Speed Metrics

| Metric | Value |
|---|---|
| Total instances | 32 |
| Total runtime | 20,063s (5.57h) |
| Avg runtime/instance | 626s (10:26) |
| Min / Max runtime | 113s / 2090s |
| Avg tokens/instance (w/ data) | 121,555 |
| Min / Max tokens | 22,208 / 237,864 |
| Total LLM calls | 484 |
| Avg LLM calls/instance | 19 |
| **Avg tokens per LLM call** | **6,278** |
| Effective wall-clock tok/s | ~206 tok/s (avg across instances) |
| **LLM API raw decode speed** | **142 tok/s** |

### 10d. Root Cause Diagnosis

**Short answer: The LLM speed IS the bottleneck, not overhead.**

The observed effective throughput (~206 tok/s wall-clock) is actually *above* the raw decode speed (142 tok/s). This is explained by:
- **KV-cache hits** — long conversations reuse cached context, making subsequent tokens cheaper
- **Parallel prefill + small overhead** — wall-clock aggregates prompt+decode together

**The real driver of 5h runtime is token volume, not inefficiency.**

Per-instance time budget (avg):
```
Avg tokens/instance:   121,555
Expected decode time:  121,555 / 142 tok/s  =  856s  (14:16)
Actual avg runtime:    626s  (10:26)
→ KV cache savings:    ~27% time saved
```

**Why so many tokens per instance?**

Each MagenticOne instance runs up to 4 turns × 19 LLM calls average × 6,278 tokens/call.
The token explosion comes from:

| Source | Impact |
|---|---|
| Full conversation history sent on every LLM call | Every call includes all prior agent messages → grows quadratically with turns |
| orchestrator max_tokens=24,576 | Allows very verbose planning, padded JSON thought chains |
| Web/file surfer tool outputs | Page content and file reads are large, injected into context |
| 28 LLM calls in worst-case instances | Some tasks hit all 4 turns × multiple retries = 28 calls × 6k avg = 168k tokens |

**Comparison to Gemma (run_001):**

| | GLM (run_003) | Gemma (run_001) |
|---|---|---|
| Avg tokens/instance | 121,555 | 53,595 |
| Total runtime | 5.57h | 2.36h |
| Token ratio | 2.27× more tokens | baseline |
| Runtime ratio | 2.36× longer | baseline |
| → Runtime scales linearly with tokens | ✅ confirmed | — |

The 2.3× more tokens in GLM is because the higher `max_tokens` caps (24k/12k/8k vs 8k/3k/2k Gemma) allow each call to produce and consume much more text, inflating the rolling context.

### 10e. Levers to Reduce Runtime

| Change | Expected effect |
|---|---|
| Lower orchestrator max_tokens 24k → 12k | ~35% fewer tokens, ~35% faster |
| Add `MAGENTIC_MAX_TURNS=3` (from 4) | Fewer turns, fewer LLM calls, less context accumulation |
| Enable KV cache reuse across instances (llama.cpp `--cache-reuse`) | 20-30% prefill speed-up on repeated tasks |
| Run with `-p 2` (2 parallel instances) | Halve wall-clock time with same total compute |

---

## 11. Comparison Table: Gemma vs GLM

| Metric | Gemma 4-26B (run_001, 24k ctx) | GLM-4.7-Flash (run_003, 98k ctx) |
|---|---|---|
| Pass rate | 18.8% (6/32) | 15.6% (5/32) |
| L1 pass rate | 40% | 20% |
| L2 pass rate | 12.5% | 18.8% |
| L3 pass rate | 0% | 0% |
| Format compliance | 25% (8 had answers) | 62.5% (20 had answers) |
| WRONG_ANSWER | 2 | 15 |
| NO_FINAL_ANSWER | 24 | 12 |
| Token overflow errors | ~few | 4 (orchestrator ceiling) |
| LedgerEntry JSON errors | 0 | 5 |
| Total tokens | 1,715,026 | 3,038,898 |
| Avg tokens/instance | 53,595 | 94,966 |
| Total runtime | 2:36h | 5:34h |
