import argparse
import os
import re
import string
import sys

import json
import pandas as pd
import tabulate as tb

from agbench.tabulate_cmd import EXCLUDE_DIR_NAMES, default_timer

def in_house_normalize_answer(a):
    # Lower case
    # Trim (left and right)
    # standardize comma separated values
    # Replace multiple spaces with one space
    # Remove trailing punctuation
    norm_answer = ", ".join(a.strip().lower().split(","))
    norm_answer = re.sub(r"[\.\!\?]+$", "", re.sub(r"\s+", " ", norm_answer))
    return norm_answer


def in_house_question_scorer(
    model_answer: str,
    ground_truth: str,
) -> bool:
     n_ma = in_house_normalize_answer(model_answer)
     n_gt = in_house_normalize_answer(ground_truth)
     return (n_gt != "" and n_gt == n_ma)
 

def gaia_question_scorer(
    model_answer: str,
    ground_truth: str,
) -> bool:
    #FROM: https://huggingface.co/spaces/gaia-benchmark/leaderboard/blob/main/scorer.py

    def normalize_number_str(number_str: str) -> float:
        # we replace these common units and commas to allow
        # conversion to float
        for char in ["$", "%", ","]:
            number_str = number_str.replace(char, "")
        try:
            return float(number_str)
        except ValueError:
            print(f"String {number_str} cannot be normalized to number str.")
            return float("inf")

    def split_string(s: str, char_list: list[str] = [",", ";"],) -> list[str]:
        pattern = f"[{''.join(char_list)}]"
        return re.split(pattern, s)

    def normalize_str(input_str, remove_punct=True) -> str:
        """
        Normalize a string by:
        - Removing all white spaces
        - Optionally removing punctuation (if remove_punct is True)
        - Converting to lowercase
        Parameters:
        - input_str: str, the string to normalize
        - remove_punct: bool, whether to remove punctuation (default: True)
        Returns:
        - str, the normalized string
        """
        # Remove all white spaces. Required e.g for seagull vs. sea gull
        no_spaces = re.sub(r"\s", "", input_str)

        # Remove punctuation, if specified.
        if remove_punct:
            translator = str.maketrans("", "", string.punctuation)
            return no_spaces.lower().translate(translator)
        else:
            return no_spaces.lower()


    def is_float(element: any) -> bool:
        try:
            float(element)
            return True
        except ValueError:
            return False

    # if gt is a number
    if is_float(ground_truth):
        normalized_answer = normalize_number_str(model_answer)
        return normalized_answer == float(ground_truth)

    # if gt is a list
    elif any(char in ground_truth for char in [",", ";"]):
        # question with the fish: normalization removes punct

        gt_elems = split_string(ground_truth)
        ma_elems = split_string(model_answer)

        # check length is the same
        if len(gt_elems) != len(ma_elems):
            #warnings.warn(
            #    "Answer lists have different lengths, returning False.", UserWarning
            #)
            return False

        # compare each element as float or str
        comparisons = []
        for ma_elem, gt_elem in zip(ma_elems, gt_elems):
            if is_float(gt_elem):
                normalized_ma_elem = normalize_number_str(ma_elem)
                comparisons.append(normalized_ma_elem == float(gt_elem))
            else:
                # we do not remove punct since comparisons can include punct
                comparisons.append(
                    normalize_str(ma_elem, remove_punct=False)
                    == normalize_str(gt_elem, remove_punct=False)
                )
        return all(comparisons)

    # if gt is a str
    else:
        return normalize_str(model_answer) == normalize_str(ground_truth)


##############

PROMPT_TOKENS_REGEX = r"PROMPT_TOKENS:\s*(\d+)\s*!#!#"
COMPLETION_TOKENS_REGEX = r"COMPLETION_TOKENS:\s*(\d+)\s*!#!#"
AGENT_MESSAGES_REGEX = r"AGENT_MESSAGES:\s*(\d+)\s*!#!#"
TOOL_CALLS_REGEX = r"TOOL_CALLS:\s*(\d+)\s*!#!#"
FINAL_ANSWER_FOUND_REGEX = r"FINAL_ANSWER_FOUND:\s*(\d+)\s*!#!#"
LLM_CALL_COUNT_REGEX = r"LLM_CALL_COUNT:\s*(\d+)\s*!#!#"
ERROR_COUNT_REGEX = r"ERROR_COUNT:\s*(\d+)\s*!#!#"
ERROR_REGEX = r"\b(error|exception|traceback|failed)\b"


