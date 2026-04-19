# Run 015 Analysis — Gemma 4 26B A4B IT (Vertex MaaS) Full Subset16, Proxy Auth Refresh

Run ID: run_015__gemma4_26b_a4b_it_maas__subset16_2x_p2_proxyfair  
Date: 2026-04-19  
Model: google/gemma-4-26b-a4b-it-maas (Vertex OpenAI-compatible endpoint via local refresh proxy)

## 1. Configuration

- Tasks: 16 (subset16)
- Repeats: 2
- Total instances: 32
- Parallel workers: 2
- Fairness controls preserved vs run_004:
  - MAGENTIC_MAX_TURNS=4
  - MAGENTIC_MAX_STALLS=2
  - Orchestrator max_tokens=24,576
  - Coder max_tokens=12,288
  - Web/File max_tokens=8,192
- Reliability hardening enabled:
  - Preflight API/auth check before run
  - Token-refresh proxy for on-the-fly reauthentication

## 2. Overall Results

| Metric | Value |
|---|---|
| Instance pass rate | 9/32 (28.1%) |
| Task pass rate (any repeat) | 7/16 (43.8%) |
| Task pass rate (all repeats) | 2/16 (12.5%) |
| Prompt tokens | 1,791,783 |
| Completion tokens | 168,549 |
| Total tokens | 1,960,332 |
| Total runtime | 2,675s (44.6 min) |
| Avg runtime/instance | 83.6s |
| Avg tokens/instance | 61,260.4 |
| LLM calls | 553 |
| Errors | 62 |

## 3. Level Breakdown (instances)

| Level | Passes | Pass Rate |
|---|---|---|
| L1 | 5/10 | 50.0% |
| L2 | 3/16 | 18.8% |
| L3 | 1/6 | 16.7% |

## 4. Failure Breakdown

| Category | Count |
|---|---|
| WRONG_ANSWER | 16 |
| NO_FINAL_ANSWER | 7 |
| PASS | 9 |

## 5. Reliability Signals

- HTTP/auth 401 failures: 0
- Length-finish truncation markers: 0
- Timeout markers: 0

Interpretation: the reauthentication strategy removed the run_014-style operational auth/truncation confounds.

## 6. Comparison Notes

Compared to run_014 (Vertex, p=2, no refresh-proxy hardening):
- Instance pass rate improved: 28.1% vs 21.9% (+6.2 pts).
- Task pass-any improved: 43.8% vs 31.2% (+12.6 pts).
- No-final-answer reduced: 7 vs 12.
- Runtime improved: 44.6 min vs 59.7 min.

Compared to run_004 (local Gemma baseline):
- Lower instance quality: 28.1% vs 34.4%.
- Similar L2 pass rate (18.8% vs 18.8%).
- Lower L3 pass rate in this run (16.7% vs 33.3%).

Compared to run_012 (GLM-4.5-Air cloud):
- Lower instance quality: 28.1% vs 31.2%.
- Equal task pass-any: 43.8% vs 43.8%.
- Much faster runtime: 44.6 min vs ~4.5h.

## 7. Conclusion

This corrected Vertex Gemma rerun is materially stronger than run_014 and operationally clean under fairness settings, but still below run_004 on overall instance pass rate.
