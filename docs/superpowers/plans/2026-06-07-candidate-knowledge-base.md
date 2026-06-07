# Candidate Knowledge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mixed user/profile model with one candidate knowledge base plus multiple target profiles, and use persisted candidate evidence embeddings for better job matching.

**Architecture:** Keep job-side RAG unchanged: `jobs`, `job_chunks`, pgvector search, and provider import flows remain the source of truth for jobs. Add candidate-side tables, repositories, services, and API routes, then update ranking to use `target_profile_id` with selected evidence weights and background evidence. Move the web Profiles workspace to a Candidate workspace once backend flows compile.

**Tech Stack:** Python 3.13, FastAPI, psycopg 3, Postgres with pgvector, uv workspace packages, Vite/React with pnpm, existing OpenAI OAuth provider for extraction/suggestions, existing `rag.embeddings` providers for vectors.

---

## Scope Notes

This plan intentionally avoids replacing job-side pgvector retrieval with LangChain vector stores. LangChain adapters can be added later at tool boundaries, but the first implementation should stabilize the new candidate data model and matching path.

The repo has no pytest/ruff/mypy setup. Verification uses compile checks, web build, Docker Compose config, and database setup with Postgres.

The existing project-local `opencode.json` is unrelated to this feature. Do not include it in these commits unless the user explicitly asks.

## File Structure

- Create `packages/rag/src/rag/candidate.py`: dataclasses and helpers for candidate evidence chunks and target-profile query text.
- Create `packages/db/src/db/candidate.py`: singleton candidate, documents, evidence, and evidence chunk repositories.
- Create `packages/db/src/db/target_profiles.py`: target profile and target profile evidence repositories.
- Modify `packages/db/src/db/schema.py`: create candidate, document, evidence, evidence chunk, target profile, and linking tables idempotently.
- Create `packages/services/src/services/candidate_indexing.py`: chunk and embed candidate evidence.
- Create `packages/services/src/services/candidate_documents.py`: upload CV, store document, extract evidence, index evidence.
- Create `packages/services/src/services/target_profiles.py`: CRUD and AI-assisted target profile suggestion orchestration.
- Modify `packages/services/src/services/profile_extraction.py`: reuse parsing for candidate evidence output or add conversion helpers.
- Modify `packages/services/src/services/job_ranking.py`: switch primary ranking input from old profile to target profile.
- Modify `packages/rag/src/rag/ranking.py`: add evidence-aware deterministic ranking signals.
- Create `apps/api/routes/candidate.py`: candidate/document/evidence endpoints.
- Create `apps/api/routes/target_profiles.py`: target profile endpoints.
- Modify `apps/api/routes/ranking.py`, `apps/api/routes/chat.py`, `apps/api/schemas.py`, `apps/api/main.py`: new schemas/routes and target-profile ranking request.
- Modify `packages/services/src/services/chat.py`, `packages/services/src/services/chat_orchestrator.py`, `packages/services/src/services/job_workflow_graph.py`: use `target_profile_id` where ranking is requested.
- Modify `apps/web/src/api.js`: candidate and target profile API client functions.
- Modify `apps/web/src/features/profiles/ProfilesView.jsx`: rename/rework into candidate workspace functionality, or create a new candidate feature and route old Profiles navigation to it.
- Modify `apps/web/src/App.jsx`, `apps/web/src/components/app-sidebar.jsx`, `apps/web/src/styles.css`: navigation and UI polish.
- Modify `AGENTS.md`: document the new candidate/target profile distinction after implementation.

## Task 1: Schema And Repository Foundations

**Files:**
- Modify: `packages/db/src/db/schema.py`
- Create: `packages/db/src/db/candidate.py`
- Create: `packages/db/src/db/target_profiles.py`
- Modify: `packages/db/src/db/__init__.py`

- [ ] **Step 1: Add schema tables in `db.schema.setup_database()`**

Add tables after `user_profiles`/profile enrichment tables and before indexes so old data can still exist during migration:

