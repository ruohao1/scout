# Candidate Knowledge Base Redesign

## Goal

Redesign Scout's user/profile model so the app stores one complete candidate knowledge base and creates multiple job-specific target profiles from that knowledge. Matching should use persisted candidate evidence embeddings, selected evidence weights, and existing job chunk retrieval to produce better job matches and clearer explanations.

## Decisions

- Scout supports one candidate/user only for now.
- Target profiles can be created manually or suggested by AI, but AI suggestions must be reviewed and edited before they affect matching.
- Target profiles use a hybrid evidence model: explicitly selected evidence has high weight, while unselected background evidence can still contribute at low weight.
- V1 supports experiences, projects, skills, education, certifications, languages, interests/hobbies, and documents/CVs.
- The old `user_profiles` concept should not remain as a long-term compatibility layer. Existing data should be migrated into the new model, then APIs and UI should move to the new names.

## Current Problem

Current Scout mixes two different concepts in `user_profiles`:

- The full facts about the candidate, including CV text and extracted evidence.
- The job-specific matching preferences used for ranking.

This makes multiple job-search personas awkward. A cybersecurity internship profile, backend Python profile, and AI/RAG developer profile should all reuse the same underlying candidate facts, but emphasize different evidence and preferences.

Current ranking already embeds a concatenated runtime profile query built from CV text, skills, experiences, and projects. It does not persist profile or evidence embeddings, and it cannot reason cleanly about selected versus background evidence.

## Target Model

### Candidate

The singleton candidate record stores high-level identity fields only.

Suggested fields:

- `id`
- `display_name`
- `headline`
- `summary`
- `created_at`
- `updated_at`

### Candidate Documents

Candidate documents store uploaded source material, such as CV PDFs and extracted text.

Suggested fields:

- `id`
- `filename`
- `content_type`
- `file_data`
- `text`
- `source`
- `created_at`
- `updated_at`

Documents are source material. They are not the main matching abstraction; structured evidence is.

### Candidate Evidence

Candidate evidence stores normalized facts about the candidate.

Evidence types for v1:

- `experience`
- `project`
- `skill`
- `education`
- `certification`
- `language`
- `interest`
- `document_note`

Suggested common fields:

- `id`
- `type`
- `title`
- `organization`
- `location`
- `start_date`
- `end_date`
- `is_current`
- `description`
- `skills text[]`
- `url`
- `metadata jsonb`
- `source_document_id`
- `confidence`
- `created_at`
- `updated_at`

The common schema intentionally uses broad optional fields instead of separate tables for every evidence type in v1. This keeps the repository and UI smaller while still supporting the required data types.

### Candidate Evidence Chunks

Evidence chunks are the persisted embedding unit for candidate knowledge.

Suggested fields:

- `id`
- `evidence_id`
- `chunk_index`
- `content`
- `embedding vector(1536)`
- `metadata jsonb`
- `created_at`

Each chunk should include enough text to stand alone in retrieval and explanation, such as title, organization, description, skills, dates, and evidence type.

### Target Profiles

Target profiles represent specific job-search personas.

Examples:

- Cybersecurity internship
- Python backend junior
- AI/RAG developer
- Luxembourg student roles

Suggested fields:

- `id`
- `name`
- `summary`
- `target_roles text[]`
- `target_locations text[]`
- `preferred_contract_types text[]`
- `seniority`
- `remote_preference`
- `must_have_keywords text[]`
- `nice_to_have_keywords text[]`
- `avoid_keywords text[]`
- `instructions`
- `created_at`
- `updated_at`

### Target Profile Evidence

Target profile evidence links candidate evidence to a target profile with explicit importance.

Suggested fields:

- `target_profile_id`
- `evidence_id`
- `weight float`
- `note`
- `created_at`

Weights should be clamped to `0.0` through `1.0`. Selected evidence usually has weights between `0.6` and `1.0`. Unselected background evidence can be used by ranking with a fixed lower weight, without needing rows in this table.

## AI-Assisted Flow

### CV Extraction

When the user uploads a CV:

1. Store the document and extracted text.
2. Ask the existing OpenAI OAuth provider to extract structured evidence.
3. Save evidence with source document and confidence.
4. Embed the evidence chunks.
5. Show extracted evidence for user review and editing.

Extraction failures should not block document upload. The app should keep the document and surface an extraction warning.

### Target Profile Suggestions

Scout can suggest target profiles from candidate evidence.

The AI should return draft profiles with:

- name
- summary
- target roles
- preferred locations/contracts/seniority/remote preference when inferable
- selected evidence IDs with proposed weights
- rationale for each selected evidence item

Draft target profiles must not affect matching until the user saves them.

## Matching Flow

Ranking should use the selected target profile instead of the old `profile_id` model.

Inputs:

- `target_profile_id`
- optional job filters
- limit

Steps:

