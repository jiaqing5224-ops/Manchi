"""LLM client backed by local settings.json configuration."""

from typing import Iterator, Optional
import httpx
from openai import OpenAI
from sqlalchemy.orm import Session

from app.services.settings_store import get_llm_settings

SYSTEM_PROMPT = (
    "You are Manchi, a helpful desktop AI assistant. "
    "You help users manage emails, tasks, and automate workflows. "
    "Respond concisely and accurately in Chinese. "
    "When asked to provide data in JSON format, respond ONLY with valid JSON. "
    "When the user asks you to create tasks, call create_task for each task "
    "individually, then stop — do not repeat or loop. "
    "When the user asks you to create an automation rule, call create_rule once. "
    "After you have completed all tool calls needed to fulfill the user's request, "
    "respond with a brief summary text and do NOT call any more tools. "
    "When the user message starts with '[AI 协助请求]', this is a task-assist "
    "consultation: analyze the task and its source context, give concrete advice "
    "on how to proceed, and if any available tool (scan_mails, list_mails, "
    "list_tasks, create_task, analyze_mail, generate_meeting_report, create_rule, "
    "send_mail) "
    "can complete the task for the user, tell them Manchi can do it and wait for "
    "their confirmation. Do NOT call any tool in this first reply — only after "
    "the user explicitly confirms in a follow-up message may you call tools."
)


def get_client() -> OpenAI:
    """Create an OpenAI-compatible client from settings.json."""
    cfg = _require_llm_settings()
    if cfg["api_format"] != "openai_chat_completions":
        raise RuntimeError("当前 LLM 配置不是 OpenAI Chat Completions 格式")
    http_client = httpx.Client(timeout=cfg["timeout_seconds"])
    return OpenAI(
        api_key=cfg["api_key"],
        base_url=_normalize_openai_base_url(cfg["endpoint"]),
        http_client=http_client,
    )


def get_model() -> str:
    """Return the model name from settings.json."""
    return _require_llm_settings()["model"]


def build_messages(
    history: list[dict],
    user_input: str,
    system_prompt: Optional[str] = None,
) -> list[dict]:
    """Build chat completion messages from history + new input."""
    messages = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT}]

    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_input})
    return messages


def chat_stream(
    history: list[dict],
    user_input: str,
    temperature: float = 0.0,
    max_tokens: int = 3000,
) -> Iterator[str]:
    """Stream a chat completion, yielding text chunks."""
    cfg = _require_llm_settings()
    messages = build_messages(history, user_input)

    if cfg["api_format"] == "anthropic_messages":
        yield _anthropic_chat_complete(messages, cfg, temperature, max_tokens)
        return

    client = get_client()

    stream = client.chat.completions.create(
        model=cfg["model"],
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices and len(chunk.choices) > 0:
            delta = chunk.choices[0].delta
            content = delta.content or ""
            if content:
                yield content


def chat_complete(
    history: list[dict],
    user_input: str,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str:
    """Non-streaming chat completion, returns full text."""
    cfg = _require_llm_settings()
    messages = build_messages(history, user_input)

    if cfg["api_format"] == "anthropic_messages":
        return _anthropic_chat_complete(messages, cfg, temperature, max_tokens)

    client = get_client()

    response = client.chat.completions.create(
        model=cfg["model"],
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )

    return response.choices[0].message.content or ""


def chat_stream_with_tools(
    history: list[dict],
    user_input: str,
    db: Session,
    temperature: float = 0.3,
    max_iterations: int = 20,
) -> Iterator[str]:
    """Stream a chat with a tool-calling loop.

    Yields JSON event strings for the SSE layer:
      {"text": "..."}                  — assistant text chunk
      {"tool_call": {"id","name","args"}}    — tool invocation start
      {"tool_result": {"id","name","result"}} — tool execution result
    Terminates when the model returns no tool_calls, max_iterations is hit,
    or the same tool is called more than 10 times.
    """
    import json
    from app.services.llm.tools import TOOL_SCHEMAS, execute_tool

    cfg = _require_llm_settings()
    if cfg["api_format"] == "anthropic_messages":
        text = chat_complete(history, user_input, temperature=temperature)
        if text:
            yield json.dumps({"text": text}, ensure_ascii=False)
        return

    client = get_client()
    messages = build_messages(history, user_input)
    tool_call_counts: dict[str, int] = {}

    for _ in range(max_iterations):
        stream = client.chat.completions.create(
            model=cfg["model"],
            messages=messages,
            tools=TOOL_SCHEMAS,
            temperature=temperature,
            stream=True,
        )
        content_buf = ""
        tool_calls_acc: list[dict] = []

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content_buf += delta.content
                yield json.dumps({"text": delta.content}, ensure_ascii=False)
            if delta.tool_calls:
                _accumulate_tool_calls(tool_calls_acc, delta.tool_calls)

        if not tool_calls_acc:
            return

        assistant_msg = {
            "role": "assistant",
            "content": content_buf or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                }
                for tc in tool_calls_acc
            ],
        }
        messages.append(assistant_msg)

        for tc in tool_calls_acc:
            call_id = tc["id"]
            fn_name = tc["function"]["name"]
            fn_args_str = tc["function"]["arguments"]

            # Anti-loop: limit repeated calls to the same tool
            tool_call_counts[fn_name] = tool_call_counts.get(fn_name, 0) + 1
            if tool_call_counts[fn_name] > 10:
                yield json.dumps(
                    {"text": f"[工具 {fn_name} 调用次数已达上限，已停止]"},
                    ensure_ascii=False,
                )
                return

            yield json.dumps(
                {"tool_call": {"id": call_id, "name": fn_name, "args": fn_args_str}},
                ensure_ascii=False,
            )
            try:
                args = json.loads(fn_args_str) if fn_args_str else {}
            except json.JSONDecodeError:
                args = {}
            result = execute_tool(fn_name, args, db)
            yield json.dumps(
                {"tool_result": {"id": call_id, "name": fn_name, "result": result[:500]}},
                ensure_ascii=False,
            )
            messages.append(
                {"role": "tool", "tool_call_id": call_id, "content": result}
            )

    yield json.dumps({"text": "[已达到工具调用上限]"}, ensure_ascii=False)