```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                display_name text,
                headline text,
                summary text,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_documents (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                filename text,
                content_type text,
                file_data bytea,
                text text NOT NULL,
                source text NOT NULL DEFAULT 'upload',
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_evidence (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                type text NOT NULL,
                title text NOT NULL,
                organization text,
                location text,
                start_date text,
                end_date text,
                is_current boolean NOT NULL DEFAULT false,
                description text,
                skills text[] NOT NULL DEFAULT '{}',
                url text,
                metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                source_document_id uuid REFERENCES candidate_documents(id) ON DELETE SET NULL,
                confidence double precision NOT NULL DEFAULT 1.0,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                CHECK (type IN ('experience', 'project', 'skill', 'education', 'certification', 'language', 'interest', 'document_note')),
                CHECK (confidence >= 0.0 AND confidence <= 1.0)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_evidence_chunks (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                evidence_id uuid NOT NULL REFERENCES candidate_evidence(id) ON DELETE CASCADE,
                chunk_index integer NOT NULL,
                content text NOT NULL,
                embedding vector(1536),
                metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                created_at timestamptz NOT NULL DEFAULT now(),
                UNIQUE (evidence_id, chunk_index)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS target_profiles (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                name text NOT NULL,
                summary text,
                target_roles text[] NOT NULL DEFAULT '{}',
                target_locations text[] NOT NULL DEFAULT '{}',
                preferred_contract_types text[] NOT NULL DEFAULT '{}',
                seniority text,
                remote_preference text,
                must_have_keywords text[] NOT NULL DEFAULT '{}',
                nice_to_have_keywords text[] NOT NULL DEFAULT '{}',
                avoid_keywords text[] NOT NULL DEFAULT '{}',
                instructions text,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS target_profile_evidence (
                target_profile_id uuid NOT NULL REFERENCES target_profiles(id) ON DELETE CASCADE,
                evidence_id uuid NOT NULL REFERENCES candidate_evidence(id) ON DELETE CASCADE,
                weight double precision NOT NULL DEFAULT 1.0,
                note text,
                created_at timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (target_profile_id, evidence_id),
                CHECK (weight >= 0.0 AND weight <= 1.0)
            )
            """
        )
```

- [ ] **Step 2: Add indexes in `db.schema.setup_database()`**

Add these index statements after existing profile indexes:

```python
        conn.execute("CREATE INDEX IF NOT EXISTS candidate_evidence_type_idx ON candidate_evidence (type)")
        conn.execute("CREATE INDEX IF NOT EXISTS candidate_evidence_source_document_idx ON candidate_evidence (source_document_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS candidate_evidence_skills_gin_idx ON candidate_evidence USING gin (skills)")
        conn.execute("CREATE INDEX IF NOT EXISTS candidate_evidence_chunks_evidence_id_idx ON candidate_evidence_chunks (evidence_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS target_profiles_created_at_idx ON target_profiles (created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS target_profile_evidence_evidence_id_idx ON target_profile_evidence (evidence_id)")
```

- [ ] **Step 3: Create `packages/db/src/db/candidate.py`**

Implement repositories with the same `psycopg.connect(self.url, row_factory=dict_row)` style as `db.profiles`. Include these concrete methods:

- `CandidateRepository.get()` returns the newest singleton candidate row or `None`.
- `CandidateRepository.upsert(candidate)` updates the existing singleton candidate when one exists; otherwise inserts a new row and returns it.
- `CandidateDocumentRepository.create(document)` inserts filename, content type, binary file data, extracted text, and source, then returns the row.
- `CandidateDocumentRepository.list(limit=50)` returns newest documents first.
- `CandidateDocumentRepository.get(document_id)` returns one document or `None`.
- `CandidateEvidenceRepository.create(evidence)` inserts a normalized evidence row and returns it.
- `CandidateEvidenceRepository.list(evidence_type=None, limit=200)` returns newest evidence rows, filtered by type when provided.
- `CandidateEvidenceRepository.get(evidence_id)` returns one evidence row or `None`.
- `CandidateEvidenceRepository.update(evidence_id, evidence)` updates editable evidence fields and returns the row or `None`.
- `CandidateEvidenceRepository.delete(evidence_id)` deletes one evidence row and returns whether a row was removed.
- `CandidateEvidenceRepository.replace_for_document(document_id, evidence)` deletes evidence for that document, inserts the provided rows, and returns inserted rows.
- `CandidateEvidenceChunkRepository.replace_for_evidence(evidence_id, chunks, embeddings)` deletes existing chunks for the evidence item and inserts the new chunk/vector pairs.
- `CandidateEvidenceChunkRepository.list_for_evidence(evidence_id)` returns chunks ordered by `chunk_index`.