def token_metrics(instance_dir):
    """Parse per-task metrics from metrics.json or console_log.txt."""
    metrics_file = os.path.join(instance_dir, "metrics.json")
    if os.path.isfile(metrics_file):
        with open(metrics_file, "rt") as fh:
            data = json.load(fh)
        prompt = data.get("prompt_tokens")
        completion = data.get("completion_tokens")
        total = data.get("total_tokens")
        messages = data.get("agent_messages")
        tool_calls = data.get("tool_calls")
        final_answer_found = data.get("final_answer_found")
        llm_call_count = data.get("llm_call_count")
        error_count = data.get("error_count")
        if total is None and prompt is not None and completion is not None:
            total = prompt + completion
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            "agent_messages": messages,
            "tool_calls": tool_calls,
            "final_answer_found": final_answer_found,
            "llm_call_count": llm_call_count,
            "error_count": error_count,
        }

    console_log_file = os.path.join(instance_dir, "console_log.txt")
    if not os.path.isfile(console_log_file):
        return None

    with open(console_log_file, "rt") as fh:
        content = fh.read()

    def _int(pattern):
        m = re.search(pattern, content)
        return int(m.group(1)) if m else None

    prompt = _int(PROMPT_TOKENS_REGEX)
    completion = _int(COMPLETION_TOKENS_REGEX)
    messages = _int(AGENT_MESSAGES_REGEX)
    tool_calls = _int(TOOL_CALLS_REGEX)
    final_answer_found = _int(FINAL_ANSWER_FOUND_REGEX)
    llm_call_count = _int(LLM_CALL_COUNT_REGEX)
    error_count = _int(ERROR_COUNT_REGEX)
    if error_count is None:
        error_count = len(re.findall(ERROR_REGEX, content, flags=re.IGNORECASE))

    total = None
    if prompt is not None and completion is not None:
        total = prompt + completion

    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "agent_messages": messages,
        "tool_calls": tool_calls,
        "final_answer_found": bool(final_answer_found) if final_answer_found is not None else None,
        "llm_call_count": llm_call_count,
        "error_count": error_count,
    }


def scorer(instance_dir):
    # Read the expected answer
    expected_answer_file = os.path.join(instance_dir, "expected_answer.txt")
    if not os.path.isfile(expected_answer_file):
        return None

    expected_answer = None
    with open(expected_answer_file, "rt") as fh:
        expected_answer = fh.read().strip()

    # Read the console
    console_log_file = os.path.join(instance_dir, "console_log.txt")
    if not os.path.isfile(console_log_file):
        return None

    console_log = ""
    with open(console_log_file, "rt") as fh:
        console_log = fh.read()

        final_answer = None
        m = re.search(r"FINAL ANSWER:(.*?)\n", console_log, re.DOTALL)
        if m:
            final_answer = m.group(1).strip()

        # Missing the final answer line
        if final_answer is None:
            return None

        # Return true if they are equal after normalization
        # return in_house_question_scorer(final_answer, expected_answer)
        return gaia_question_scorer(final_answer, expected_answer)


