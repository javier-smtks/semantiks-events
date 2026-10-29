"""The LangChain layer: a deepagents planner with two tools.

The planner (default `gpt-6.1-sol`, override with `AGENT_MODEL`) picks
between:
  - `fetch_url`     — plain HTTP GET for factual questions with a known URL.
  - `drive_computer`— drives the whole desktop via gpt-6.1-sol + trycua/cua.

The `drive_computer` tool wraps our existing `Agent` from `agent.py` as a
long-lived singleton so a single DesktopDriver + one macOS permission grant
is shared across every call in the session.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Optional

import httpx
from deepagents import create_deep_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from .agent import Agent

PLANNER_MODEL = os.environ.get("AGENT_MODEL", "gpt-6.1-sol")

INSTRUCTIONS = """You are a Semantiks assistant that helps the user by using
tools. Reply in the user's language. After the tool returns, respond in one
or two sentences.

TOOLS YOU MAY USE. Do not use any other tool that appears in your tool list
(no ls, read_file, write_file, edit_file, glob, grep, execute, task — they
are not part of this demo):

1. `drive_computer(task)` — takes over the user's actual desktop via
   `gpt-6.1-sol` + the trycua/cua Driver. Clicks, types, opens apps. Use
   this when the user asks anything that implies real GUI interaction:
     * naming an app ("Mail", "Slack", "Finder", "Spotify", "VS Code")
     * verbs like "abre", "entra", "haz clic", "escribe", "manda", "open",
       "click", "type", "send"
   Keep the task description short and direct. On macOS, apps launch via
   Spotlight (Cmd+Space → type name → Enter). Say what to click/type AND
   what to report back.

2. `fetch_url(url)` — plain HTTP GET. Use only for a factual question the
   user asked with a known URL that answers it in raw HTML. If the request
   mentions a browser or a GUI, use `drive_computer` instead.
"""


# ---- Agent singleton -------------------------------------------------------

_agent: Optional[Agent] = None
_action_hook: Callable[[dict], None] = lambda _a: None
_error_hook: Callable[[dict, BaseException], None] = lambda _a, _e: None


def set_hooks(
    *,
    on_action: Callable[[dict], None],
    on_action_error: Callable[[dict, BaseException], None],
) -> None:
    """Wire terminal-UI callbacks before any `drive_computer` call runs."""
    global _action_hook, _error_hook
    _action_hook = on_action
    _error_hook = on_action_error


async def _get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent(on_action=_action_hook, on_action_error=_error_hook)
        await _agent.start()
    return _agent


async def shutdown_agent() -> None:
    global _agent
    if _agent is not None:
        await _agent.shutdown()
        _agent = None


def session_dir() -> Optional[str]:
    return str(_agent.session_dir) if _agent is not None else None


# ---- Tools -----------------------------------------------------------------


@tool
async def drive_computer(task: str) -> str:
    """Take over the user's computer via gpt-6.1-sol + the trycua/cua Driver
    and perform a GUI task. Prefer this whenever the user asks anything that
    requires real desktop interaction (opening apps, clicking buttons,
    typing in native fields, sending messages in Slack/Mail/etc.).

    Args:
        task: A short, direct instruction describing what to do and what to
            report back (one or two sentences).
    """
    agent = await _get_agent()
    return await agent.run_turn(task)


@tool
def fetch_url(url: str) -> str:
    """Fetch a URL over HTTP and return the response body as text (first
    10,000 chars). Use for factual questions when the answer lives in the
    raw HTML of a specific page.
    """
    with httpx.Client(follow_redirects=True, timeout=20.0) as client:
        resp = client.get(url, headers={"User-Agent": "semantiks-cua/0.1"})
        resp.raise_for_status()
        text = resp.text
    if len(text) > 10_000:
        return text[:10_000] + f"\n\n...[truncated {len(text) - 10_000} chars]"
    return text


# ---- Graph -----------------------------------------------------------------


def build_graph() -> Any:
    """Build the deepagents graph. Called once at CLI startup."""
    model = ChatOpenAI(model=PLANNER_MODEL)
    return create_deep_agent(
        model=model,
        tools=[fetch_url, drive_computer],
        system_prompt=INSTRUCTIONS,
    )


async def run_turn(
    graph: Any,
    history: list[dict],
    user_prompt: str,
    *,
    on_tool_start: Optional[Callable[[str, str], None]] = None,
) -> str:
    """Stream one planner turn and return the assistant's final text."""
    history.append({"role": "user", "content": user_prompt})

    final_text = ""
    final_messages: Optional[list] = None

    async for event in graph.astream_events({"messages": list(history)}, version="v2"):
        kind = event["event"]
        name = event.get("name", "")
        data = event.get("data", {})

        if kind == "on_tool_start" and on_tool_start:
            on_tool_start(name, _shorten(data.get("input")))
        elif kind == "on_chat_model_stream":
            text = _extract_chunk_text(data.get("chunk"))
            if text:
                final_text += text
        elif kind == "on_chain_end":
            out = data.get("output")
            if isinstance(out, dict) and isinstance(out.get("messages"), list):
                final_messages = out["messages"]

    # Fallback — if streaming produced no tokens, use the final message's text.
    if not final_text and final_messages:
        tail = final_messages[-1]
        text = _flatten_text(getattr(tail, "content", None))
        if text:
            final_text = text

    history.clear()
    history.extend(_slim(final_messages or []))
    return final_text or "[no reply]"


# ---- Helpers --------------------------------------------------------------


def _extract_chunk_text(chunk: Any) -> str:
    if chunk is None:
        return ""
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in {"text", "output_text"}:
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _flatten_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in {"text", "output_text"}:
                parts.append(block.get("text", ""))
        return "".join(parts).strip()
    return ""


def _slim(final_messages: list) -> list[dict]:
    """Keep only user prompts + text-only assistant replies for cross-turn
    history. Prevents the planner's PatchToolCallsMiddleware from crashing on
    orphaned tool messages whose tool_call_id we no longer have."""
    out: list[dict] = []
    for m in final_messages:
        role = getattr(m, "type", None) if not isinstance(m, dict) else m.get("role")
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        if role == "user" and isinstance(content, str) and content.strip():
            out.append({"role": "user", "content": content})
        elif role == "assistant":
            text = _flatten_text(content)
            if text:
                out.append({"role": "assistant", "content": text})
    return out


def _shorten(value: Any, limit: int = 120) -> str:
    s = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return s if len(s) <= limit else s[: limit - 1] + "…"