Use local `_vector_literal(embedding: list[float]) -> str` identical to `db.job_chunks`.

- [ ] **Step 4: Create `packages/db/src/db/target_profiles.py`**

Implement these concrete methods:

- `TargetProfileRepository.create(profile)` inserts target profile fields and returns the row.
- `TargetProfileRepository.list(limit=50)` returns newest target profiles first.
- `TargetProfileRepository.get(target_profile_id)` returns one target profile or `None`.
- `TargetProfileRepository.update(target_profile_id, profile)` updates editable fields and returns the row or `None`.
- `TargetProfileRepository.delete(target_profile_id)` deletes one target profile and returns whether a row was removed.
- `TargetProfileEvidenceRepository.replace_for_profile(target_profile_id, links)` deletes existing links for the profile and inserts the supplied evidence links with clamped weights.
- `TargetProfileEvidenceRepository.list_for_profile(target_profile_id)` returns evidence links joined to evidence rows, ordered by weight descending and creation time ascending.

Clamp `weight` in Python before writes using:

```python
def _clamp_weight(value: object) -> float:
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    return 1.0
```

- [ ] **Step 5: Export repositories in `packages/db/src/db/__init__.py`**

Add imports and `__all__` entries for new repository classes.

- [ ] **Step 6: Verify Python compile**

Run: `uv run python -m compileall main.py apps packages`

Expected: command exits `0`.

- [ ] **Step 7: Commit**

```bash
git add packages/db/src/db/schema.py packages/db/src/db/candidate.py packages/db/src/db/target_profiles.py packages/db/src/db/__init__.py
git commit -m "feat: add candidate knowledge schema"
```

## Task 2: Candidate Evidence Dataclasses And Indexing

**Files:**
- Create: `packages/rag/src/rag/candidate.py`
- Create: `packages/services/src/services/candidate_indexing.py`
- Modify: `packages/services/src/services/__init__.py`

- [ ] **Step 1: Create `rag.candidate` evidence text helpers**

Create `candidate_evidence_text(evidence: dict) -> str` that serializes only non-empty fields in stable order:

```python
def candidate_evidence_text(evidence: dict) -> str:
    parts = [
        f"Type: {evidence.get('type')}",
        f"Title: {evidence.get('title')}",
        f"Organization: {evidence.get('organization')}",
        f"Location: {evidence.get('location')}",
        f"Dates: {_dates(evidence)}",
        f"Description: {evidence.get('description')}",
        f"Skills: {', '.join(evidence.get('skills') or [])}",
        f"URL: {evidence.get('url')}",
    ]
    return "\n".join(part for part in parts if not part.endswith(': None') and not part.endswith(': ')).strip()
```

Also add `candidate_evidence_metadata(evidence: dict) -> dict` returning `type`, `title`, `organization`, `skills`, `source_document_id`, and `confidence`.

- [ ] **Step 2: Create `services.candidate_indexing`**

Implement:

