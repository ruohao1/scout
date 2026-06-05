# LangGraph Chat Streaming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/chat/stream` use LangGraph native streaming instead of callback-driven streaming around `workflow.invoke()`.

**Architecture:** Keep Server-Sent Events as the browser transport and preserve the frontend event schema. Move backend stream production to `CompiledStateGraph.stream(..., stream_mode=["updates", "custom"], version="v2")`, with graph nodes and orchestrator code emitting curated app events through LangGraph `get_stream_writer()`.

**Tech Stack:** Python 3.13, FastAPI `StreamingResponse`, LangGraph 1.x, existing React SSE reader.

---

### Task 1: Add LangGraph Stream API

**Files:**
- Modify: `packages/services/src/services/job_workflow_graph.py`
- Modify: `packages/services/src/services/chat_orchestrator.py`
- Modify: `apps/api/routes/chat.py`

- [ ] Add a stream helper in `job_workflow_graph.py` that calls `workflow.stream(input_state, stream_mode=["updates", "custom"], version="v2")` and yields existing app events.
- [ ] Convert graph `_emit(...)` to write with `langgraph.config.get_stream_writer()` instead of an injected callback.
- [ ] Convert orchestrator progress emission to the same stream-writer helper so planner/tool events still appear while `plan_and_run` executes.
- [ ] Keep non-streaming `/chat` on `workflow.invoke(...)` for the simple response path.
- [ ] Update `/chat/stream` to iterate the service stream directly and serialize each event as `data: <json>\n\n`.

### Task 2: Verify Behavior

**Files:**
- Verify: `packages/services/src/services/job_workflow_graph.py`
- Verify: `apps/api/routes/chat.py`

- [ ] Run `uv run python -m compileall main.py apps packages` from the repo root.
- [ ] Confirm the frontend contract is unchanged: events are still `step_*`, `tool_*`, `done`, or `error`.
- [ ] Review `git diff` to ensure no frontend changes were needed.