def main(args):
    invocation_cmd = args[0]
    args_rest = args[1:]

    warning = (
        f"CAUTION: '{invocation_cmd}' is in early preview and is not thoroughly tested.\n"
        "Please do not cite values from these calculations in academic work without first "
        "inspecting and verifying the results in the run logs yourself."
    )

    parser = argparse.ArgumentParser(prog=invocation_cmd)
    parser.add_argument("runlogs")
    parser.add_argument("-c", "--csv", action="store_true")
    parser.add_argument("-e", "--excel", type=str, default=None)
    parser.add_argument("--prompt-cost-per-1m", type=float, default=0.0)
    parser.add_argument("--completion-cost-per-1m", type=float, default=0.0)
    parsed = parser.parse_args(args_rest)
    runlogs = parsed.runlogs

    level_match = re.search(r"level_(\d+)", os.path.basename(os.path.normpath(runlogs)))
    benchmark_level = level_match.group(1) if level_match else "mixed/unknown"

    all_results = []
    max_instances = 0

    for task_id in sorted(
        os.listdir(runlogs),
        key=lambda s: os.path.getmtime(os.path.join(runlogs, s)),
    ):
        if task_id in EXCLUDE_DIR_NAMES:
            continue
        task_path = os.path.join(runlogs, task_id)
        if not os.path.isdir(task_path):
            continue

        results = {"Task Id": task_id}
        instance_dirs = sorted(
            os.listdir(task_path),
            key=lambda s: os.path.getmtime(os.path.join(task_path, s)),
        )
        instances = [int(d) for d in instance_dirs if d.isdigit()]

        for instance in instances:
            instance_dir = os.path.join(task_path, str(instance))
            results[f"Trial {instance} Success"] = scorer(instance_dir)
            results[f"Trial {instance} Time"] = default_timer(instance_dir)
            tm = token_metrics(instance_dir)
            if tm:
                results[f"Trial {instance} Prompt Tokens"] = tm["prompt_tokens"]
                results[f"Trial {instance} Completion Tokens"] = tm["completion_tokens"]
                results[f"Trial {instance} Total Tokens"] = tm["total_tokens"]
                results[f"Trial {instance} Agent Messages"] = tm["agent_messages"]
                results[f"Trial {instance} Tool Calls"] = tm["tool_calls"]
                results[f"Trial {instance} Final Answer Found"] = tm["final_answer_found"]
                results[f"Trial {instance} LLM Calls"] = tm["llm_call_count"]
                results[f"Trial {instance} Error Count"] = tm["error_count"]
            else:
                results[f"Trial {instance} Prompt Tokens"] = None
                results[f"Trial {instance} Completion Tokens"] = None
                results[f"Trial {instance} Total Tokens"] = None
                results[f"Trial {instance} Agent Messages"] = None
                results[f"Trial {instance} Tool Calls"] = None
                results[f"Trial {instance} Final Answer Found"] = None
                results[f"Trial {instance} LLM Calls"] = None
                results[f"Trial {instance} Error Count"] = None

        if instances:
            max_instances = max(max_instances, max(instances))
        all_results.append(results)

    num_instances = max_instances + 1

    # Pad missing trial columns
    for result in all_results:
        for i in range(num_instances):
            for col in [
                f"Trial {i} Success",
                f"Trial {i} Time",
                f"Trial {i} Prompt Tokens",
                f"Trial {i} Completion Tokens",
                f"Trial {i} Total Tokens",
                f"Trial {i} Agent Messages",
                f"Trial {i} Tool Calls",
                f"Trial {i} Final Answer Found",
                f"Trial {i} LLM Calls",
                f"Trial {i} Error Count",
            ]:
                if col not in result:
                    result[col] = None

    df = pd.DataFrame(all_results)

    if parsed.csv:
        print(df.to_csv(index=False))
        sys.stderr.write("\n" + warning + "\n\n")
        return

    if parsed.excel:
        df.to_excel(parsed.excel, index=False)
        sys.stderr.write(f"\nResults written to '{parsed.excel}'\n")
        sys.stderr.write("\n" + warning + "\n\n")
        return

    # Per-task table
    print(f"Benchmark Level: {benchmark_level}")
    print(tb.tabulate(df, headers="keys", tablefmt="simple"))

    # --- Summary Statistics ---
    print("\nSummary Statistics\n")

    def _is_true(x):
        if isinstance(x, pd.Series):
            return x.apply(lambda y: y is True)
        return x is True

    def _is_false(x):
        if isinstance(x, pd.Series):
            return x.apply(lambda y: y is False)
        return x is False

    score_cols = [f"Trial {i} Success" for i in range(num_instances)]
    time_cols = [f"Trial {i} Time" for i in range(num_instances)]
    prompt_cols = [f"Trial {i} Prompt Tokens" for i in range(num_instances)]
    completion_cols = [f"Trial {i} Completion Tokens" for i in range(num_instances)]
    total_tok_cols = [f"Trial {i} Total Tokens" for i in range(num_instances)]
    msg_cols = [f"Trial {i} Agent Messages" for i in range(num_instances)]
    tool_call_cols = [f"Trial {i} Tool Calls" for i in range(num_instances)]
    final_answer_cols = [f"Trial {i} Final Answer Found" for i in range(num_instances)]
    llm_call_cols = [f"Trial {i} LLM Calls" for i in range(num_instances)]
    error_cols = [f"Trial {i} Error Count" for i in range(num_instances)]

    successes = df[score_cols].apply(_is_true).sum(axis=0)
    failures = df[score_cols].apply(_is_false).sum(axis=0)
    missings = df[score_cols].isna().sum(axis=0)
    totals = successes + failures + missings
    avg_success_rates = successes / (successes + failures)
    avg_times = df[time_cols].mean(axis=0, skipna=True)
    total_times = df[time_cols].sum(axis=0, skipna=True)
    total_prompt = df[prompt_cols].sum(axis=0, skipna=True)
    total_completion = df[completion_cols].sum(axis=0, skipna=True)
    total_tokens = df[total_tok_cols].sum(axis=0, skipna=True)
    avg_tokens = df[total_tok_cols].mean(axis=0, skipna=True)
    avg_messages = df[msg_cols].mean(axis=0, skipna=True)
    total_tool_calls = df[tool_call_cols].sum(axis=0, skipna=True)
    avg_tool_calls = df[tool_call_cols].mean(axis=0, skipna=True)
    avg_llm_calls = df[llm_call_cols].mean(axis=0, skipna=True)
    final_answer_rate = df[final_answer_cols].mean(axis=0, skipna=True)
    total_errors = df[error_cols].sum(axis=0, skipna=True)
    avg_errors = df[error_cols].mean(axis=0, skipna=True)

    prompt_cost_rate = parsed.prompt_cost_per_1m / 1_000_000.0
    completion_cost_rate = parsed.completion_cost_per_1m / 1_000_000.0
    estimated_total_cost = pd.Series(
        (total_prompt.to_numpy(dtype=float) * prompt_cost_rate)
        + (total_completion.to_numpy(dtype=float) * completion_cost_rate),
        index=[f"Trial {i}" for i in range(num_instances)],
    )

    # Tokens per success (efficiency)
    def _tokens_per_success(trial_idx):
        s = successes.iloc[trial_idx] if hasattr(successes, "iloc") else successes
        t = total_tokens.iloc[trial_idx] if hasattr(total_tokens, "iloc") else total_tokens
        if s and s > 0:
            return round(t / s, 1)
        return None

    def _messages_per_success(trial_idx):
        s = successes.iloc[trial_idx] if hasattr(successes, "iloc") else successes
        m = avg_messages.iloc[trial_idx] if hasattr(avg_messages, "iloc") else avg_messages
        if s and s > 0 and m is not None:
            return round(m, 2)
        return None

    def _llm_calls_per_success(trial_idx):
        s = successes.iloc[trial_idx] if hasattr(successes, "iloc") else successes
        l = avg_llm_calls.iloc[trial_idx] if hasattr(avg_llm_calls, "iloc") else avg_llm_calls
        if s and s > 0 and l is not None:
            return round(l, 2)
        return None

    def _successes_per_1k_tokens(trial_idx):
        s = successes.iloc[trial_idx] if hasattr(successes, "iloc") else successes
        t = total_tokens.iloc[trial_idx] if hasattr(total_tokens, "iloc") else total_tokens
        if t and t > 0:
            return round((s * 1000.0) / t, 4)
        return None

    def _cost_per_success(trial_idx):
        s = successes.iloc[trial_idx] if hasattr(successes, "iloc") else successes
        c = estimated_total_cost.iloc[trial_idx] if hasattr(estimated_total_cost, "iloc") else estimated_total_cost
        if s and s > 0:
            return round(c / s, 6)
        return None

    def _recovery_rate(trial_idx):
        error_col = f"Trial {trial_idx} Error Count"
        success_col = f"Trial {trial_idx} Success"
        errored = df[error_col].fillna(0) > 0
        if errored.sum() == 0:
            return None
        recovered = ((df[success_col] == True) & errored).sum()  # noqa: E712
        return round(recovered / errored.sum(), 4)

    def _score_inverse(value, good, bad):
        """Return a 0..1 score where lower values are better."""
        if value is None or pd.isna(value):
            return 0.0
        if value <= good:
            return 1.0
        if value >= bad:
            return 0.0
        return float((bad - value) / (bad - good))

    def _composite_agentic_capability_index(trial_idx):
        """Compute CAI as a weighted 0..100 capability score.

        Weights prioritize correctness while still accounting for efficiency,
        reliability, and completion discipline.
        """
        success = avg_success_rates.iloc[trial_idx] if hasattr(avg_success_rates, "iloc") else avg_success_rates
        final_answer = final_answer_rate.iloc[trial_idx] if hasattr(final_answer_rate, "iloc") else final_answer_rate
        avg_time = avg_times.iloc[trial_idx] if hasattr(avg_times, "iloc") else avg_times
        token_mean = avg_tokens.iloc[trial_idx] if hasattr(avg_tokens, "iloc") else avg_tokens
        llm_mean = avg_llm_calls.iloc[trial_idx] if hasattr(avg_llm_calls, "iloc") else avg_llm_calls
        msg_mean = avg_messages.iloc[trial_idx] if hasattr(avg_messages, "iloc") else avg_messages
        err_mean = avg_errors.iloc[trial_idx] if hasattr(avg_errors, "iloc") else avg_errors
        recovery = _recovery_rate(trial_idx)
        if recovery is None:
            recovery = 1.0  # no errored runs implies no observed recovery penalty

        # Absolute normalization anchors; adjust as dataset/runtime characteristics evolve.
        time_score = _score_inverse(avg_time, good=60.0, bad=600.0)
        token_score = _score_inverse(token_mean, good=10000.0, bad=120000.0)
        llm_score = _score_inverse(llm_mean, good=6.0, bad=30.0)
        msg_score = _score_inverse(msg_mean, good=8.0, bad=40.0)
        error_score = _score_inverse(err_mean, good=0.0, bad=5.0)

        # Weighted CAI in [0, 100]
        cai = (
            0.35 * float(success if pd.notna(success) else 0.0)
            + 0.15 * float(final_answer if pd.notna(final_answer) else 0.0)
            + 0.15 * time_score
            + 0.10 * token_score
            + 0.10 * llm_score
            + 0.05 * msg_score
            + 0.05 * error_score
            + 0.05 * float(recovery)
        )
        return round(cai * 100.0, 2)

    def _list(series):
        if hasattr(series, "__iter__") and not isinstance(series, str):
            return list(series)
        return [series]

    trial_df = pd.DataFrame(
        {
            "Successes": _list(successes),
            "Failures": _list(failures),
            "Missing": _list(missings),
            "Total": _list(totals),
            "Avg Success Rate": _list(avg_success_rates),
            "Avg Time (s)": _list(avg_times),
            "Total Time (s)": _list(total_times),
            "Prompt Tokens": _list(total_prompt),
            "Completion Tokens": _list(total_completion),
            "Total Tokens": _list(total_tokens),
            "Avg Tokens/Task": _list(avg_tokens),
            "Avg Agent Messages": _list(avg_messages),
            "Total Tool Calls": _list(total_tool_calls),
            "Avg Tool Calls": _list(avg_tool_calls),
            "Avg LLM Calls": _list(avg_llm_calls),
            "Final Answer Found Rate": _list(final_answer_rate),
            "Total Errors": _list(total_errors),
            "Avg Errors": _list(avg_errors),
            "Messages/Success": [_messages_per_success(i) for i in range(num_instances)],
            "LLM Calls/Success": [_llm_calls_per_success(i) for i in range(num_instances)],
            "Successes per 1K Tokens": [_successes_per_1k_tokens(i) for i in range(num_instances)],
            "Recovery Rate After Error": [_recovery_rate(i) for i in range(num_instances)],
            "Estimated Total Cost (USD)": _list(estimated_total_cost),
            "Cost/Success (USD)": [_cost_per_success(i) for i in range(num_instances)],
            "Tokens/Success": [_tokens_per_success(i) for i in range(num_instances)],
            "Composite Agentic Capability Index": [_composite_agentic_capability_index(i) for i in range(num_instances)],
        },
        index=[f"Trial {i}" for i in range(num_instances)],
    )
    print(tb.tabulate(trial_df, headers="keys", tablefmt="simple"))

    # Cross-trial aggregates
    avg_at_least_one = df[score_cols].any(axis=1).mean(skipna=True)
    avg_all = df[score_cols].all(axis=1).mean(skipna=True)
    agg_df = pd.DataFrame(
        {
            "At Least One Success": [avg_at_least_one],
            "All Successes": [avg_all],
        },
        index=["Trial Aggregated"],
    )
    print(tb.tabulate(agg_df, headers="keys", tablefmt="simple"))

    sys.stderr.write("\n" + warning + "\n\n")