```python
class CandidateEvidenceNotFoundError(ValueError):
    pass

def index_candidate_evidence(
    evidence_id: str,
    *,
    evidence: CandidateEvidenceRepository | None = None,
    chunks: CandidateEvidenceChunkRepository | None = None,
    embeddings: EmbeddingProvider | None = None,
) -> int:
    evidence_repository = evidence or CandidateEvidenceRepository()
    chunk_repository = chunks or CandidateEvidenceChunkRepository()
    embedding_provider = embeddings or create_embedding_provider()
    item = evidence_repository.get(evidence_id)
    if item is None:
        raise CandidateEvidenceNotFoundError(f"Candidate evidence not found: {evidence_id}")
    content = candidate_evidence_text(item)
    chunk = {"chunk_index": 0, "content": content, "metadata": candidate_evidence_metadata(item)}
    vectors = embedding_provider.embed_texts([content])
    chunk_repository.replace_for_evidence(evidence_id=evidence_id, chunks=[chunk], embeddings=vectors)
    return 1

def reindex_all_candidate_evidence(
    *,
    evidence: CandidateEvidenceRepository | None = None,
    embeddings: EmbeddingProvider | None = None,
) -> int:
    evidence_repository = evidence or CandidateEvidenceRepository()
    indexed = 0
    for item in evidence_repository.list(limit=10_000):
        indexed += index_candidate_evidence(str(item["id"]), evidence=evidence_repository, embeddings=embeddings)
    return indexed
```

`reindex_all_candidate_evidence` should list all evidence and call `index_candidate_evidence` for each item.

- [ ] **Step 3: Export service functions**

Update `packages/services/src/services/__init__.py` with `index_candidate_evidence`, `reindex_all_candidate_evidence`, and `CandidateEvidenceNotFoundError`.

- [ ] **Step 4: Verify compile**

Run: `uv run python -m compileall main.py apps packages`

Expected: command exits `0`.

- [ ] **Step 5: Commit**

```bash
git add packages/rag/src/rag/candidate.py packages/services/src/services/candidate_indexing.py packages/services/src/services/__init__.py
git commit -m "feat: index candidate evidence embeddings"
```

## Task 3: Candidate Document And Evidence Services

**Files:**
- Create: `packages/services/src/services/candidate_documents.py`
- Modify: `packages/services/src/services/profile_extraction.py`
- Modify: `packages/services/src/services/__init__.py`

- [ ] **Step 1: Add conversion helper in `profile_extraction.py`**

Add `profile_fields_to_candidate_evidence(extracted: dict, *, source_document_id: str | None = None) -> list[dict[str, Any]]`.

Map extracted data as follows:

```python
experience -> type='experience', title, organization=company, location, start_date, end_date, is_current, description, skills
projects -> type='project', title=name, organization=None, url, description, skills
enriched_skills -> type='skill', title=name, description=category/proficiency sentence, metadata={'category': category, 'proficiency': proficiency}
```

Also create evidence from top-level values:

```text
target_roles -> type='document_note', title='Target roles', description=', '.join(values)
target_locations -> type='document_note', title='Target locations', description=', '.join(values)
preferred_contract_types -> type='document_note', title='Preferred contract types', description=', '.join(values)
```

- [ ] **Step 2: Create `candidate_documents.py`**

Implement `upload_candidate_cv`:

```python
def upload_candidate_cv(
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    extract_profile: bool = True,
    model: str = "gpt-5.5",
) -> dict[str, Any]:
    cv_text = extract_cv_text(filename, content_type, data)
    document = CandidateDocumentRepository().create(
        {
            "filename": filename,
            "content_type": content_type or "application/pdf",
            "file_data": data,
            "text": cv_text,
            "source": "upload",
        }
    )
    evidence_items = []
    extraction_warning = None
    if extract_profile:
        try:
            extracted = extract_profile_fields(cv_text, model=model)
            evidence_items = profile_fields_to_candidate_evidence(extracted, source_document_id=str(document["id"]))
            created = CandidateEvidenceRepository().replace_for_document(str(document["id"]), evidence_items)
            for item in created:
                index_candidate_evidence(str(item["id"]))
        except ProfileExtractionError as exc:
            extraction_warning = str(exc)
    return {"document": document, "evidence": created if extract_profile and extraction_warning is None else [], "extraction_warning": extraction_warning}
```

