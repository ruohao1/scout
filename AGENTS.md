# AGENTS.md

## Scope
- Python 3.13 project; `.python-version` and all package `pyproject.toml` files require `>=3.13`.
- Root `pyproject.toml` is a `uv` workspace for `packages/db`, `packages/providers`, `packages/rag`, and `packages/services`; run Python commands from the repo root with `uv` so workspace imports resolve.
- Python packages use `src/` layout; runtime entrypoints are the CLI in `main.py`, the FastAPI app in `apps/api/main.py` (`app = create_app()`), and the Vite/React web app in `apps/web`.

## Commands
- Sync dependencies with `uv sync`; root `pyproject.toml` wires workspace packages as workspace sources.
- Run the CLI with `uv run python main.py`; schema setup is `uv run python main.py db setup`.
- Run the API with `uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload`.
- Web commands run from `apps/web`: `pnpm install`, `pnpm run dev`, `pnpm run build`, `pnpm run preview`.
- Web Docker builds use `apps/web/pnpm-lock.yaml` with `pnpm install --frozen-lockfile`; do not regenerate or commit `package-lock.json`.
- Ask Scout for latest/live/current jobs to import and index JobSpy results; editable JobSpy sites/default count live in `/settings` and `GET/PUT /settings/runtime`.
- Import and index Adzuna jobs with `ADZUNA_APP_ID=... ADZUNA_APP_KEY=... SCOUT_EMBEDDINGS=hash uv run python main.py jobs import-adzuna --country gb --what "python developer" --where "London" --count 10`; use `--no-index` to skip indexing.
- The API equivalent is `POST /providers/adzuna/import`; `GET /jobs` supports `source` and `indexed` query filters and returns `indexed_chunks`/`is_indexed`; `GET /providers/import-runs` lists persisted provider import runs.
- OpenAI OAuth login is `uv run python main.py auth openai login --no-browser`; omit `--no-browser` only when opening a browser is intended.
- No repo-level test, lint, typecheck, formatter, codegen, or CI config exists; do not assume `pytest`, `ruff`, `mypy`, pre-commit, or root npm scripts until they are added.

## Safe Checks
- Python syntax/import check: `uv run python -m compileall main.py apps packages`.
- Compose config check: `docker compose config --services`.
- Web production build: run `pnpm run build` from `apps/web`.
- DB setup check requires Postgres first: `docker compose up -d postgres` then `uv run python main.py db setup`.

## Database
- `docker-compose.yml` starts Postgres on `127.0.0.1:5432` with `pgvector/pgvector:pg17`; it also defines Redis, but current Python code does not import Redis.
- Default `DATABASE_URL` is `postgresql://scout:scout@127.0.0.1:5432/scout`.
- There is no migration framework; `db.schema.setup_database()` creates tables/extensions/indexes idempotently.
- Provider import run history lives in `provider_import_runs`; schema changes must go through `db.schema.setup_database()` because there is no migration framework.
- Current job search/ranking uses `job_chunks.embedding vector(1536)` through `db.job_chunks` and `db.search`; `db.pgvector.PgVectorChunkStore` is a generic store, not the active job-search path.
- Candidate/user knowledge is separate from job-specific target profiles; new ranking/chat code should pass `target_profile_id` rather than legacy `profile_id`.
- Candidate evidence embeddings live in `candidate_evidence_chunks`; reindex candidate evidence after changing `SCOUT_EMBEDDINGS`, embedding model, or dimensions.
- Legacy `user_profiles` data can be migrated with `uv run python main.py candidate migrate-profile` or `uv run python main.py candidate migrate-profile --profile-id ...`.

## Embeddings And Chat
- Retrieval embeddings live in `rag.embeddings`; local Python defaults to `SCOUT_EMBEDDINGS=gemini`, while the Compose API defaults to `SCOUT_EMBEDDINGS=hash`.
- `SCOUT_EMBEDDINGS=hash` is deterministic local/offline, `SCOUT_EMBEDDINGS=gemini` needs `GEMINI_API_KEY`, and `SCOUT_EMBEDDINGS=openai` uses `OPENAI_API_KEY` with `text-embedding-3-small` by default.
- Keep `SCOUT_EMBEDDING_DIMENSIONS`, the embedding provider output, and the `job_chunks.embedding` schema/indexed data aligned; re-index jobs after changing provider, model, or dimensions.
- Chat/reasoning, profile extraction, and explanations use `providers.openai_auth.OpenAIAuthProvider`, not `OPENAI_API_KEY`; this is separate from retrieval embeddings.
- The LangGraph chat workflow can call JobSpy through `fetch_job_offers`; this imports and indexes live jobs, records `provider_import_runs` with provider `jobspy`, and may hit external job-board/network behavior.
- `SCOUT_JOBSPY_SITES` defaults JobSpy sites before persisted settings exist; supported values are `indeed`, `linkedin`, `glassdoor`, `google`, `zip_recruiter`, `bayt`, `bdjobs`, and `naukri`.
- OpenAI OAuth tokens default to `.auth/openai_auth.json` (ignored by git); set `SCOUT_AUTH_DIR` to keep credentials outside the repo.
- `OpenAICodexOAuth.login_browser()` starts a localhost callback on port `1455` and may open a browser; do not run OAuth login as routine verification.
- `OpenAIAuthProvider.generate()` calls `https://chatgpt.com/backend-api/codex/responses`; tests should fake OAuth/token storage and HTTP.

## Boundaries
- Shared request/response dataclasses live in `providers.types`.
- OpenAI Responses API shape conversion lives in `providers.openai_responses`.
- Provider HTTP and OAuth implementation lives under `providers.openai_auth`.
- RAG dataclasses, chunking, embedding/store protocols, and retriever orchestration live under `rag`.
- Cross-package orchestration lives under `services`; keep `rag` pure and keep SQL inside `db`.
- Deterministic job skill extraction lives in `services.job_skills` and enriches imported/manual jobs before persistence.
- FastAPI routes are thin adapters in `apps/api/routes`; database-backed operations go through repositories in `db` and orchestration functions in `services`.
- `apps/web` calls `/chat` through `VITE_API_BASE_URL` (dev default `http://127.0.0.1:8000`; Docker build default `/api`, proxied by nginx to the API service).