def _accumulate_tool_calls(acc: list[dict], deltas: list) -> None:
    """Accumulate streamed tool_call deltas by their index."""
    for d in deltas:
        idx = d.index if d.index is not None else 0
        while len(acc) <= idx:
            acc.append(
                {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
            )
        if d.id:
            acc[idx]["id"] = d.id
        if d.function:
            if d.function.name:
                acc[idx]["function"]["name"] += d.function.name
            if d.function.arguments:
                acc[idx]["function"]["arguments"] += d.function.arguments


def test_llm_connection() -> dict:
    """Run a short completion against the configured LLM service."""
    cfg = _require_llm_settings()
    result = chat_complete([], "请只回复 OK", temperature=0.0, max_tokens=32)
    return {
        "ok": True,
        "api_format": cfg["api_format"],
        "model": cfg["model"],
        "message": "LLM 连接测试成功",
        "response_preview": result[:200],
    }


def _require_llm_settings() -> dict:
    cfg = get_llm_settings()
    missing = []
    if not cfg["endpoint"]:
        missing.append("接口地址")
    if not cfg["api_key"]:
        missing.append("API Key")
    if not cfg["model"]:
        missing.append("模型")
    if missing:
        raise RuntimeError(f"请先在设置页配置 LLM：{', '.join(missing)}")
    return cfg


def _normalize_openai_base_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    suffix = "/chat/completions"
    if endpoint.endswith(suffix):
        endpoint = endpoint[: -len(suffix)]
    return endpoint


def _anthropic_messages_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/messages"):
        return endpoint
    return f"{endpoint}/messages"


def _anthropic_chat_complete(
    messages: list[dict],
    cfg: dict,
    temperature: float,
    max_tokens: int,
) -> str:
    system_parts: list[str] = []
    anthropic_messages: list[dict[str, str]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content") or ""
        if role == "system":
            system_parts.append(str(content))
            continue
        if role not in {"user", "assistant"}:
            role = "user"
        anthropic_messages.append({"role": role, "content": str(content)})

    body: dict[str, object] = {
        "model": cfg["model"],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": anthropic_messages,
    }
    if system_parts:
        body["system"] = "\n\n".join(system_parts)

    headers = {
        "content-type": "application/json",
        "x-api-key": cfg["api_key"],
        "anthropic-version": "2023-06-01",
    }

    with httpx.Client(timeout=cfg["timeout_seconds"]) as client:
        response = client.post(_anthropic_messages_url(cfg["endpoint"]), headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

    content = data.get("content", [])
    if isinstance(content, list):
        return "".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return str(content or "")