Use `services.cv_parsing.extract_cv_text` and keep extraction failures non-blocking after document storage.

- [ ] **Step 3: Export service functions**

Update `services.__init__` with `upload_candidate_cv`.

- [ ] **Step 4: Verify compile**

Run: `uv run python -m compileall main.py apps packages`

Expected: command exits `0`.

- [ ] **Step 5: Commit**

```bash
git add packages/services/src/services/candidate_documents.py packages/services/src/services/profile_extraction.py packages/services/src/services/__init__.py
git commit -m "feat: extract candidate evidence from CVs"
```

## Task 4: Candidate And Target Profile APIs

**Files:**
- Modify: `apps/api/schemas.py`
- Create: `apps/api/routes/candidate.py`
- Create: `apps/api/routes/target_profiles.py`
- Modify: `apps/api/main.py`

- [ ] **Step 1: Add schemas in `apps/api/schemas.py`**

Add Pydantic models with these exact fields:

- `CandidateRead`: `id: UUID`, `display_name: str | None`, `headline: str | None`, `summary: str | None`, `created_at: datetime`, `updated_at: datetime`.
- `CandidateUpdate`: `display_name: str | None = None`, `headline: str | None = None`, `summary: str | None = None`.
- `CandidateDocumentRead`: `id: UUID`, `filename: str | None`, `content_type: str | None`, `text: str`, `source: str`, `created_at: datetime`, `updated_at: datetime`.
- `CandidateEvidenceCreate`: `type`, `title`, `organization`, `location`, `start_date`, `end_date`, `is_current`, `description`, `skills`, `url`, `metadata`, `source_document_id`, `confidence`.
- `CandidateEvidenceRead`: all `CandidateEvidenceCreate` fields plus `id: UUID`, `created_at: datetime`, `updated_at: datetime`.
- `CandidateEvidenceReindexRead`: `indexed: int`.
- `TargetProfileEvidenceLink`: `evidence_id: UUID`, `weight: float = Field(default=1.0, ge=0.0, le=1.0)`, `note: str | None = None`.
- `TargetProfileCreate`: `name`, `summary`, `target_roles`, `target_locations`, `preferred_contract_types`, `seniority`, `remote_preference`, `must_have_keywords`, `nice_to_have_keywords`, `avoid_keywords`, `instructions`, `evidence`.
- `TargetProfileRead`: all `TargetProfileCreate` fields plus `id: UUID`, `created_at: datetime`, `updated_at: datetime`.
- `TargetProfileSuggestionRequest`: `count: int = Field(default=3, ge=1, le=5)`.

Use `Literal` for evidence types: `Literal['experience', 'project', 'skill', 'education', 'certification', 'language', 'interest', 'document_note']`.

- [ ] **Step 2: Create candidate routes**

Routes:

```python
GET /candidate
PUT /candidate
GET /candidate/documents
POST /candidate/documents/upload
GET /candidate/evidence
POST /candidate/evidence
PUT /candidate/evidence/{evidence_id}
DELETE /candidate/evidence/{evidence_id}
POST /candidate/evidence/reindex
```

For create/update evidence, call `index_candidate_evidence` after a successful write. For delete, return `204`.

- [ ] **Step 3: Create target profile routes**

Routes:

```python
GET /target-profiles
POST /target-profiles
GET /target-profiles/{target_profile_id}
PUT /target-profiles/{target_profile_id}
DELETE /target-profiles/{target_profile_id}
POST /target-profiles/suggest
```

For `suggest`, return draft objects but do not save them.

- [ ] **Step 4: Wire routers in `apps/api/main.py`**

Import and include `candidate_router` and `target_profiles_router`.

- [ ] **Step 5: Verify compile**

Run: `uv run python -m compileall main.py apps packages`

Expected: command exits `0`.

- [ ] **Step 6: Commit**

```bash
git add apps/api/schemas.py apps/api/routes/candidate.py apps/api/routes/target_profiles.py apps/api/main.py
git commit -m "feat: add candidate and target profile APIs"
```

