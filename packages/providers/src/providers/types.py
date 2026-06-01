from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ProviderName = Literal["openai_auth"]


@dataclass(frozen=True)
class ProviderMessage:
    role: str
    content: str


@dataclass(frozen=True)
class GenerateRequest:
    model: str
    messages: list[ProviderMessage]
    instructions: str = "You are a helpful coding assistant. Use available tools when they help answer the user."
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    previous_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class GenerateResponse:
    provider: ProviderName
    model: str
    text: str
    raw: dict[str, Any]
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
