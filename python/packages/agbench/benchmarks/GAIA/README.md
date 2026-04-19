# GAIA Benchmark

This scenario implements the [GAIA](https://arxiv.org/abs/2311.12983) agent benchmark. Before you begin, make sure you have followed instruction in `../README.md` to prepare your environment.

### Setup Environment Variables for AgBench

Navigate to GAIA

```bash
cd benchmarks/GAIA
```

Update `config.yaml` to point to your model host, as appropriate. The default configuration points to 'gpt-4o'.

Now initialize the tasks.

```bash
python Scripts/init_tasks.py
```

Note: This will attempt to download GAIA from Hugginface, but this requires authentication.

The resulting folder structure should look like this:

```
.
./Downloads
./Downloads/GAIA
./Downloads/GAIA/2023
./Downloads/GAIA/2023/test
./Downloads/GAIA/2023/validation
./Scripts
./Templates
./Templates/TeamOne
```

Then run `Scripts/init_tasks.py` again.

Once the script completes, you should now see a folder in your current directory called `Tasks` that contains one JSONL file per template in `Templates`.

### Running GAIA

Now to run a specific subset of GAIA use:

```bash
agbench run Tasks/gaia_validation_level_1__MagenticOne.jsonl
```

You should see the command line print the raw logs that shows the agents in action To see a summary of the results (e.g., task completion rates), in a new terminal run the following:

```bash
agbench tabulate Results/gaia_validation_level_1__MagenticOne/
```

### Running with Live Progress Dashboard

To run with a Rich live terminal dashboard (progress bar, ETA, active instances, token/cost stats), use the `run_with_progress.py` wrapper:

```bash
# Generic usage
/path/to/.venv/bin/python3 Scripts/run_with_progress.py <TASKS_FILE.jsonl> \
    -r <REPEAT> \
    -p <PARALLEL> \
    --refresh-seconds 0.5 \
    --log-tail-lines 6

# Example: 40-task subset, 3 repeats, 1 parallel worker
/home/atemin/autogen/.venv/bin/python3 Scripts/run_with_progress.py \
    Tasks/gaia_validation_subset40__MagenticOne.jsonl \
    -r 3 -p 1 \
    --refresh-seconds 0.5 \
    --log-tail-lines 6

# Quick sanity check: 10-task subset, 1 repeat, 2 parallel (~55 min)
# Note: agbench does not support -p and -s together; use a pre-sliced task file instead.
/home/atemin/autogen/.venv/bin/python3 Scripts/run_with_progress.py \
    Tasks/gaia_validation_subset10__MagenticOne.jsonl \
    -r 1 -p 2 \
    --refresh-seconds 0.5 \
    --log-tail-lines 6
```

To see all available options:

```bash
/home/atemin/autogen/.venv/bin/python3 Scripts/run_with_progress.py --help
```

After the run completes, tabulate results with cost and CAI metrics:

```bash
/home/atemin/autogen/.venv/bin/python3 Scripts/custom_tabulate.py \
    Results/<RUN_FOLDER>/ \
    --prompt-cost-per-1m 0.20 \
    --completion-cost-per-1m 0.80
```

---

## What We Added vs Upstream

This section describes changes made to the upstream AutoGen MagenticOne GAIA scenario. All modifications are in the `gaia-agentic-metrics-progress` branch.

### New Files

| File | Purpose |
|------|---------|
| `Scripts/run_with_progress.py` | Live terminal dashboard wrapper around agbench with Rich progress bar, ETA, active-instances table, per-instance log tail, token/cost stats, and graceful interrupt (SIGINT). |
| `Scripts/custom_tabulate.py` | Extended tabulator: parses `metrics.json` per instance, computes CAI (Correct-Answer-Instances), total tokens, cost estimates, level breakdown summary. |
| `Templates/MagenticOne/scenario_finalize.sh` | Bash post-run script that extracts `FINAL ANSWER:` from `console_log.txt`, normalizes it (lowercase, strip punctuation), compares against `expected_answer.txt`, and emits `ALL TESTS PASSED` or `TESTS FAILED` markers for agbench to tabulate. |
| `METRICS_STRATEGY.md` | Internal document describing our agentic metrics design, token budget reasoning, and evaluation methodology. |
| `convert_parquet_to_jsonl.py` | Utility to convert GAIA Parquet dataset to JSONL format compatible with the MagenticOne template. |
| `Tasks/gaia_validation_subset16__MagenticOne.jsonl` | 16-task subset used for all full evaluation runs. |
| `Tasks/gaia_validation_subset40__MagenticOne.jsonl` | Larger 40-task subset for extended evaluations. |
| `EvalRuns/model_eval_archives/` | Archive folder for published evaluation run artifacts (reports, metadata, config snapshots). |
| `EvalRuns/model_eval_archives/EVALUATION_REPORT.md` | Aggregate metrics report covering all published evaluation runs. |

### Modified Files

| File | Change |
|------|--------|
| `Templates/MagenticOne/scenario.py` | Added `LLMEventLogHandler` to write every LLM call to `llm_events.jsonl`; added post-run metrics extraction (prompt/completion tokens, error count, LLM call count, final/expected answer comparison); writes `metrics.json` per instance; max_tokens tuned to 24,576/12,288/8,192 across agent roles to stay within context window. |
| `config.yaml` | Made model endpoint and API key configurable; added support for structured-output toggle and thinking disable; tuned default parameters for non-GPT models. |
| `agbench/src/agbench/template/global_init.sh` | Added shared-venv reactivation for native (non-Docker) mode: when running outside Docker, agbench's per-instance `.agbench_venv` is replaced with the shared project venv so `pip install` runs instantly instead of downloading packages 32 times per run. |

---

## Monitoring and Observability

Each instance run produces:

- **`llm_events.jsonl`** — one JSON line per LLM call with `prompt_tokens`, `completion_tokens`, `model`, `timestamp`.
- **`metrics.json`** — instance summary: `prompt_tokens`, `completion_tokens`, `total_tokens`, `llm_call_count`, `error_count`, `final_answer`, `expected_answer`, `pass`.
- **`console_log.txt`** — full agent conversation and tool output (existing agbench file).
- **Terminal dashboard** — `run_with_progress.py` shows real-time per-instance status during the run.

After a run completes, aggregate token and cost metrics are available via `Scripts/custom_tabulate.py`.

---

## Verified Model Integrations

The following model endpoints have been tested end-to-end through the full evaluation pipeline (smoke run + full 32-instance run):

| Model | Interface | Config file | Status |
|-------|-----------|------------|--------|
| GLM-4.7-Flash-APEX-I-Mini (GGUF) | llama.cpp localhost:8080 | `config.yaml` default | ✓ Verified (runs 002, 003) |
| Gemma-4-26B-A4B (GGUF) | llama.cpp localhost:8080 | `config.yaml` default | ✓ Verified (run 004) |
| GLM-4.5-Air | Z.AI cloud (api.z.ai/api/paas/v4) | `config.zai_glm45_air.yaml` | ✓ Verified (run 012) |
| Gemma-4-26B-A4B-IT | Google Vertex AI MaaS (OpenAI-compat) | `config.gemma4_26b_a4b_it.yaml` | ✓ Verified (run 015) |
| Gemma-4-26B-A4B | Google Gemini API | `config.gemma4_26b_a4b_it.yaml` | ✓ Verified (smoke test) |

All cloud providers use OpenAI-compatible endpoints. Set the relevant environment variable before running:

```bash
# Z.AI
export ZAI_API_KEY=...

# Vertex AI MaaS (requires running the token-refresh proxy — not included in this repo)
export VERTEX_ACCESS_TOKEN=$(gcloud auth print-access-token)

# Gemini API
export GEMINI_API_KEY=...
```

---

## Testing Procedures

### 1. Smoke Test (1 task, 1 instance)

Used to validate the pipeline end-to-end before committing to a full run:

```bash
# Start the model server (llama.cpp or cloud proxy)
# Then run 1 task, 1 repeat, 1 parallel
agbench run Tasks/gaia_validation_subset1__MagenticOne.jsonl -r 1 -p 1 \
    --refresh-seconds 0.5 --log-tail-lines 8
```

Expected result: `ALL TESTS PASSED` or `TESTS FAILED` — either is acceptable; what matters is that the pipeline completed without crash or hang.

### 2. 2-Task Smoke Run (4 instances)

Used to verify multi-instance parallelism and error recovery before a full run:

```bash
agbench run Tasks/gaia_validation_subset2__MagenticOne.jsonl -r 2 -p 2 \
    --refresh-seconds 0.5
```

### 3. Full Evaluation Run (16 tasks × 2 repeats = 32 instances)

Standard full run with the live dashboard:

```bash
# With Rich live dashboard (recommended)
python Scripts/run_with_progress.py \
    Tasks/gaia_validation_subset16__MagenticOne.jsonl \
    -r 2 -p 1 \
    --refresh-seconds 0.5 \
    --log-tail-lines 6

# With p=2 parallel workers (faster, requires sufficient VRAM or cloud credits)
python Scripts/run_with_progress.py \
    Tasks/gaia_validation_subset16__MagenticOne.jsonl \
    -r 2 -p 2 \
    --refresh-seconds 0.5 \
    --log-tail-lines 6
```

### 4. Tabulate Results

After a run, compute pass rates and token stats:

```bash
# Basic agbench tabulation (pass/fail counts)
agbench tabulate Results/gaia_validation_subset16__MagenticOne/

# Extended tabulation with token cost estimates
python Scripts/custom_tabulate.py \
    Results/gaia_validation_subset16__MagenticOne/ \
    --prompt-cost-per-1m 0.20 \
    --completion-cost-per-1m 0.80
```

### 5. curl API Test

Quick health-check of a running model server without agbench:

```bash
# Test llama.cpp local server
curl http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "Say hello"}], "max_tokens": 50}'

# Test Z.AI cloud endpoint
curl https://api.z.ai/api/paas/v4/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ZAI_API_KEY" \
    -d '{"model": "glm-4.5-air", "messages": [{"role": "user", "content": "Say hello"}], "max_tokens": 50}'

# Test Vertex AI MaaS endpoint (requires valid token)
curl https://<VERTEX_ENDPOINT>/v1/projects/<PROJECT>/locations/<REGION>/endpoints/openapi/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $VERTEX_ACCESS_TOKEN" \
    -d '{"model": "google/gemma-4-26b-it", "messages": [{"role": "user", "content": "Say hello"}], "max_tokens": 50}'
```

### Testing Process Summary

1. **Configure** `config.yaml` (or a per-model config file) with model endpoint and env-var API key.
2. **Start backend**: llama.cpp server, cloud proxy, or Vertex token-refresh proxy.
3. **Smoke test** with 1 task to confirm the pipeline runs.
4. **Full run** with `run_with_progress.py` for the 16-task subset.
5. **Tabulate** with `custom_tabulate.py` for metrics.
6. **Archive** results with the internal archiving scripts (excluded from this repo).

---

## References

**GAIA: a benchmark for General AI Assistants** `<br/>`
Grégoire Mialon, Clémentine Fourrier, Craig Swift, Thomas Wolf, Yann LeCun, Thomas Scialom `<br/>`
[https://arxiv.org/abs/2311.12983](https://arxiv.org/abs/2311.12983)
