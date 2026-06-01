from __future__ import annotations

import json
from typing import Any

import requests

from providers.errors import ProviderHTTPError
from providers.openai_responses import extract_text, extract_tool_calls, messages_to_input, tool_calls_to_input, tool_results_to_input
from providers.types import GenerateRequest, GenerateResponse, ProviderName

from .oauth import OpenAICodexOAuth


class OpenAIAuthProvider:
    name: ProviderName = "openai_auth"

    def __init__(
        self,
        *,
        oauth: OpenAICodexOAuth | None = None,
        codex_api_endpoint: str = "https://chatgpt.com/backend-api/codex/responses",
        timeout: float = 120.0,
    ) -> None:
        self.oauth = oauth or OpenAICodexOAuth()
        self.codex_api_endpoint = codex_api_endpoint
        self.timeout = timeout

    def login_browser(self, *, open_browser: bool = True) -> None:
        self.oauth.login_browser(open_browser=open_browser)

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        tokens = self.oauth.valid_tokens()
        headers = {
            "Authorization": f"Bearer {tokens.access_token}",
            "Content-Type": "application/json",
            "originator": "scout",
        }
        if tokens.account_id:
            headers["ChatGPT-Account-Id"] = tokens.account_id

        payload: dict[str, Any] = {
            "model": request.model,
            "instructions": request.instructions,
            "store": False,
            "stream": True,
            "input": messages_to_input(request.messages)
            + tool_calls_to_input(request.previous_tool_calls)
            + tool_results_to_input(request.tool_results),
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_output_tokens"] = request.max_tokens
        if request.tools:
            payload["tools"] = request.tools

        raw = self._post_stream(headers=headers, payload=payload)
        return GenerateResponse(
            provider=self.name,
            model=request.model,
            text=extract_text(raw),
            raw=raw,
            tool_calls=extract_tool_calls(raw),
        )

    def _post_stream(self, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            self.codex_api_endpoint,
            headers=headers,
            json=payload,
            timeout=self.timeout,
            stream=True,
        )
        if not response.ok:
            raise ProviderHTTPError(
                f"Request failed with HTTP {response.status_code}",
                status_code=response.status_code,
                body=response.text,
            )

        output: list[dict[str, Any]] = []
        final_response: dict[str, Any] | None = None
        for raw_line in response.iter_lines(decode_unicode=True):
            line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
            if not line or not line.startswith("data: "):
                continue
            try:
                event = json.loads(line.removeprefix("data: "))
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            if _stream_event_failed(event):
                raise ProviderHTTPError(
                    "Stream failed after HTTP 200",
                    status_code=response.status_code,
                    body=json.dumps(event),
                )
            if event.get("type") == "response.output_item.done" and isinstance(event.get("item"), dict):
                output.append(event["item"])
            if event.get("type") == "response.completed" and isinstance(event.get("response"), dict):
                final_response = event["response"]

        if final_response:
            if final_response.get("status") in {"failed", "incomplete", "cancelled"}:
                raise ProviderHTTPError(
                    "Stream completed with failure status",
                    status_code=response.status_code,
                    body=json.dumps(final_response),
                )
            if output and not final_response.get("output"):
                final_response["output"] = output
            return final_response
        return {"output": output}


def _stream_event_failed(event: dict[str, Any]) -> bool:
    event_type = event.get("type")
    if not isinstance(event_type, str):
        return False
    return event_type == "error" or event_type.endswith((".failed", ".incomplete", ".error"))
