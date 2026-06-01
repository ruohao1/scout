# Scout

Scout is a job-matching RAG backend. It stores job postings and CV profiles, indexes job descriptions into pgvector chunks, searches indexed jobs semantically, ranks jobs against a profile with deterministic scores, and can generate grounded match explanations with the chat provider.

## Architecture

```txt
apps/api              FastAPI routes and HTTP schemas
packages/db           Postgres/pgvector schema and repositories
packages/rag          chunking, embeddings, ranking, prompts, shared dataclasses
packages/services     orchestration across db/rag/providers
packages/providers    OpenAI OAuth chat/reasoning provider
```

Important separation:

```txt
Embedding model = retrieval layer
Chat model = reasoning/output layer
```

Embeddings are selected through `rag.embeddings`; Gemini is the default retrieval provider. Chat/reasoning currently uses `OpenAIAuthProvider`.

## Setup

Python 3.13 is required.

```bash
uv sync
docker compose up -d postgres
uv run python main.py db setup
```

Run the API:

```bash
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
```

OpenAPI docs are available at:

```txt
http://127.0.0.1:8000/docs
```

## Docker Compose

Build and run the containerized stack:

```bash
docker compose build
docker compose up -d postgres redis
docker compose run --rm api uv run python main.py db setup
docker compose up -d api web
```

Container endpoints:

```txt
API: http://127.0.0.1:8000/docs
Web: http://127.0.0.1:5173
```

The Compose stack defaults to deterministic local embeddings so it can run without external API keys:

```env
SCOUT_EMBEDDINGS=hash
```

To use Gemini embeddings in containers, set `SCOUT_EMBEDDINGS=gemini` and `GEMINI_API_KEY` before starting the API. Re-index jobs after changing embedding provider, model, or dimensions.

OpenAI OAuth tokens for containerized profile extraction and explanations are stored in the `scout-auth` Docker volume. Log in through the API container when needed:

```bash
docker compose run --rm api uv run python main.py auth openai login --no-browser
```

## Configuration

Copy `.env.example` if you want local environment values:

```bash
cp .env.example .env
```

Default local database:

```env
DATABASE_URL=postgresql://scout:scout@127.0.0.1:5432/scout
```

Default retrieval embeddings use Gemini:

```env
SCOUT_EMBEDDINGS=gemini
SCOUT_EMBEDDING_DIMENSIONS=1536
GEMINI_API_KEY=...
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
```

For deterministic local/offline embeddings:

```env
SCOUT_EMBEDDINGS=hash
```

For real OpenAI embeddings:

```env
SCOUT_EMBEDDINGS=openai
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Jobs must be re-indexed after changing embedding provider, model, or dimensions. Indexing and querying must use the same embedding provider/model/dimensions.

## OpenAI Auth

The chat/reasoning provider uses OpenAI OAuth tokens, not `OPENAI_API_KEY`.

```bash
uv run python main.py auth openai login
```

Headless/manual URL mode:

```bash
uv run python main.py auth openai login --no-browser
```

Tokens are stored in `.auth/openai_auth.json` by default. Set `SCOUT_AUTH_DIR` to move them elsewhere.

## API Pipeline

The current end-to-end flow is:

```txt
1. Create a profile
2. Create a job
3. Index the job
4. Search indexed jobs
5. Rank jobs against the profile
6. Explain ranked jobs with the chat model
```

Jobs must be indexed before `/search`, `/rank-jobs`, or `/rank-jobs/explain` can find them.

## Health

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

## Create A Profile

```bash
curl -X POST http://127.0.0.1:8000/profiles \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Ruohao",
    "cv_text": "Python Linux cybersecurity student with SIEM experience.",
    "target_roles": ["cybersecurity intern", "SOC analyst"],
    "target_locations": ["Luxembourg"],
    "skills": ["Python", "Linux", "SIEM"],
    "seniority": "student",
    "preferred_contract_types": ["internship"],
    "remote_preference": "hybrid"
  }'
```

Save the returned `id` as `PROFILE_ID`.

## Upload A CV Profile

Upload a PDF CV, extract its text into `cv_text`, and infer structured profile fields with the OpenAI Auth chat provider:

```bash
curl -X POST http://127.0.0.1:8000/profiles/upload \
  -F "file=@cv.pdf" \
  -F "name=Ruohao" \
  -F "extract_profile=true"
```

Profile extraction requires OpenAI OAuth login. Manual multipart fields override extracted fields:

```bash
curl -X POST http://127.0.0.1:8000/profiles/upload \
  -F "file=@cv.pdf" \
  -F "name=Ruohao" \
  -F "skills=Python,Linux,SIEM" \
  -F "target_roles=SOC analyst,cybersecurity intern" \
  -F "target_locations=Luxembourg" \
  -F "preferred_contract_types=internship" \
  -F "seniority=student" \
  -F "remote_preference=hybrid"
