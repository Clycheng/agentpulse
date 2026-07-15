"""Function-calling loop: LLM decides tools → execute → feed results → repeat.

Drives the agent through a decision loop:
1. Send user message + system prompt + tools to LLM
2. If LLM returns tool_calls → execute them → feed results back → go to 1
3. If LLM returns text → collect as streaming chunks → yield to caller

Max 5 tool-calling rounds per user message to prevent infinite loops.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from app.core.database import Database, Row
from app.schemas.run import LlmChatMessage
from app.tools.registry import (
    TOOLS,
    ToolCall,
    ToolResult,
    execute_tool,
    system_prompt_for_operator,
)

MAX_TOOL_ROUNDS = 5


async def run_function_loop(
    *,
    conn: Database,
    workspace_id: str,
    workspace_name: str,
    agent: Row,
    history: list[LlmChatMessage],
    user_message_content: str,
    deepseek_client: Any,  # DeepSeekChatClient
) -> AsyncGenerator[dict, None]:
    """Run the function-calling loop, yielding {type: chunk|tool_call|tool_result} events.

    The caller is responsible for collecting the chunks into a final agent message
    and persisting it.

    Yields:
        {"type": "chunk", "content": str}  — text chunks from the final LLM reply
        {"type": "tool_call", "name": str, "args": dict}  — tool being invoked
        {"type": "tool_result", "name": str, "result": str}  — tool result
    """
    messages: list[dict[str, Any]] = []

    # System prompt
    messages.append({
        "role": "system",
        "content": system_prompt_for_operator(
            workspace_name,
            agent["name"],
            agent.get("role", ""),
        ),
    })

    # History (skip system messages, keep user/assistant)
    for msg in history[-16:]:
        role = msg.role
        if role == "user":
            messages.append({"role": "user", "content": msg.content})
        else:
            messages.append({"role": "assistant", "content": msg.content})

    # Add the latest user message if not already included
    if not messages or messages[-1].get("role") != "user" or messages[-1].get("content") != user_message_content:
        messages.append({"role": "user", "content": user_message_content})

    for round_num in range(MAX_TOOL_ROUNDS):
        # Call DeepSeek with tools
        try:
            response = await _call_llm_with_tools(deepseek_client, messages)
        except Exception:
            # If function calling fails (e.g. model doesn't support it),
            # fall back to a normal completion
            break

        # Check if the response contains tool_calls
        tool_calls = _extract_tool_calls(response)
        if not tool_calls:
            # No more tools needed — extract text reply and yield it
            text = _extract_text(response)
            if text:
                yield {"type": "chunk", "content": text}
            return

        # Process tool calls
        # Add the assistant's tool_calls to messages
        messages.append(response)

        for tc in tool_calls:
            yield {
                "type": "tool_call",
                "name": tc.name,
                "args": tc.arguments,
            }

        # Execute all tool calls and collect results
        tool_results: list[ToolResult] = []
        for tc in tool_calls:
            result = await execute_tool(conn, workspace_id, agent, tc)
            tool_results.append(result)
            yield {
                "type": "tool_result",
                "name": result.name,
                "result": result.content,
            }

        # Persist tool execution results to database
        conn.commit()

        # Feed tool results back as tool role messages
        for tr in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": tr.tool_call_id,
                "content": tr.content,
            })

    # Max rounds reached — do one final non-tool completion for a summary
    try:
        final_text = await _call_llm_text_only(deepseek_client, messages)
        if final_text:
            yield {"type": "chunk", "content": final_text}
    except Exception:
        pass


async def _call_llm_with_tools(
    client: Any,
    messages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Call the LLM with tools available. Returns the raw API response message dict."""
    payload = {
        "model": client.model,
        "messages": messages,
        "tools": TOOLS,
        "stream": False,
    }
    # Don't force a tool call — let the model decide

    import httpx
    async with httpx.AsyncClient(timeout=client.timeout_seconds, trust_env=False) as http:
        resp = await http.post(
            f"{client.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {client.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if resp.status_code >= 400:
        body = await resp.aread()
        raise RuntimeError(f"LLM tool call failed: {resp.status_code} {body[:500]}")
    data = resp.json()
    choice = data.get("choices", [{}])[0]
    return choice.get("message", {})


async def _call_llm_text_only(
    client: Any,
    messages: list[dict[str, Any]],
) -> str:
    """Call the LLM without tools for a final text summary."""
    payload = {
        "model": client.model,
        "messages": messages,
        "stream": False,
    }
    import httpx
    async with httpx.AsyncClient(timeout=client.timeout_seconds, trust_env=False) as http:
        resp = await http.post(
            f"{client.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {client.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if resp.status_code >= 400:
        return ""
    data = resp.json()
    choice = data.get("choices", [{}])[0]
    return (choice.get("message", {}).get("content") or "").strip()


def _extract_tool_calls(message: dict[str, Any]) -> list[ToolCall]:
    """Extract parsed tool calls from an LLM response message."""
    raw = message.get("tool_calls") or []
    result: list[ToolCall] = []
    for tc in raw:
        fid = str(tc.get("id", ""))
        func = tc.get("function", {})
        name = str(func.get("name", ""))
        raw_args = func.get("arguments", "{}")
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except (json.JSONDecodeError, TypeError):
            args = {}
        if name and fid:
            result.append(ToolCall(id=fid, name=name, arguments=args))
    return result


def _extract_text(message: dict[str, Any]) -> str:
    """Extract text content from an LLM response message."""
    return (message.get("content") or "").strip()