## Task 5: Target Profile Services And Suggestions

**Files:**
- Create: `packages/services/src/services/target_profiles.py`
- Modify: `packages/services/src/services/__init__.py`

- [ ] **Step 1: Implement target profile service helpers**

Add service helpers with these behaviors:

- `create_target_profile(payload)` splits profile fields from `payload["evidence"]`, creates the target profile row, writes evidence links through `TargetProfileEvidenceRepository.replace_for_profile`, and returns the target profile with evidence links.
- `update_target_profile(target_profile_id, payload)` updates the target profile row, replaces evidence links when `payload` includes `evidence`, and returns the target profile with evidence links or `None`.
- `get_target_profile_with_evidence(target_profile_id)` returns one target profile merged with `evidence` links or `None`.

- [ ] **Step 2: Implement AI suggestion**

Add `TargetProfileSuggestionProvider` as a `Protocol` with a `generate(request: GenerateRequest)` method. Add `suggest_target_profiles(count=3, provider=None, model="gpt-5.5")` that loads candidate evidence, calls the provider, parses strict JSON, and returns unsaved target profile drafts.

Build prompt from candidate evidence list. Instruct model to return strict JSON with `profiles`, and each profile containing `name`, `summary`, `target_roles`, `target_locations`, `preferred_contract_types`, `seniority`, `remote_preference`, `must_have_keywords`, `nice_to_have_keywords`, `avoid_keywords`, `instructions`, and `evidence` links by `evidence_id` with `weight` and `note`.

- [ ] **Step 3: Parse suggestions defensively**

Invalid JSON should raise `TargetProfileSuggestionError`. Unknown evidence IDs should be skipped. Weights should be clamped.

- [ ] **Step 4: Export service functions**

Update `services.__init__`.

- [ ] **Step 5: Verify compile**

Run: `uv run python -m compileall main.py apps packages`

Expected: command exits `0`.

- [ ] **Step 6: Commit**

```bash
git add packages/services/src/services/target_profiles.py packages/services/src/services/__init__.py
git commit -m "feat: suggest target profiles"
```

## Task 6: Evidence-Aware Ranking

**Files:**
- Modify: `packages/services/src/services/job_ranking.py`
- Modify: `packages/rag/src/rag/ranking.py`
- Modify: `apps/api/schemas.py`
- Modify: `apps/api/routes/ranking.py`
- Modify: `packages/services/src/services/chat.py`
- Modify: `packages/services/src/services/chat_orchestrator.py`
- Modify: `packages/services/src/services/job_workflow_graph.py`

- [ ] **Step 1: Change ranking request schema**

In `apps/api/schemas.py`, update ranking request to accept `target_profile_id: UUID`. Keep `profile_id` only if needed as a temporary compatibility alias; new code should prefer `target_profile_id`.

- [ ] **Step 2: Load target profile context**

In `services.job_ranking`, replace `ProfileRepository.get_with_enrichment(profile_id)` with `get_target_profile_with_evidence(target_profile_id)`.

Add `TargetProfileNotFoundError`.

- [ ] **Step 3: Build target query**

Create `_target_profile_query(target_profile: dict) -> str` using:

```python
summary
target_roles
must_have_keywords
nice_to_have_keywords
selected evidence title, description, skills repeated by weight bucket
low-weight background evidence title, description, skills once
```

Do not include `avoid_keywords` in positive query text.

- [ ] **Step 4: Add ranking signals**

In `rag.ranking`, add fields to `RankedJob` only if needed. Prefer preserving existing response shape and extending with optional fields:

```python
selected_evidence_score: float = 0.0
background_evidence_score: float = 0.0
keyword_score: float = 0.0
penalty_score: float = 0.0
matched_evidence: list[dict[str, Any]] = field(default_factory=list)
```

Compute keyword score from job title/content/skills. Apply avoid keyword penalty when title/content contains avoid keyword.

- [ ] **Step 5: Update route error handling**

