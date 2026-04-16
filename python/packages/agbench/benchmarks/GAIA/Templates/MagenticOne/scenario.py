import asyncio
import json
import logging
import os
import re
import yaml
import warnings
from datetime import datetime
from autogen_agentchat import EVENT_LOGGER_NAME as AGENTCHAT_EVENT_LOGGER_NAME
from autogen_core import EVENT_LOGGER_NAME as CORE_EVENT_LOGGER_NAME
from autogen_ext.agents.magentic_one import MagenticOneCoderAgent
from autogen_agentchat.teams import MagenticOneGroupChat
from autogen_agentchat.ui import Console
from autogen_core.models import ModelFamily
from autogen_core.logging import LLMCallEvent
from autogen_ext.code_executors.local import LocalCommandLineCodeExecutor
from autogen_agentchat.conditions import TextMentionTermination
from autogen_core.models import ChatCompletionClient
from autogen_ext.agents.web_surfer import MultimodalWebSurfer
from autogen_ext.agents.file_surfer import FileSurfer
from autogen_agentchat.agents import CodeExecutorAgent
from autogen_agentchat.messages import TextMessage

# Suppress warnings about the requests.Session() not being closed
warnings.filterwarnings(action="ignore", message="unclosed", category=ResourceWarning)


class LLMEventLogHandler(logging.FileHandler):
    """Capture structured LLM call events into JSONL for downstream metrics."""

    def __init__(self, filename: str = "llm_events.jsonl") -> None:
        super().__init__(filename, mode="w")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if isinstance(record.msg, LLMCallEvent):
                payload = {
                    "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                    "type": "LLMCallEvent",
                    "prompt_tokens": record.msg.kwargs.get("prompt_tokens", 0),
                    "completion_tokens": record.msg.kwargs.get("completion_tokens", 0),
                }
                self.stream.write(json.dumps(payload) + "\n")
                self.flush()
        except Exception:
            self.handleError(record)

