# AGENTS.md

## Scope
- Python 3.13 project; `.python-version` and all package `pyproject.toml` files require `>=3.13`.
- Root `pyproject.toml` is a `uv` workspace; implemented packages use `src/` layout under `packages/providers`, `packages/db`, `packages/rag`, and `packages/services`.
- Runtime entrypoints are the CLI in `main.py` and the FastAPI app in `apps/api/main.py` (`app = create_app()`).

## Commands
- Sync dependencies with `uv sync`; root `pyproject.toml` wires workspace packages as workspace sources.
- Run the CLI with `uv run python main.py`; schema setup is `uv run python main.py db setup`.
- OpenAI OAuth login is `uv run python main.py auth openai login`; use `--no-browser` when a browser should not be opened.
- Run the API with `uv run uvicorn apps.api.main:app --reload`.
- No repo-level test, lint, typecheck, formatter, codegen, or CI config exists; do not assume `pytest`, `ruff`, `mypy`, or task-runner commands until they are added.

## Database
- `docker-compose.yml` starts Postgres on `127.0.0.1:5432` with `pgvector/pgvector:pg17`; it also defines Redis, but current Python code does not import Redis.
- Default `DATABASE_URL` is `postgresql://scout:scout@127.0.0.1:5432/scout`.
- There is no migration framework; `db.schema.setup_database()` creates tables/extensions/indexes idempotently.

## Provider Auth
- OpenAI OAuth tokens default to `.auth/openai_auth.json`; set `SCOUT_AUTH_DIR` to avoid writing repo-local credentials during development.
- `OpenAICodexOAuth.login_browser()` starts a localhost callback on port `1455` and may open a browser; do not run it as routine verification.
- `OpenAIAuthProvider.generate()` calls `https://chatgpt.com/backend-api/codex/responses` and requires prior OAuth login; unit tests should fake OAuth/token storage and HTTP.

## Package Notes
- Shared request/response dataclasses live in `providers.types`.
- OpenAI Responses API shape conversion lives in `providers.openai_responses`.
- Provider HTTP and OAuth implementation lives under `providers.openai_auth`.
- RAG dataclasses, chunking, embedding/store protocols, and retriever orchestration live under `rag`.
- Cross-package orchestration lives under `services`; keep `rag` pure and keep SQL inside `db`.
- Embedding providers live in `rag.embeddings`; `SCOUT_EMBEDDINGS=gemini` is the default retrieval provider using `GEMINI_API_KEY` and `GEMINI_EMBEDDING_MODEL=gemini-embedding-001`.
- `SCOUT_EMBEDDINGS=hash` is deterministic local/offline fallback, and `SCOUT_EMBEDDINGS=openai` uses OpenAI `text-embedding-3-small`.
- Re-index jobs after changing embedding provider, model, or dimensions; indexing and querying must match.
- Keep embedding providers separate from `OpenAIAuthProvider`, which is for chat/reasoning output.
- FastAPI routes are thin adapters in `apps/api/routes`; database-backed operations go through repositories in `db` and orchestration functions in `services`.
- Postgres/pgvector integration lives in `db.pgvector`.
