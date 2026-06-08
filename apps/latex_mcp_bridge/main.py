from __future__ import annotations

import json
import os
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class ValidateCompileRequest(BaseModel):
    file_path: str = Field(description="Path relative to LATEX_SERVER_BASE_PATH")
    engine: Literal["pdflatex", "xelatex", "lualatex"] = "pdflatex"


class ValidateCompileResponse(BaseModel):
    validation: dict[str, Any]
    compile: dict[str, Any] | None = None


app = FastAPI(title="Scout LaTeX MCP Bridge")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/validate-compile", response_model=ValidateCompileResponse)
async def validate_compile(request: ValidateCompileRequest) -> dict[str, Any]:
    try:
        validation = await _call_latex_tool("validate_latex", {"file_path": request.file_path})
        if not validation.get("valid"):
            return {"validation": validation, "compile": None}
        compile_result = await _call_latex_tool(
            "compile_latex",
            {"file_path": request.file_path, "engine": request.engine},
        )
        return {"validation": validation, "compile": compile_result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LaTeX MCP call failed: {exc}") from exc


async def _call_latex_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    command = os.environ.get("LATEX_MCP_COMMAND", "mcp-latex-server")
    params = StdioServerParameters(
        command=command,
        args=_split_args(os.environ.get("LATEX_MCP_ARGS", "")),
        env={"LATEX_SERVER_BASE_PATH": os.environ.get("LATEX_SERVER_BASE_PATH", "/workspace")},
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            structured = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
            if isinstance(structured, dict):
                return structured
            content = getattr(result, "content", None) or []
            for item in content:
                text = getattr(item, "text", None)
                if text:
                    try:
                        parsed = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(parsed, dict):
                        return parsed
            return {"ok": not bool(getattr(result, "isError", False)), "content": [str(item) for item in content]}


def _split_args(value: str) -> list[str]:
    return [part for part in value.split(" ") if part]
