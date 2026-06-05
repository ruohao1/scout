# JobSpy RAG Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an LLM-callable `fetch_job_offers` tool that uses JobSpy to fetch fresh job offers, persist them, index them into RAG, and return searchable results.

**Architecture:** Reuse the existing provider seam in `services.job_providers`: add a JobSpy client and adapter, then call existing `import_jobs(..., should_index=True)`. Register a new chat tool in `services.chat_orchestrator` that imports fresh offers, records the provider run, and searches the updated RAG corpus for the LLM response.

**Tech Stack:** Python 3.13, FastAPI schemas, LangGraph chat workflow, JobSpy (`python-jobspy`), PostgreSQL/pgvector, existing Scout RAG embeddings and indexing.

---

## File Structure

- Modify `packages/services/pyproject.toml` to add `python-jobspy`.
- Modify `packages/services/src/services/job_providers.py` to add `JobSpyJobProviderClient`, `JobSpyJobProviderAdapter`, and normalization helpers.
- Modify `packages/services/src/services/__init__.py` to export the JobSpy provider classes.
- Modify `packages/services/src/services/chat_orchestrator.py` to expose and execute `fetch_job_offers`.
- Modify `apps/api/schemas.py` so `ChatResponse.tool` accepts `fetch_job_offers`.
- Run `uv sync` to update lock data.
- Run `uv run python -m compileall main.py apps packages`.

### Task 1: Add JobSpy Dependency

**Files:**
- Modify: `packages/services/pyproject.toml`

- [ ] **Step 1: Add dependency**

Add `python-jobspy>=1.1.82` to the `dependencies` list in `packages/services/pyproject.toml`.

- [ ] **Step 2: Sync dependencies**

Run: `uv sync`

Expected: dependencies resolve and `uv.lock` updates.

### Task 2: Add JobSpy Provider Classes

**Files:**
- Modify: `packages/services/src/services/job_providers.py`
- Modify: `packages/services/src/services/__init__.py`

- [ ] **Step 1: Implement `JobSpyJobProviderClient`**

Add a client with constructor args for `site_name`, `search_term`, `location`, `distance`, `job_type`, `is_remote`, `hours_old`, `country_indeed`, and `verbose`. Its `fetch_jobs(count=...)` calls `jobspy.scrape_jobs(...)` and returns dataframe records.

- [ ] **Step 2: Implement `JobSpyJobProviderAdapter`**

Normalize JobSpy rows into Scout fields. Required behavior:

- Reject rows without `title`.
- Use `description` when present; otherwise create a small description from title/company/location.
- Store `source="jobspy"`.
- Store URL from `job_url`.
- Format location from `city`, `state`, `country`, or fallback `location`.
- Format salary from `interval`, `min_amount`, `max_amount`, and `currency`.
- Infer remote policy from `is_remote`.
- Preserve the full raw row.

- [ ] **Step 3: Export classes**

Export `JobSpyJobProviderClient` and `JobSpyJobProviderAdapter` from `services.__init__`.

### Task 3: Add LLM Tool Execution

**Files:**
- Modify: `packages/services/src/services/chat_orchestrator.py`
- Modify: `apps/api/schemas.py`

- [ ] **Step 1: Add imports**

Import `ProviderImportRunRepository`, `JobSpyJobProviderAdapter`, `JobSpyJobProviderClient`, and `import_jobs` into `chat_orchestrator.py`.

- [ ] **Step 2: Add tool definition**

Add a `fetch_job_offers` tool to `_TOOLS` with parameters `search_term`, `location`, `sites`, `count`, `hours_old`, `is_remote`, `job_type`, `country_indeed`, and `limit`.

- [ ] **Step 3: Add execution branch**

Route `fetch_job_offers` in `_execute_tool(...)` to a new `_fetch_job_offers_tool(...)`.

- [ ] **Step 4: Implement tool body**

The tool should bound count to 25, default sites to `['indeed']`, import/index via JobSpy, record provider import runs, then call `search_jobs(...)` and return `jobs`, `created`, `skipped`, `indexed`, and `job_ids`.

- [ ] **Step 5: Update result plumbing**

Include `fetch_job_offers` in `_chat_result(...)` as a job-returning tool, `_tool_summary(...)`, `_public_args(...)`, and `apps/api/schemas.py` tool literals.

### Task 4: Verify

**Files:**
- Read/verify: modified files above

- [ ] **Step 1: Compile check**

Run: `uv run python -m compileall main.py apps packages`

Expected: command exits 0.

- [ ] **Step 2: Avoid real scraping during verification**

Do not call JobSpy against live job boards as routine verification because results depend on external networks and may trigger rate limits.

## Self-Review

- Spec coverage: the plan covers dependency, provider client/adapter, LLM tool registration, RAG indexing, import-run recording, API schema update, and safe verification.
- Placeholder scan: no placeholders remain.
- Type consistency: provider names and tool names are consistent across the planned files.