Return `404` when target profile does not exist.

- [ ] **Step 6: Update chat tools**

Change tool argument from `profile_id` to `target_profile_id` in prompts and schema. If a user asks to rank without a selected target profile, tell them to create or select one.

- [ ] **Step 7: Verify compile**

Run: `uv run python -m compileall main.py apps packages`

Expected: command exits `0`.

- [ ] **Step 8: Commit**

```bash
git add packages/services/src/services/job_ranking.py packages/rag/src/rag/ranking.py apps/api/schemas.py apps/api/routes/ranking.py packages/services/src/services/chat.py packages/services/src/services/chat_orchestrator.py packages/services/src/services/job_workflow_graph.py
git commit -m "feat: rank jobs with target profiles"
```

## Task 7: Data Migration From Old Profiles

**Files:**
- Create: `packages/services/src/services/candidate_migration.py`
- Modify: `main.py`
- Modify: `packages/services/src/services/__init__.py`

- [ ] **Step 1: Create migration service**

Implement `migrate_profiles_to_candidate(source_profile_id=None) -> dict[str, Any]` with this behavior and return shape:

- If no `source_profile_id`, use the newest existing `user_profiles` row.
- Upsert singleton candidate from profile name and CV text summary.
- Create a candidate document for CV text if one does not already exist with metadata marker `legacy_profile_id`.
- Convert `profile_experiences`, `profile_projects`, `profile_skills` into candidate evidence if not already migrated.
- Create one default target profile from the legacy profile preferences if no migrated target profile exists.
- Link migrated evidence to default target profile with `0.8` weight.
- Index migrated candidate evidence.
- Return `{"candidate_id": str, "document_id": str | None, "evidence_count": int, "target_profile_id": str | None, "indexed_count": int}`.

- [ ] **Step 2: Add CLI command**

In `main.py`, add:

```bash
uv run python main.py candidate migrate-profile
```

Also support `--profile-id`.

- [ ] **Step 3: Verify compile**

Run: `uv run python -m compileall main.py apps packages`

Expected: command exits `0`.

- [ ] **Step 4: Commit**

```bash
git add packages/services/src/services/candidate_migration.py packages/services/src/services/__init__.py main.py
git commit -m "feat: migrate profiles to candidate model"
```

## Task 8: Web API Client And State Model

**Files:**
- Modify: `apps/web/src/api.js`
- Modify: `apps/web/src/lib/profile.js` or create `apps/web/src/lib/candidate.js`
- Modify: `apps/web/src/lib/storage.js`

- [ ] **Step 1: Add API client functions**

In `api.js`, add functions for candidate, documents, evidence, target profiles, suggestion, and rank-by-target-profile. Use the existing error handling style.

Function names:

```javascript
getCandidate
updateCandidate
listCandidateDocuments
uploadCandidateDocument
listCandidateEvidence
createCandidateEvidence
updateCandidateEvidence
deleteCandidateEvidence
reindexCandidateEvidence
listTargetProfiles
createTargetProfile
getTargetProfile
updateTargetProfile
deleteTargetProfile
suggestTargetProfiles
rankJobsForTargetProfile
```

- [ ] **Step 2: Update local storage key**

Store active target profile ID under a new key such as `scout.activeTargetProfileId`. Do not reuse the old selected profile key.

- [ ] **Step 3: Verify web build**

Run from `apps/web`: `pnpm run build`

Expected: build exits `0`; Vite large chunk warning is acceptable.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/api.js apps/web/src/lib/profile.js apps/web/src/lib/storage.js
git commit -m "feat: add candidate web API client"
```

If `apps/web/src/lib/candidate.js` is created instead of modifying `profile.js`, include it in the commit and leave `profile.js` only for compatibility helpers used by existing components.

## Task 9: Candidate Workspace UI

**Files:**
- Modify: `apps/web/src/features/profiles/ProfilesView.jsx`
- Modify: `apps/web/src/App.jsx`
- Modify: `apps/web/src/components/app-sidebar.jsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Rename UI language**

