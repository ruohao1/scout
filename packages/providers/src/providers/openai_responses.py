from __future__ import annotations

from typing import Any

from providers.types import ProviderMessage


def messages_to_input(messages: list[ProviderMessage]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for message in messages:
        role = _response_role(message.role)
        content_type = "output_text" if role == "assistant" else "input_text"
        items.append(
            {
                "type": "message",
                "role": role,
                "content": [{"type": content_type, "text": message.content}],
            }
        )
    return items


def tool_calls_to_input(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return tool_calls


def tool_results_to_input(tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return tool_results


def extract_text(raw: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in raw.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "".join(parts)


def extract_tool_calls(raw: dict[str, Any]) -> list[dict[str, Any]]:
    tool_calls: list[dict[str, Any]] = []
    for item in raw.get("output", []):
        if isinstance(item, dict) and item.get("type") in {"function_call", "tool_call"}:
            tool_calls.append(item)
    return tool_calls


def _response_role(role: str) -> str:
    if role in {"human", "user"}:
        return "user"
    if role in {"ai", "assistant"}:
        return "assistant"
    if role in {"system", "developer"}:
        return role
    if role == "tool":
        return "user"
    return "user"
