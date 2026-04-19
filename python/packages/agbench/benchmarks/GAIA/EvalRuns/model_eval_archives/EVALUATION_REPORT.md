# GAIA Benchmark — Evaluation Report

**Benchmark:** GAIA (General AI Assistants)  
**Framework:** AutoGen MagenticOne via agbench  
**Dataset:** 16-task validation subset (subset16), 2 repeats = 32 instances per full run  
**Report date:** 2026-04-19  

This report collects all available metrics from the five evaluation runs published in this repository.

---

## Summary Table

| Run | Model | Provider / Infra | Tasks | Instances | Passed | Pass Rate | Total Tokens | Runtime |
|-----|-------|-----------------|-------|-----------|--------|-----------|--------------|---------|
| [run_002](#run_002) | GLM-4.7-Flash-APEX-I-Mini | llama.cpp local | 1 | 1 | 1 | 100% (smoke) | 30,628 | 00:02:51 |
| [run_003](#run_003) | GLM-4.7-Flash-APEX-I-Mini | llama.cpp local | 16 | 32 | 5 | 15.6% | 3,038,898 | 5:34h |
| [run_004](#run_004) | Gemma-4-26B-A4B | llama.cpp local | 16 | 32 | 11 | 34.4% | 2,176,060 | 59.4 min |
| [run_012](#run_012) | GLM-4.5-Air | Z.AI cloud API | 16 | 32 (30 ok) | 10 | 31.2% | 2,973,337 | — |
| [run_015](#run_015) | Gemma-4-26B-A4B-IT MaaS | Vertex AI MaaS | 16 | 32 | 9 | 28.1% | 1,960,332 | 00:44:35 |

> **Best overall:** run_004 (Gemma local) at **34.4%**  
> **Most efficient (tokens):** run_002 smoke baseline (30 K tokens/1 task)  
> **Fastest full run:** run_015 (Vertex MaaS, p=2 parallel) at **44:35 min**

---

## run_002 — GLM Smoke Test {#run_002}

| Field | Value |
|-------|-------|
| Run ID | `run_002__glm47_flash_apex_i_mini__subset1_smoke__20260416_222234` |
| Date | 2026-04-16 |
| Model | GLM-4.7-Flash-APEX-I-Mini.gguf |
| API | llama.cpp localhost:8080 |
| Task file | gaia_validation_subset1__MagenticOne.jsonl |
| Tasks / Instances | 1 / 1 |
| Run type | Smoke run (1 task, 1 repeat) |
| **Pass rate** | **100% (1/1)** |
| Total tokens | 30,628 |
| Avg tokens/instance | 30,628 |
| Elapsed | 00:02:51 |
| LLM calls | 8 |
| Errors | 1 |
| FINAL_ANSWER_EXTRACTED | 6 |
| EXPECTED_ANSWER | 6 |
| Result | ALL TESTS PASSED |

**Notes:** Smoke run used to validate that the full evaluation pipeline (agbench, Docker, llama.cpp server, MagenticOne agents) works end-to-end before committing to a full 32-instance run.

---

## run_003 — GLM-4.7 Full Run {#run_003}

| Field | Value |
|-------|-------|
| Run ID | `run_003__glm47_flash_apex_i_mini__subset16_2x__20260417_201549` |
| Date | 2026-04-17 |
| Model | GLM-4.7-Flash-APEX-I-Mini.gguf |
| Context window | 98,304 tokens |
| API | llama.cpp localhost:8080 |
| Tasks / Repeats / Instances | 16 / ×2 / 32 |
| **Pass rate** | **15.6% (5/32 instances)** |
| Total tokens | 3,038,898 |
| Avg tokens/instance | 94,966 |
| Total runtime | 20,063 s (5:34 h) |
| Avg runtime/instance | 626 s |
| LLM calls | — |

### Token Allocation
| Client | max_tokens |
|--------|-----------|
| Orchestrator | 24,576 |
| Coder | 12,288 |
| Web / File | 8,192 |

### Pass Rate by Level
| Level | Passed | Pass Rate |
|-------|--------|-----------|
| L1 (Explicit) | 2/10 | 20.0% |
| L2 (Implicit) | 3/16 | 18.8% |
| L3 (Reasoning) | 0/6 | 0.0% |

### Failure Root Causes
| Cause | Count | % of failures |
|-------|-------|---------------|
| WRONG_ANSWER | 15 | 55.6% |
| NO_FINAL_ANSWER (total) | 12 | 44.4% |
| → LengthFinishReasonError (orchestrator ceiling 24576) | 4 | — |
| → LedgerEntry JSON parse/pydantic error | 5 | — |
| → Tool error exhausted turns | 2 | — |
| → Misc | 1 | — |

**Notes:** Very long runtime (5.5 h) due to high avg tokens/instance. GLM showed significantly better format compliance (62.5%) vs earlier Gemma test (25%), but the context limit hit (LengthFinishReason) became the dominant failure mode for harder tasks.

---

## run_004 — Gemma-4-26B Full Run {#run_004}

| Field | Value |
|-------|-------|
| Run ID | `run_004__gemma4_26b_a4b__subset16_2x__20260417_220653` |
| Date | 2026-04-17 |
| Model | gemma-4-26B-A4B-APEX-I-Mini.gguf |
| Context window | 98,304 tokens |
| API | llama.cpp localhost:8080 |
| Tasks / Repeats / Instances | 16 / ×2 / 32 |
| **Pass rate** | **34.4% (11/32 instances)** |
| Prompt tokens | 1,973,628 |
| Completion tokens | 202,432 |
| Total tokens | 2,176,060 |
| Avg tokens/instance | 68,001.9 |
| Total runtime | 3,562 s (59.4 min) |
| Avg runtime/instance | 111.3 s |
| Total LLM calls | 625 |
| Avg LLM calls/instance | 19.5 |
| Avg tokens/LLM call | 3,481.7 |

### Pass Rate by Level
| Level | Passed | Pass Rate |
|-------|--------|-----------|
| L1 (Explicit) | 6/10 | 60.0% |
| L2 (Implicit) | 3/16 | 18.8% |
| L3 (Reasoning) | 2/6 | 33.3% |

### Pass Rate by Attachment Type
| Attachment | Passed | Pass Rate |
|-----------|--------|-----------|
| No file | 6/22 | 27.3% |
| Has file | 5/10 | 50.0% |

### Failure Categories
| Category | Count |
|----------|-------|
| WRONG_ANSWER | 18 |
| NO_FINAL_ANSWER (ledger parse) | 2 |
| NO_FINAL_ANSWER (other) | 1 |

**Notes:** Best performing local model. Running 6× faster than GLM run_003 with higher pass rate — shorter, more efficient LLM calls and far fewer parser failures. File-attached tasks had 50% success rate, noticeably better than no-attachment tasks.

---

## run_012 — GLM-4.5-Air via Z.AI Cloud {#run_012}

| Field | Value |
|-------|-------|
| Run ID | `run_012__glm45_air_zai__subset16_prod__20260418_140435` |
| Date | 2026-04-18 |
| Model | glm-4.5-air |
| Provider | Z.AI cloud (api.z.ai) |
| API base URL | https://api.z.ai/api/paas/v4 |
| Tasks / Instances | 16 / 32 |
| Completed instances | 30/32 |
| **Pass rate (instances)** | **31.2% (10/32)** |
| **Pass rate (tasks)** | **43.8% (7/16)** |
| Total tokens | 2,973,337 |
| Prompt tokens | 2,144,344 |
| Completion tokens | 828,993 |
| LLM calls | 618 |
| Errors | 52 |
| Config | structured_output=false, thinking=disabled |

**Notes:** First cloud-API run. 2 instances did not complete (likely rate limit / timeout). Task-level pass rate (43.8%) is notably higher than instance-level (31.2%), meaning many tasks passed in one repeat but not both. High error count (52) reflects transient HTTP failures against the cloud endpoint. Thinking (chain-of-thought) was disabled to reduce token cost.

---

## run_015 — Gemma-4-26B-A4B-IT via Vertex AI MaaS {#run_015}

| Field | Value |
|-------|-------|
| Run ID | `run_015__gemma4_26b_a4b_it_maas__subset16_2x_p2_proxyfair__20260419_215905` |
| Date | 2026-04-19 |
| Model | gemma-4-26b-it (Vertex AI MaaS) |
| Provider | Google Vertex AI Model-as-a-Service |
| Tasks / Repeats / Instances | 16 / ×2 / 32 |
| Parallel workers | p=2 |
| **Pass rate** | **28.1% (9/32 instances)** |
| Total tokens | 1,960,332 |
| Elapsed | 00:44:35 |
| HTTP 401 auth failures | 0 |

**Notes:** First run using the Vertex AI MaaS endpoint with the token-refresh proxy (`vertex_openai_refresh_proxy.py`). The proxy handles periodic `gcloud auth print-access-token` refresh so long runs do not expire mid-run. Zero 401 auth errors confirms the proxy works reliably. Running with p=2 parallel workers cut wall-clock time to 44 min (vs ~90 min est. at p=1). Lower pass rate than local Gemma run_004 (28.1% vs 34.4%) likely reflects the instruction-tuned variant's different behavior on agentic tasks.

---

## Cross-Run Comparison

### Pass Rate Progression
```
run_002 (smoke)  ████████████████████ 100% (1/1)  [validation only]
run_003 (GLM-4.7)  ███░░░░░░░░░░░░░░   15.6% (5/32)
run_004 (Gemma-4 local)  ███████░░░░░  34.4% (11/32)  ← best local
run_012 (GLM-4.5 cloud)  ██████░░░░░░  31.2% (10/32)
run_015 (Gemma Vertex)   █████░░░░░░░  28.1% (9/32)
```

### Token Efficiency (full runs)
| Run | Total Tokens | Instances | Avg/Instance |
|-----|-------------|-----------|--------------|
| run_015 | 1,960,332 | 32 | 61,260 |
| run_004 | 2,176,060 | 32 | 68,001 |
| run_012 | 2,973,337 | 32 | 92,917 |
| run_003 | 3,038,898 | 32 | 94,966 |

### Runtime Efficiency (full runs)
| Run | Total Runtime | Parallel | Wall-clock |
|-----|--------------|----------|-----------|
| run_015 | — | p=2 | 00:44:35 |
| run_004 | 59.4 min | p=1 | ~60 min |
| run_003 | 5:34 h | p=1 | ~5:34 h |

---

## Metrics Definitions

| Metric | Definition |
|--------|-----------|
| Pass rate (instances) | Instances where FINAL_ANSWER matched EXPECTED_ANSWER / total instances |
| Pass rate (tasks) | Tasks where at least one repeat passed / total tasks |
| Total tokens | Prompt + completion tokens across all instances and all LLM calls |
| LLM calls | Total API calls to the model endpoint across the full run |
| Errors | Count of exception/error events logged in instance metrics |
| Runtime | Wall-clock elapsed time from run start to completion |
| L1/L2/L3 | GAIA difficulty levels: L1=explicit lookup, L2=implicit reasoning, L3=multi-step reasoning |
| WRONG_ANSWER | Agent produced a final answer but it was incorrect |
| NO_FINAL_ANSWER | Agent exhausted turns/budget without producing a valid concluding answer |
| LengthFinishReasonError | LLM response cut off due to max_tokens ceiling |

---

## Environment Notes

- **Local runs (run_002/003/004):** llama.cpp server on localhost:8080, GGUF quantized models, `--ctx-size 98304`
- **Cloud runs (run_012):** Z.AI cloud API; API key via env var `ZAI_API_KEY`
- **Vertex MaaS (run_015):** Vertex AI OpenAI-compatible endpoint; token refreshed via local proxy; env var `VERTEX_ACCESS_TOKEN`
- **MagenticOne settings:** `MAGENTIC_MAX_TURNS=4`, `MAGENTIC_MAX_STALLS=2` for all runs
- **agbench version:** AutoGen MagenticOne scenario, modified for GAIA subset16 task file