Change visible labels from Profiles to Candidate where the screen represents the single user. Keep component filename if a full rename causes too much churn.

- [ ] **Step 2: Load candidate workspace data**

Load candidate, documents, evidence, target profiles, and active target profile on mount. Use existing loading/error patterns.

- [ ] **Step 3: Build evidence sections**

Render sections for `experience`, `project`, `skill`, `education`, `certification`, `language`, `interest`, and `document_note`. Add/edit/delete forms should call the API client from Task 8.

- [ ] **Step 4: Build target profile panel**

Render target profile list, create/edit form, active profile selector, and evidence-weight editor. Evidence weights should use numeric inputs clamped between `0` and `1` with step `0.1`.

- [ ] **Step 5: Add AI suggestion flow**

Add a button that calls `suggestTargetProfiles`. Show returned drafts and let the user save a draft through `createTargetProfile`. Do not auto-save suggestions.

- [ ] **Step 6: Update matching calls**

Ensure matches/ranking uses `rankJobsForTargetProfile` and active target profile ID.

- [ ] **Step 7: Verify web build**

Run from `apps/web`: `pnpm run build`

Expected: build exits `0`; Vite large chunk warning is acceptable.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/features/profiles/ProfilesView.jsx apps/web/src/App.jsx apps/web/src/components/app-sidebar.jsx apps/web/src/styles.css
git commit -m "feat: add candidate workspace UI"
```

## Task 10: Documentation And Final Verification

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`

- [ ] **Step 1: Update `AGENTS.md`**

Add high-signal notes:

```markdown
- Candidate/user knowledge is now separate from job-specific target profiles; ranking should use `target_profile_id` for new code.
- Candidate evidence embeddings live in `candidate_evidence_chunks`; reindex them after changing `SCOUT_EMBEDDINGS`, embedding model, or dimensions.
- Legacy `user_profiles` data can be migrated with `uv run python main.py candidate migrate-profile`.
```

- [ ] **Step 2: Update `README.md`**

Add a compact section explaining:

- Candidate knowledge base
- Target profiles
- Evidence reindexing
- Profile migration command

- [ ] **Step 3: Run full safe checks**

Run from repo root:

```bash
uv run python -m compileall main.py apps packages
docker compose config --services
```

Run from `apps/web`:

```bash
pnpm run build
```

Expected: all exit `0`; Vite large chunk warning is acceptable.

- [ ] **Step 4: Run DB setup check when Postgres is available**

Run:

```bash
uv run python main.py db setup
```

Expected: `Database schema is ready.`

- [ ] **Step 5: Commit docs**

```bash
git add AGENTS.md README.md
git commit -m "docs: document candidate target profiles"
```

## Manual Smoke Test Script

After all tasks are implemented, run these commands with local hash embeddings and Postgres:

```bash
docker compose up -d postgres
SCOUT_EMBEDDINGS=hash uv run python main.py db setup
SCOUT_EMBEDDINGS=hash uv run python main.py jobs import-mock --count 5 --index
```

Then run API:

```bash
SCOUT_EMBEDDINGS=hash uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload
```

Use OpenAPI docs at `http://127.0.0.1:8000/docs` to verify:

1. `PUT /candidate` creates or updates the singleton candidate.
2. `POST /candidate/evidence` creates an evidence item.
3. `POST /candidate/evidence/reindex` indexes evidence.
4. `POST /target-profiles` creates a target profile linked to evidence.
5. `POST /rank-jobs` ranks jobs with `target_profile_id`.

## Plan Self-Review

- Spec coverage: candidate model, documents, evidence, evidence embeddings, target profiles, selected/background evidence, AI suggestion, migration, ranking, API, UI, and verification are covered.
- Marker scan: no incomplete implementation markers remain.
- Type consistency: plan consistently uses `target_profile_id`, `candidate_evidence`, and `candidate_evidence_chunks`.
- Scope check: this is a large feature but split into independently reviewable commits with backend foundations before UI changes.