```

Skip LLM extraction and store only PDF text plus manual fields:

```bash
curl -X POST http://127.0.0.1:8000/profiles/upload \
  -F "file=@cv.pdf" \
  -F "name=Ruohao" \
  -F "extract_profile=false"
```

Only PDF uploads are supported. The upload limit is 5 MB. Scanned or image-only PDFs may fail because this version extracts embedded text and does not run OCR.

## Create A Job

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Cybersecurity Intern",
    "company": "Example SA",
    "location": "Luxembourg",
    "contract_type": "internship",
    "source": "manual",
    "url": "https://example.com/jobs/cybersecurity-intern",
    "description": "Requirements:\nPython\nLinux\nSIEM\nSOC\n\nResponsibilities:\nMonitor alerts and write scripts.",
    "seniority": "student",
    "remote_policy": "hybrid",
    "skills": ["Python", "Linux", "SIEM", "SOC"]
  }'
```

Save the returned `id` as `JOB_ID`.

## Import Mock Jobs

Import and index fixture jobs with deterministic local/offline embeddings:

```bash
SCOUT_EMBEDDINGS=hash uv run python main.py jobs import-mock \
  --fixture packages/services/fixtures/mock_jobs.json \
  --count 10 \
  --index
```

Import and index fixture jobs with the default Gemini embeddings:

```bash
GEMINI_API_KEY=... uv run python main.py jobs import-mock \
  --fixture packages/services/fixtures/mock_jobs.json \
  --count 10 \
  --index
```

Fixture imports skip duplicate job URLs, so re-running the command does not abort the whole import. Generated mock jobs do not need a fixture and use unique URLs:

```bash
SCOUT_EMBEDDINGS=hash uv run python main.py jobs import-mock --count 10 --index
```

## Index A Job

```bash
curl -X POST http://127.0.0.1:8000/jobs/$JOB_ID/index
```

Expected shape:

```json
{
  "job_id": "...",
  "chunks_indexed": 2
}
```

Indexing splits the job description into sections/chunks, embeds each chunk, and stores vectors in `job_chunks`.

## Search Jobs

```bash
curl -X POST http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Python SIEM internship",
    "filters": {
      "location": "Luxembourg",
      "contract_type": "internship"
    },
    "limit": 5
  }'
```

Search returns evidence chunks joined with job metadata.

## Rank Jobs

```bash
curl -X POST http://127.0.0.1:8000/rank-jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "profile_id": "'"$PROFILE_ID"'",
    "filters": {
      "location": "Luxembourg",
      "contract_type": "internship"
    },
    "limit": 5
  }'
```

Ranking is deterministic:

```txt
final_score =
  0.45 * vector_score
+ 0.25 * skill_overlap_score
+ 0.15 * location_score
+ 0.10 * contract_type_score
+ 0.05 * recency_score
```

`missing_skills` is computed from structured fields:

```txt
job.skills - profile.skills
```

## Explain Ranked Jobs

Requires OpenAI OAuth login.

```bash
curl -X POST http://127.0.0.1:8000/rank-jobs/explain \
  -H 'Content-Type: application/json' \
  -d '{
    "profile_id": "'"$PROFILE_ID"'",
    "filters": {
      "location": "Luxembourg",
      "contract_type": "internship"
    },
    "limit": 1
  }'
```

The default explanation model is `gpt-5.5`, which has been verified with the current OpenAI OAuth provider. This is separate from Gemini retrieval embeddings. The LLM explains the deterministic ranking using evidence chunks; it does not change scores.

## Current Endpoints

```txt
GET  /health
POST /jobs
GET  /jobs
GET  /jobs/{job_id}
POST /jobs/{job_id}/index
POST /profiles
GET  /profiles
GET  /profiles/{profile_id}
POST /search
POST /rank-jobs
POST /rank-jobs/explain
```

## Development Checks

There is no repo-level test, lint, typecheck, formatter, or CI config yet. Current safe checks are:

```bash
uv sync
uv run python -m compileall main.py apps packages
docker compose config --services
uv run python main.py db setup
```

Optional API smoke with the server running:

```bash
curl http://127.0.0.1:8000/health
```

## Not Built Yet

```txt
frontend UI
scraping
raw job text normalization
automatic indexing after job creation
background workers
persistent ranking history
cover letter generation
CV keyword suggestions
auth/users/multi-tenancy
```