1. Load the target profile.
2. Load selected candidate evidence and background candidate evidence.
3. Build a target query from profile preferences plus selected evidence.
4. Embed the query and search existing `job_chunks` with pgvector.
5. Compare selected evidence chunks against retrieved job chunks to compute an evidence coverage score.
6. Rank grouped jobs with deterministic scores.
7. Return ranked jobs with matched evidence and explanation-ready context.

The existing `jobs` and `job_chunks` tables remain the source of truth for job-side RAG.

## Ranking Signals

The current ranking uses vector score, skill overlap, location, contract type, and recency.

The redesigned ranking should add:

- selected evidence semantic score
- background evidence semantic score
- selected evidence coverage
- must-have keyword score
- nice-to-have keyword bonus
- avoid keyword penalty
- seniority and remote preference fit

Initial target weighting:

- `0.35` job semantic match
- `0.20` selected evidence match
- `0.15` skill overlap
- `0.10` location fit
- `0.10` contract, seniority, and remote fit
- `0.05` recency
- `0.05` keyword bonuses and penalties

Weights can be constants in v1. They do not need to be configurable through the UI.

## API Shape

Candidate APIs:

- `GET /candidate`
- `PUT /candidate`
- `GET /candidate/documents`
- `POST /candidate/documents/upload`
- `GET /candidate/evidence`
- `POST /candidate/evidence`
- `PUT /candidate/evidence/{evidence_id}`
- `DELETE /candidate/evidence/{evidence_id}`
- `POST /candidate/evidence/reindex`

Target profile APIs:

- `GET /target-profiles`
- `POST /target-profiles`
- `GET /target-profiles/{target_profile_id}`
- `PUT /target-profiles/{target_profile_id}`
- `DELETE /target-profiles/{target_profile_id}`
- `POST /target-profiles/suggest`

Matching APIs:

- `POST /rank-jobs` should accept `target_profile_id` instead of `profile_id`.
- Chat tools should use `target_profile_id` for ranking.

The existing profile APIs may remain briefly during migration, but new UI work should use candidate and target profile APIs.

## Migration

Migration should happen through `db.schema.setup_database()` because Scout has no migration framework.

Existing data maps as follows:

- `user_profiles.name` maps to `candidate.display_name`.
- `user_profiles.cv_text` maps to a candidate document or `document_note` evidence.
- `profile_experiences` maps to evidence type `experience`.
- `profile_projects` maps to evidence type `project`.
- `profile_skills` maps to evidence type `skill`.
- `user_profiles.target_roles`, `target_locations`, `preferred_contract_types`, `seniority`, and `remote_preference` map to a default target profile.
- Existing profile evidence should be linked to the default target profile with moderate-to-high weights.

The migration should be idempotent and safe to run multiple times.

## UI Shape

The web app should move from a Profiles page to a Candidate workspace with two areas.

Candidate knowledge area:

- Candidate summary
- Documents/CVs
- Evidence sections for experience, projects, skills, education, certifications, languages, interests/hobbies
- Manual add/edit/delete for evidence
- CV upload and AI extraction review

Target profiles area:

- List target profiles
- Create/edit target profile
- AI-suggest target profiles
- Select evidence and set emphasis weights
- Choose active target profile for matching/chat

The chat and ranking flows should ask the user to choose or create a target profile when none is active.

## Error Handling

- Missing target profile returns a clear 404-style API error and a user-facing prompt to create/select one.
- Evidence reindex failures should identify which evidence item failed and leave existing embeddings untouched when possible.
- Embedding provider changes still require reindexing evidence and jobs.
- CV extraction failures should store the document and return an extraction warning.
- AI target profile suggestion failures should not modify saved target profiles.

## Testing And Verification

Repo currently has no formal test framework. Minimum safe checks for implementation:

- `uv run python -m compileall main.py apps packages`
- `docker compose config --services`
- `pnpm run build` from `apps/web`
- With Postgres running: `uv run python main.py db setup`

Focused behavioral checks:

- Create/update/delete evidence.
- Upload CV and confirm document storage even if extraction fails.
- Reindex candidate evidence with `SCOUT_EMBEDDINGS=hash`.
- Create target profile manually and link evidence weights.
- Suggest target profile without saving drafts automatically.
- Rank jobs using `target_profile_id`.
- Confirm old job indexing/search still works.

## Non-Goals For V1

- Multi-user account management.
- Full graph database or complex relationship model.
- UI-configurable ranking weights.
- Replacing job-side pgvector retrieval with LangChain vector stores.
- Removing all old profile code in the first small implementation step if a temporary compatibility window is needed.

## Open Implementation Notes

- Prefer new repository modules for candidate documents, evidence, evidence chunks, target profiles, and target profile evidence rather than expanding `db.profiles` further.
- Keep SQL in `db`, orchestration in `services`, and RAG dataclasses/helpers in `rag`.
- Add LangChain adapters only at the retrieval/tool boundary; do not make LangChain the source of truth for stored vectors.
- Use `SCOUT_EMBEDDINGS=hash` for local deterministic verification.
