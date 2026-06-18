# Chat-First CV Orchestration Design

## Purpose

Move Scout toward a chat-first multi-agent product while preserving the existing jobs, candidate, target profile, and CV panes as fallback inspection and editing surfaces. The first milestone covers the core user loop: fetch or search jobs in chat, select a job from chat, and ask Scout to tailor a CV for that selected job.

## Current State

The API chat route already enters `services.job_workflow_graph`, which routes requests through `chat_router`, `chat_orchestrator`, and `job_search_agent`. Chat can search, rank, fetch live JobSpy jobs, list profiles, and load a target profile. The web chat already renders job cards and links them to `/chat/jobs/:jobId`, which opens a job detail pane in the chat workspace.

CV generation exists, but it is still driven by direct job routes and the Jobs workspace pane:

- `POST /jobs/{job_id}/tailored-cv`
- `POST /jobs/{job_id}/tailored-cv/latex`
- `GET /jobs/{job_id}/tailored-cv/latex/{artifact_id}/pdf`
- `apps/web/src/features/jobs/TailoredCVPane.jsx`

The recent CV length work added `length`, `selected_length`, and `length_reason` to the LaTeX endpoint.

## Goals

- Keep `/chat` as the primary user-facing flow for the first job-to-CV loop.
- Support both click-based and natural-language job selection.
- Reuse existing job search, ranking, and CV generation services.
- Return CV artifacts in chat with enough metadata for download buttons and user trust.
- Keep existing pages and panes available as review/edit fallbacks.
- Preserve current streaming progress behavior.

## Non-Goals

- Do not remove or hide existing pages in this milestone.
- Do not build a full persistent workflow/task system yet.
- Do not add candidate-evidence editing through chat yet.
- Do not add settings/admin changes through chat yet.
- Do not rewrite the current LangGraph workflow from scratch.

## User Experience

The intended flow is:

1. The user asks Scout to fetch, search, or rank jobs.
2. Scout returns job cards in chat.
3. The user clicks a job card or refers to a result by language such as `job 2`, `the second one`, `the Revolut role`, or `this one` after opening a card.
4. The user asks Scout to tailor a CV.
5. Scout resolves the job reference, generates tailored CV content and LaTeX through existing services, and returns a chat message with artifact metadata.
6. The chat message offers `.tex` download, PDF download when available, and a way to open the existing job/CV review surface.

If Scout cannot resolve the job, it asks the user to choose a job card or refer to one of the recent numbered jobs.

## Architecture

Extend the current chat workflow rather than replacing it.

Add an application/CV specialist path behind the existing orchestrator graph. Keep job-reference resolution in a focused service module so `services.job_workflow_graph` does not grow another large parsing responsibility. The route/action should be named around `tailor_cv` or `application_cv`.

The workflow responsibilities are:

- Route CV-tailoring requests separately from generic chat and job search.
- Resolve the requested job from explicit selected context or recent chat results.
- Call `draft_tailored_cv_latex` with the selected target profile, user instruction, and optional length.
- Return a normal `ChatResult` plus artifact metadata.
- Emit streaming events for route, resolve, generate, and artifact completion.

## Job Reference Resolution

The resolver should accept these inputs:

- `selected_job_id` from the active chat route `/chat/jobs/:jobId`.
- The latest assistant messages in chat history that contain `jobs` or `ranked_jobs`.
- The current user message.

Resolution order:

1. If `selected_job_id` is present and the user says `this`, `this one`, `selected job`, or gives no other conflicting reference, use it.
2. If the user says `job 1`, `job 2`, `first`, `second`, etc., resolve against the most recent chat result list.
3. If the user mentions a recognizable title or company from recent results, choose the best simple text match.
4. If multiple jobs match or none match, return a clarifying chat response instead of generating a CV.

The resolver should not invent jobs and should not search the full database for vague references in this milestone.

## API Shape

Extend `ChatRequest` with:

```python
selected_job_id: UUID | None = None
```

Extend `ChatResponse` with:

```python
artifacts: list[ChatArtifact] = Field(default_factory=list)
```

Introduce a chat artifact model with a first artifact type:

```python
class ChatArtifact(BaseModel):
    type: Literal["tailored_cv_latex"]
    job_id: UUID
    title: str | None = None
    filename: str | None = None
    artifact_id: str | None = None
    pdf_available: bool = False
    pdf_filename: str | None = None
    selected_length: Literal["one_page", "two_page"] | None = None
    length_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
```

The existing `jobs`, `ranked_jobs`, and `warnings` fields stay unchanged.

## Frontend Shape

Add `selected_job_id` to the chat payload when the active route is `/chat/jobs/:jobId`.

Persist artifact metadata on assistant messages in the thread state. Render `tailored_cv_latex` artifacts below the assistant response with:

- Generated filename.
- Selected length and length reason.
- Warnings.
- Download PDF button when `pdf_available` and `artifact_id` are present.
- Link/button to open the existing job details or CV pane for review.

Do not move TailoredCVPane into chat in this milestone. Reuse it as the review/edit fallback through navigation.

## Error Handling

- Missing candidate evidence: return a chat response explaining that candidate evidence must be added or reindexed before tailoring a CV.
- Missing selected target profile: use the current default target profile behavior where available; otherwise explain that Scout needs a target profile or candidate evidence.
- Unresolvable job reference: ask the user to click a job card or refer to a numbered recent result.
- LaTeX bridge unavailable: still return the `.tex` artifact metadata and include the existing warning that PDF validation/compilation was skipped.
- Job not found: return a warning and ask the user to select a current job card.

## Streaming Events

The stream should emit clear progress events that fit the existing `ActivityTimeline`:

- Interpret request.
- Resolve selected job.
- Generate tailored CV.
- Compile or skip LaTeX/PDF.
- Prepare artifact response.

Failures should use existing `step_failed` or `tool_failed` style events where possible.

## Testing And Verification

Service-level tests or smoke checks should cover:

- `selected_job_id` resolves when the user says `tailor my CV for this`.
- `job 2` resolves to the second recent chat result.
- Company/title text resolves when it uniquely matches a recent result.
- Ambiguous or missing references produce a clarifying response.
- Successful generation returns a `tailored_cv_latex` artifact.
- LaTeX bridge unavailable still returns artifact metadata with warnings.

Frontend checks should cover:

- Chat payload includes `selected_job_id` on `/chat/jobs/:jobId`.
- Assistant messages retain and render artifacts.
- Artifact PDF download URL uses the existing `/jobs/{job_id}/tailored-cv/latex/{artifact_id}/pdf` path.

Run available safe checks after implementation:

```bash
uv run python -m compileall main.py apps packages
```

For web changes, run from `apps/web`:

```bash
pnpm run build
```

## Scope Boundary

Expected implementation files include:

- `apps/api/schemas.py`
- `apps/api/routes/chat.py`
- `packages/services/src/services/job_workflow_graph.py`
- `packages/services/src/services/chat_job_reference.py`
- `apps/web/src/App.jsx`
- `apps/web/src/features/chat/chatStreamReducer.js`
- `apps/web/src/features/chat/ChatMessage.jsx`
- `apps/web/src/api.js`

Avoid broad navigation changes, sidebar removal, candidate editing through chat, and settings orchestration in this milestone.
