# Mock Job Provider Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add mock job-provider API responses, adapters, and a CLI import command for seeding Scout with normalized mock jobs.

**Architecture:** Split provider clients from adapters. A mock client returns raw provider-shaped payloads from static fixtures or dynamic generation, an adapter normalizes raw payloads into `JobRepository.create()` dicts, and an import service coordinates optional indexing.

**Tech Stack:** Python 3.13, uv workspace packages, argparse CLI, psycopg-backed repositories.

---

### Task 1: Mock Provider Layer

**Files:**
- Create: `packages/services/src/services/job_providers.py`

- [ ] Define provider protocols, mock fixture/dynamic client, adapter, and `import_jobs()` service.
- [ ] Keep raw provider payloads in `raw_payload` and set normalized `source` to the provider name.
- [ ] Support optional indexing through existing `services.job_indexing.index_job()`.

### Task 2: CLI Wiring

**Files:**
- Modify: `main.py`

- [ ] Add `jobs import-mock --count N --fixture PATH --index --source SOURCE`.
- [ ] Print imported job IDs and count.
- [ ] Return non-zero with clear stderr on fixture, DB, or indexing failures.

### Task 3: Verification

**Commands:**
- `uv run python main.py jobs import-mock --help`
- `uv run python -m compileall main.py packages/services/src/services/job_providers.py`
- Optional with local Postgres: `uv run python main.py db setup && uv run python main.py jobs import-mock --count 3`
