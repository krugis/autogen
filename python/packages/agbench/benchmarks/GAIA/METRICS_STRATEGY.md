# GAIA Benchmark Metrics Improvement Strategy

## Status

Implemented in this repository for `MagenticOne`:

- Token counting per task and per run aggregate
- Structured LLM call event logging (`llm_events.jsonl`)
- Structured agent event logging (`agent_events.log`)
- Per-task machine-readable metrics artifact (`metrics.json`)
- Extended tabulation with efficiency metrics

## Token Counting Decision

Chosen approach:

- `total_usage()` from AutoGen model clients for aggregate prompt/completion tokens
- `LLMCallEvent` capture for per-call event-level usage

Not used:

- Langfuse (extra infra requirement, unnecessary for local benchmark loop)
- tiktoken-only estimation (less accurate than provider-reported usage)

## Implemented Metrics

### Per-task metrics (stored in `metrics.json`)

| Metric | Source |
|--------|--------|
| `prompt_tokens` | Sum of `client.total_usage().prompt_tokens` across orchestrator/coder/web/file clients |
| `completion_tokens` | Sum of `client.total_usage().completion_tokens` across clients |
| `total_tokens` | `prompt_tokens + completion_tokens` |
| `agent_messages` | Number of messages in `TaskResult.messages` |
| `tool_calls` | Count from `agent_events.log` (`ToolCallRequestEvent` / `ToolCallExecutionEvent`), with message-type fallback |
| `final_answer_found` | Whether any message includes `FINAL ANSWER:` |
| `llm_call_count` | Number of lines in `llm_events.jsonl` |
| `error_count` | Count of error-like events from messages (`error/exception/traceback/failed`) |

### Tabulated per-trial aggregates

| Metric | Meaning |
|--------|---------|
| `Successes`, `Failures`, `Missing`, `Total` | Existing task outcome counts |
| `Avg Success Rate` | `successes / (successes + failures)` |
| `Avg Time (s)`, `Total Time (s)` | Existing timing metrics |
| `Prompt Tokens`, `Completion Tokens`, `Total Tokens` | Token totals across tasks |
| `Avg Tokens/Task` | Mean task token usage |
| `Avg Agent Messages` | Mean messages per task |
| `Total Tool Calls`, `Avg Tool Calls` | Tool call totals/means |
| `Avg LLM Calls` | Mean LLM call count |
| `Final Answer Found Rate` | Fraction of tasks with detected final answer |
| `Total Errors`, `Avg Errors` | Error counts aggregated across tasks |
| `Messages/Success` | Mean messages per successful task |
| `LLM Calls/Success` | Mean LLM calls per successful task |
| `Successes per 1K Tokens` | $\text{successes} \times 1000 / \text{total tokens}$ |
| `Recovery Rate After Error` | Fraction of errored tasks that still succeeded |
| `Estimated Total Cost (USD)` | Token-priced estimate from CLI rates |
| `Cost/Success (USD)` | Estimated total cost divided by successes |
| `Tokens/Success` | `total tokens / successes` |
| `Composite Agentic Capability Index` | Weighted 0-100 capability score combining correctness, efficiency, and reliability |

Cost arguments supported in tabulation:

- `--prompt-cost-per-1m`
- `--completion-cost-per-1m`

### Composite Agentic Capability Index (implemented)

CAI is computed per trial on a 0-100 scale:

$$
\mathrm{CAI} = 100 \times \Big(
0.35\,S + 0.15\,F + 0.15\,T + 0.10\,K + 0.10\,L + 0.05\,M + 0.05\,E + 0.05\,R
\Big)
$$

Where:

- $S$: Avg Success Rate
- $F$: Final Answer Found Rate
- $T$: Time score (inverse-normalized; better at lower average runtime)
- $K$: Token score (inverse-normalized; better at lower avg tokens/task)
- $L$: LLM call score (inverse-normalized; better at fewer calls)
- $M$: Message score (inverse-normalized; better at fewer messages)
- $E$: Error score (inverse-normalized; better at fewer errors)
- $R$: Recovery Rate After Error (defaults to 1.0 when no errored tasks are observed)

Current normalization anchors:

- Avg Time (good=60s, bad=600s)
- Avg Tokens/Task (good=10k, bad=120k)
- Avg LLM Calls (good=6, bad=30)
- Avg Agent Messages (good=8, bad=40)
- Avg Errors (good=0, bad=5)

These anchors are intended to be tuned as benchmark distributions evolve.

## Produced Artifacts Per Instance

Each task instance directory now contains:

- `console_log.txt`
- `metrics.json`
- `llm_events.jsonl`
- `agent_events.log`

## File Change Map

| File | Implemented change |
|------|---------------------|
| `Templates/MagenticOne/scenario.py` | Added event handlers, token aggregation, tool/final-answer/LLM-call metrics, writes `metrics.json`, emits metric lines to console |
| `Scripts/custom_tabulate.py` | Reads `metrics.json` (or console fallback), adds new trial columns, prints extended aggregate efficiency metrics |

## Remaining Future Enhancements

These are intentionally not implemented yet:

- Multi-seed variance and confidence intervals
- Cross-level breakdown when evaluating mixed-level task sets
- Recovery metrics (error then success)
- Cost estimation with configurable pricing table