async def main() -> None:

    # Attach a structured core-event logger for per-call LLM usage tracking.
    core_event_logger = logging.getLogger(CORE_EVENT_LOGGER_NAME)
    llm_handler = LLMEventLogHandler("llm_events.jsonl")
    llm_handler.setLevel(logging.INFO)
    core_event_logger.addHandler(llm_handler)
    core_event_logger.setLevel(logging.INFO)

    # Keep a dedicated agentchat events file for future trajectory metrics.
    agentchat_event_logger = logging.getLogger(AGENTCHAT_EVENT_LOGGER_NAME)
    agentchat_handler = logging.FileHandler("agent_events.log", mode="w")
    agentchat_handler.setLevel(logging.INFO)
    agentchat_event_logger.addHandler(agentchat_handler)
    agentchat_event_logger.setLevel(logging.INFO)

    # Load model configuration and create the model client.
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    orchestrator_client = ChatCompletionClient.load_component(config["orchestrator_client"])
    coder_client = ChatCompletionClient.load_component(config["coder_client"])
    web_surfer_client = ChatCompletionClient.load_component(config["web_surfer_client"])
    file_surfer_client = ChatCompletionClient.load_component(config["file_surfer_client"])
    
    # Read the prompt
    prompt = ""
    with open("prompt.txt", "rt") as fh:
        prompt = fh.read().strip()
    filename = "__FILE_NAME__".strip()

    # Set up the team
    coder = MagenticOneCoderAgent(
        "Assistant",
        model_client = coder_client,
    )

    # Use an explicit work_dir to avoid FileNotFoundError from os.getcwd() in native agbench runs.
    _work_dir = os.path.abspath("code_workspace")
    os.makedirs(_work_dir, exist_ok=True)
    executor = CodeExecutorAgent("ComputerTerminal", code_executor=LocalCommandLineCodeExecutor(work_dir=_work_dir))

    file_surfer = FileSurfer(
        name="FileSurfer",
        model_client = file_surfer_client,
    )
                
    web_surfer = MultimodalWebSurfer(
        name="WebSurfer",
        model_client = web_surfer_client,
        downloads_folder=os.getcwd(),
        debug_dir="logs",
        to_save_screenshots=True,
    )

    # max_turns and max_stalls are tuned for 24k context window models.
    # Lower values reduce cumulative context growth across turns.
    team = MagenticOneGroupChat(
        [coder, executor, file_surfer, web_surfer],
        model_client=orchestrator_client,
        max_turns=int(os.environ.get("MAGENTIC_MAX_TURNS", "10")),
        max_stalls=int(os.environ.get("MAGENTIC_MAX_STALLS", "2")),
        final_answer_prompt= f""",
We have completed the following task:

{prompt}

The above messages contain the conversation that took place to complete the task.
Read the above conversation and output a FINAL ANSWER to the question.
To output the final answer, use the following template: FINAL ANSWER: [YOUR FINAL ANSWER]
Your FINAL ANSWER should be a number OR as few words as possible OR a comma separated list of numbers and/or strings.
ADDITIONALLY, your FINAL ANSWER MUST adhere to any formatting instructions specified in the original question (e.g., alphabetization, sequencing, units, rounding, decimal places, etc.)
If you are asked for a number, express it numerically (i.e., with digits rather than words), don't use commas, and don't include units such as $ or percent signs unless specified otherwise.
If you are asked for a string, don't use articles or abbreviations (e.g. for cities), unless specified otherwise. Don't output any final sentence punctuation such as '.', '!', or '?'.
If you are asked for a comma separated list, apply the above rules depending on whether the elements are numbers or strings.
""".strip()
    )

    # Prepare the prompt
    filename_prompt = ""
    if len(filename) > 0:
        filename_prompt = f"The question is about a file, document or image, which can be accessed by the filename '{filename}' in the current working directory."
    task = f"{prompt}\n\n{filename_prompt}"

    try:
        # Run the task
        stream = team.run_stream(task=task.strip())
        result = await Console(stream)

        # total_usage() aggregates all LLM calls made by each client.
        prompt_tokens = 0
        completion_tokens = 0
        for client in [orchestrator_client, coder_client, web_surfer_client, file_surfer_client]:
            try:
                usage = client.total_usage()
                prompt_tokens += usage.prompt_tokens
                completion_tokens += usage.completion_tokens
            except Exception:
                pass

        messages = list(result.messages) if result is not None else []
        agent_messages = len(messages)
        tool_calls = 0
        final_answer_found = False
        error_count = 0

        for message in messages:
            content = getattr(message, "content", "")
            content_str = content if isinstance(content, str) else str(content)
            if "FINAL ANSWER:" in content_str:
                final_answer_found = True
            if re.search(r"\b(error|exception|traceback|failed)\b", content_str, flags=re.IGNORECASE):
                error_count += 1
            message_type = type(message).__name__.lower()
            if "toolcall" in message_type or "functioncall" in message_type:
                tool_calls += 1

        # Prefer event-log-derived tool call counts when available.
        if os.path.isfile("agent_events.log"):
            with open("agent_events.log", "rt") as fh:
                event_log_content = fh.read()
            event_tool_calls = len(re.findall(r"ToolCallRequestEvent|ToolCallExecutionEvent", event_log_content))
            if event_tool_calls > 0:
                tool_calls = event_tool_calls

        llm_call_count = 0
        if os.path.isfile("llm_events.jsonl"):
            with open("llm_events.jsonl", "r") as fh:
                llm_call_count = sum(1 for _ in fh)

        print(f"PROMPT_TOKENS: {prompt_tokens} !#!#")
        print(f"COMPLETION_TOKENS: {completion_tokens} !#!#")
        print(f"AGENT_MESSAGES: {agent_messages} !#!#")
        print(f"TOOL_CALLS: {tool_calls} !#!#")
        print(f"FINAL_ANSWER_FOUND: {int(final_answer_found)} !#!#")
        print(f"LLM_CALL_COUNT: {llm_call_count} !#!#")
        print(f"ERROR_COUNT: {error_count} !#!#")

        # Write machine-readable metrics snapshot for downstream analysis
        metrics = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "agent_messages": agent_messages,
            "tool_calls": tool_calls,
            "final_answer_found": final_answer_found,
            "llm_call_count": llm_call_count,
            "error_count": error_count,
        }
        with open("metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)
    finally:
        core_event_logger.removeHandler(llm_handler)
        llm_handler.close()
        agentchat_event_logger.removeHandler(agentchat_handler)
        agentchat_handler.close()

if __name__ == "__main__":
    asyncio.run(main())
