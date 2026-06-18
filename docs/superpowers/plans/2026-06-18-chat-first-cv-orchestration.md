# Chat-First CV Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users select or reference a job from chat and generate tailored CV LaTeX/PDF artifacts directly through the chat flow.

**Architecture:** Extend the existing `/chat` LangGraph workflow instead of replacing it. Add a focused job-reference resolver service, thread artifact fields in `ChatResult`/API schemas, call the existing `draft_tailored_cv_latex` service from a new CV-specialist graph path, and render returned artifacts in chat while keeping existing Jobs/CV panes available.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, LangGraph, React/Vite, pnpm, existing Scout service packages.

---

## File Structure

- Modify `packages/services/src/services/chat.py`: add non-`None` `artifacts` to `ChatResult` so service results can carry chat artifact metadata.
- Create `packages/services/src/services/chat_job_reference.py`: resolve selected/referenced jobs from selected context and recent chat history.
- Modify `apps/api/schemas.py`: add recent job metadata to `ChatMessage`, add `selected_job_id` to `ChatRequest`, add `ChatArtifact`, and add `artifacts` to `ChatResponse`.
- Modify `apps/api/routes/chat.py`: pass `selected_job_id` into sync and streaming chat graph calls.
- Modify `packages/services/src/services/job_workflow_graph.py`: add state field, route CV-tailoring requests, call the resolver and CV service, and return artifacts.
- Modify `apps/web/src/App.jsx`: include selected chat job ID in chat requests and persist cloned artifact metadata in threads.
- Modify `apps/web/src/features/chat/chatStreamReducer.js`: carry streamed `artifacts` onto assistant messages.
- Modify `apps/web/src/features/chat/ChatMessage.jsx`: render tailored CV artifact cards with warnings, length metadata, and download/open links.

## Task 1: Add Chat Artifact Data Shape

**Files:**
- Modify: `packages/services/src/services/chat.py`
- Modify: `apps/api/schemas.py`

- [ ] **Step 1: Update service result dataclass**

In `packages/services/src/services/chat.py`, change the dataclasses import to include `field`:

```python
from dataclasses import dataclass, field
```

Then update `ChatResult` near the top of the file to include artifacts:

```python
@dataclass
class ChatResult:
    message: str
    tool: str
    jobs: list[dict] | None = None
    ranked_jobs: list[dict] | None = None
    warnings: list[str] | None = None
    artifacts: list[dict] = field(default_factory=list)
```

This must preserve existing call sites because `artifacts` defaults to an empty list.

- [ ] **Step 2: Add API request and response artifact fields**

In `apps/api/schemas.py`, replace the current chat message/request/response section with this shape while preserving existing field order where practical:

```python
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    ranked_jobs: list[dict[str, Any]] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    target_profile_id: UUID | None = None
    profile_id: UUID | None = None
    selected_job_id: UUID | None = None
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(default=5, ge=1, le=10)


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


class ChatResponse(BaseModel):
    message: str
    tool: Literal[
        "search_jobs",
        "rank_jobs_for_profile",
        "list_profiles",
        "get_profile",
        "get_job_corpus_status",
        "import_adzuna_jobs",
        "fetch_job_offers",
        "tailored_cv_latex",
        "none",
    ]
    jobs: list[SearchResult] = Field(default_factory=list)
    ranked_jobs: list["RankedJobResult"] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    artifacts: list[ChatArtifact] = Field(default_factory=list)
```

- [ ] **Step 3: Run schema smoke check**

Run:

```bash
uv run python - <<'PY'
from uuid import uuid4
from apps.api.schemas import ChatArtifact, ChatRequest, ChatResponse

job_id = uuid4()
request = ChatRequest(
    message="tailor this",
    selected_job_id=job_id,
    history=[{"role": "assistant", "content": "Found jobs", "jobs": [{"id": str(job_id), "title": "Engineer"}]}],
)
assert request.selected_job_id == job_id
assert request.history[0].jobs[0]["title"] == "Engineer"

artifact = ChatArtifact(type="tailored_cv_latex", job_id=job_id, filename="cv.tex", selected_length="one_page")
response = ChatResponse(message="Generated CV", tool="tailored_cv_latex", artifacts=[artifact])
assert response.artifacts[0].filename == "cv.tex"
print("chat schema ok")
PY
```

Expected: exits 0 and prints `chat schema ok`.

- [ ] **Step 4: Commit Task 1**

Run:

```bash
git add packages/services/src/services/chat.py apps/api/schemas.py
git commit -m "feat: add chat artifact shape"
```

## Task 2: Add Job Reference Resolver

**Files:**
- Create: `packages/services/src/services/chat_job_reference.py`

- [ ] **Step 1: Create resolver module**

Create `packages/services/src/services/chat_job_reference.py` with this content:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResolvedChatJob:
    job_id: str
    title: str | None = None
    company: str | None = None


@dataclass(frozen=True)
class JobReferenceResolution:
    job: ResolvedChatJob | None
    reason: str
    needs_clarification: bool = False


def resolve_chat_job_reference(*, message: str, history: list[dict[str, Any]], selected_job_id: str | None = None) -> JobReferenceResolution:
    recent_jobs = _recent_jobs(history)
    normalized = _normalized(message)
    if selected_job_id and (_uses_selected_reference(normalized) or not _has_explicit_reference(normalized)):
        return JobReferenceResolution(job=_selected_job(selected_job_id, recent_jobs), reason="Used the currently selected chat job.")

    ordinal = _ordinal_reference(normalized)
    if ordinal is not None:
        if 0 <= ordinal < len(recent_jobs):
            return JobReferenceResolution(job=_job_from_result(recent_jobs[ordinal]), reason=f"Resolved job {ordinal + 1} from recent chat results.")
        return JobReferenceResolution(job=None, reason=f"I could not find job {ordinal + 1} in the recent chat results.", needs_clarification=True)

    matches = _text_matches(normalized, recent_jobs)
    if len(matches) == 1:
        return JobReferenceResolution(job=_job_from_result(matches[0]), reason="Resolved the job from a title or company mention in recent chat results.")
    if len(matches) > 1:
        return JobReferenceResolution(job=None, reason="I found multiple recent jobs matching that reference.", needs_clarification=True)

    if selected_job_id:
        return JobReferenceResolution(job=_selected_job(selected_job_id, recent_jobs), reason="Used the currently selected chat job.")
    return JobReferenceResolution(job=None, reason="I could not tell which job to use for the CV.", needs_clarification=True)


def _recent_jobs(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in reversed(history[-12:]):
        jobs = item.get("ranked_jobs") or item.get("rankedJobs") or item.get("jobs") or []
        if isinstance(jobs, list) and jobs:
            return [job for job in jobs if isinstance(job, dict) and (job.get("id") or job.get("job_id"))]
    return []


def _selected_job(selected_job_id: str, recent_jobs: list[dict[str, Any]]) -> ResolvedChatJob:
    for item in recent_jobs:
        if str(item.get("id") or item.get("job_id")) == selected_job_id:
            return _job_from_result(item)
    return ResolvedChatJob(job_id=selected_job_id)


def _job_from_result(item: dict[str, Any]) -> ResolvedChatJob:
    return ResolvedChatJob(job_id=str(item.get("id") or item.get("job_id")), title=_string(item.get("title")), company=_string(item.get("company")))


def _uses_selected_reference(normalized: str) -> bool:
    return any(phrase in normalized for phrase in ("this", "this one", "selected job", "open job", "current job"))


def _has_explicit_reference(normalized: str) -> bool:
    return _ordinal_reference(normalized) is not None or bool(re.search(r"\b(the\s+)?[a-z0-9][a-z0-9&.,+-]*(\s+[a-z0-9][a-z0-9&.,+-]*){0,4}\s+(role|job)\b", normalized))


def _ordinal_reference(normalized: str) -> int | None:
    match = re.search(r"\b(?:job|role|option|result)\s*(\d{1,2})\b", normalized)
    if match:
        return int(match.group(1)) - 1
    words = {
        "first": 0,
        "1st": 0,
        "second": 1,
        "2nd": 1,
        "third": 2,
        "3rd": 2,
        "fourth": 3,
        "4th": 3,
        "fifth": 4,
        "5th": 4,
    }
    for word, index in words.items():
        if re.search(rf"\b{re.escape(word)}\b", normalized):
            return index
    return None


def _text_matches(normalized: str, recent_jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = []
    for item in recent_jobs:
        title = _normalized(_string(item.get("title")) or "")
        company = _normalized(_string(item.get("company")) or "")
        if (company and company in normalized) or (title and title in normalized):
            matches.append(item)
    return matches


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9&.,+\s-]", " ", value.lower())).strip()


def _string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
```

- [ ] **Step 2: Run resolver smoke check**

Run:

```bash
uv run python - <<'PY'
from services.chat_job_reference import resolve_chat_job_reference

history = [{
    "role": "assistant",
    "content": "Found jobs",
    "jobs": [
        {"id": "job-a", "title": "Backend Developer", "company": "Acme"},
        {"id": "job-b", "title": "Python Engineer", "company": "Revolut"},
    ],
}]

assert resolve_chat_job_reference(message="tailor CV for job 2", history=history).job.job_id == "job-b"
assert resolve_chat_job_reference(message="tailor the Revolut role", history=history).job.job_id == "job-b"
assert resolve_chat_job_reference(message="tailor this", history=history, selected_job_id="job-a").job.job_id == "job-a"
assert resolve_chat_job_reference(message="tailor job 4", history=history).needs_clarification is True
print("resolver ok")
PY
```

Expected: exits 0 and prints `resolver ok`.

- [ ] **Step 3: Commit Task 2**

Run:

```bash
git add packages/services/src/services/chat_job_reference.py
git commit -m "feat: resolve chat job references"
```

## Task 3: Wire CV Specialist Into Chat Graph

**Files:**
- Modify: `apps/api/routes/chat.py`
- Modify: `packages/services/src/services/job_workflow_graph.py`

- [ ] **Step 1: Pass selected job ID from API route**

In `apps/api/routes/chat.py`, pass `selected_job_id` into both graph calls:

```python
        selected_job_id=str(request.selected_job_id) if request.selected_job_id else None,
```

The sync call should become:

```python
    result = respond_to_chat_with_graph(
        message=request.message,
        history=[message.model_dump() for message in request.history],
        target_profile_id=target_profile_id,
        profile_id=str(request.profile_id) if request.profile_id else None,
        selected_job_id=str(request.selected_job_id) if request.selected_job_id else None,
        filters=JobSearchFilters(**request.filters.model_dump()),
        limit=request.limit,
    )
```

Make the same addition in `_chat_event_stream` for `stream_chat_with_graph`.

- [ ] **Step 2: Extend graph function signatures and state**

In `packages/services/src/services/job_workflow_graph.py`, add imports:

```python
from .application_latex import draft_tailored_cv_latex
from .application_materials import CandidateEvidenceUnavailableError, JobForApplicationNotFoundError, TailoredCVGenerationError
from .chat_job_reference import resolve_chat_job_reference
```

Add `selected_job_id` to `JobWorkflowState`:

```python
    selected_job_id: str | None
```

Add `selected_job_id: str | None = None` to `respond_to_chat_with_graph`, `stream_chat_with_graph`, and `_input_state`, and include it in the state dict:

```python
        "selected_job_id": selected_job_id,
```

- [ ] **Step 3: Include artifacts in state conversion**

Update `_chat_result_from_state` to pass artifacts:

```python
    return ChatResult(
        message=str(result.get("message") or "What would you like to do next?"),
        tool=str(result.get("tool") or "none"),
        jobs=_dict_list(result.get("jobs")),
        ranked_jobs=_dict_list(result.get("ranked_jobs")),
        warnings=_string_list(result.get("warnings")),
        artifacts=_dict_list(result.get("artifacts")),
    )
```

- [ ] **Step 4: Add CV intent helpers near existing route helpers**

Add these helpers near `_is_adzuna_import_request`:

```python
def _is_tailor_cv_request(message: str) -> bool:
    normalized = message.lower()
    has_cv = any(phrase in normalized for phrase in ("cv", "resume", "application"))
    has_action = any(word in normalized for word in ("tailor", "generate", "draft", "write", "create", "make", "export"))
    return has_cv and has_action


def _cv_length_from_message(message: str) -> str:
    normalized = message.lower()
    if "two page" in normalized or "two-page" in normalized or "2 page" in normalized or "2-page" in normalized:
        return "two_page"
    if "one page" in normalized or "one-page" in normalized or "1 page" in normalized or "1-page" in normalized:
        return "one_page"
    return "auto"
```

- [ ] **Step 5: Route CV requests to a new graph node**

In `route_initial`, add this check after `route_name = route.get("route")` and before job-search routing:

```python
        if _is_tailor_cv_request(message):
            return "tailor_cv"
```

Add node registration and edge:

```python
    builder.add_node("tailor_cv", tailor_cv_node)
```

And include it in the conditional map:

```python
            "tailor_cv": "tailor_cv",
```

Add terminal edge:

```python
    builder.add_edge("tailor_cv", END)
```

- [ ] **Step 6: Add CV-specialist node**

Inside `build_job_workflow_graph`, before node registration, add:

```python
    def tailor_cv_node(state: JobWorkflowState) -> dict[str, Any]:
        _emit({"type": "step_started", "id": "resolve_job", "title": "Resolve selected job"})
        resolution = resolve_chat_job_reference(
            message=state.get("message", ""),
            history=state.get("history") or [],
            selected_job_id=state.get("selected_job_id"),
        )
        if resolution.job is None:
            _emit({"type": "step_completed", "id": "resolve_job", "summary": "Job selection needed"})
            return {
                "result": {
                    "message": "Which job should I tailor the CV for? Click a job card, or refer to a recent result like `job 1` or `job 2`.",
                    "tool": "none",
                    "jobs": [],
                    "ranked_jobs": [],
                    "warnings": [resolution.reason],
                    "artifacts": [],
                }
            }

        _emit({"type": "step_completed", "id": "resolve_job", "summary": resolution.reason})
        _emit({"type": "step_started", "id": "tailor_cv", "title": "Generate tailored CV"})
        try:
            artifact = draft_tailored_cv_latex(
                resolution.job.job_id,
                target_profile_id=state.get("target_profile_id") or state.get("profile_id"),
                instruction=state.get("message") or None,
                evidence_limit=8,
                length=_cv_length_from_message(state.get("message", "")),
            )
        except JobForApplicationNotFoundError:
            _emit({"type": "tool_failed", "id": "tailor_cv", "summary": "Job not found"})
            return {
                "result": {
                    "message": "I could not find that job anymore. Please select a current job card and try again.",
                    "tool": "tailored_cv_latex",
                    "jobs": [],
                    "ranked_jobs": [],
                    "warnings": ["Job not found."],
                    "artifacts": [],
                }
            }
        except CandidateEvidenceUnavailableError as exc:
            _emit({"type": "tool_failed", "id": "tailor_cv", "summary": "Candidate evidence unavailable"})
            return {
                "result": {
                    "message": "I need indexed candidate evidence before I can tailor a CV. Add or reindex candidate evidence, then ask me again.",
                    "tool": "tailored_cv_latex",
                    "jobs": [],
                    "ranked_jobs": [],
                    "warnings": [str(exc)],
                    "artifacts": [],
                }
            }
        except TailoredCVGenerationError as exc:
            _emit({"type": "tool_failed", "id": "tailor_cv", "summary": "CV generation failed"})
            return {
                "result": {
                    "message": "I could not generate the tailored CV. Try a shorter instruction or check the model connection.",
                    "tool": "tailored_cv_latex",
                    "jobs": [],
                    "ranked_jobs": [],
                    "warnings": [str(exc)],
                    "artifacts": [],
                }
            }

        chat_artifact = {
            "type": "tailored_cv_latex",
            "job_id": resolution.job.job_id,
            "title": resolution.job.title,
            "filename": artifact.get("filename"),
            "artifact_id": artifact.get("artifact_id"),
            "pdf_available": bool(artifact.get("pdf_available")),
            "pdf_filename": artifact.get("pdf_filename"),
            "selected_length": artifact.get("selected_length"),
            "length_reason": artifact.get("length_reason"),
            "warnings": artifact.get("warnings") or [],
        }
        _emit({"type": "tool_completed", "id": "tailor_cv", "summary": f"Generated {artifact.get('filename') or 'tailored CV LaTeX'}"})
        _emit({"type": "step_completed", "id": "tailor_cv", "summary": "Prepared CV artifact"})
        message = "I generated a tailored CV export for the selected job."
        if artifact.get("pdf_available"):
            message += " The PDF is ready to download."
        else:
            message += " The LaTeX source is ready; PDF compilation was skipped or unavailable."
        return {
            "result": {
                "message": message,
                "tool": "tailored_cv_latex",
                "jobs": [],
                "ranked_jobs": [],
                "warnings": artifact.get("warnings") or [],
                "artifacts": [chat_artifact],
            }
        }
```

- [ ] **Step 7: Run backend smoke checks**

Run:

```bash
uv run python - <<'PY'
from apps.api.schemas import ChatResponse
from services.job_workflow_graph import _is_tailor_cv_request, _cv_length_from_message

assert _is_tailor_cv_request("tailor my CV for this") is True
assert _is_tailor_cv_request("find python jobs") is False
assert _cv_length_from_message("make a two-page CV") == "two_page"
response = ChatResponse(message="ok", tool="tailored_cv_latex", artifacts=[])
assert response.tool == "tailored_cv_latex"
print("backend graph shape ok")
PY
```

Expected: exits 0 and prints `backend graph shape ok`.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add apps/api/routes/chat.py packages/services/src/services/job_workflow_graph.py
git commit -m "feat: route chat CV tailoring"
```

## Task 4: Render Chat Artifacts In The Web App

**Files:**
- Modify: `apps/web/src/App.jsx`
- Modify: `apps/web/src/features/chat/chatStreamReducer.js`
- Modify: `apps/web/src/features/chat/ChatMessage.jsx`

- [ ] **Step 1: Include selected job ID in chat payload**

In `apps/web/src/App.jsx`, add `selected_job_id: selectedChatJobId,` to the payload created in `submitMessage`:

```javascript
      const payload = {
        message: content,
        history: history
          .filter((message) => message.role === 'user' || message.role === 'assistant')
          .map((message) => ({
            role: message.role,
            content: message.content,
            jobs: message.jobs || [],
            ranked_jobs: message.rankedJobs || [],
          })),
        target_profile_id: selectedProfileId,
        selected_job_id: selectedChatJobId,
        filters: {
          location: null,
          contract_type: null,
          company: null,
          seniority: null,
          remote_policy: null,
        },
        limit: 5,
      }
```

Also update `cloneMessages` to clone artifacts:

```javascript
    artifacts: message.artifacts ? message.artifacts.map((artifact) => ({ ...artifact, warnings: artifact.warnings ? [...artifact.warnings] : [] })) : message.artifacts,
```

- [ ] **Step 2: Carry artifacts in stream reducer**

In `apps/web/src/features/chat/chatStreamReducer.js`, update the `done` event merge so the assistant message stores artifacts:

```javascript
              artifacts: response.artifacts || [],
```

Place it next to the existing `jobs`, `rankedJobs`, and `warnings` assignments.

- [ ] **Step 3: Reuse artifact URL helper**

Use the existing `tailoredCvLatexPdfUrl(jobId, artifactId)` helper from `apps/web/src/api.js`. Do not modify `api.js` for this task.

- [ ] **Step 4: Render artifacts in chat messages**

In `apps/web/src/features/chat/ChatMessage.jsx`, import the PDF URL helper and `Link`:

```javascript
import { Link } from 'react-router-dom'
import { tailoredCvLatexPdfUrl } from '../../api.js'
```

Then render artifacts after result jobs:

```javascript
      {message.artifacts?.length > 0 && (
        <div className="chat-artifact-list">
          {message.artifacts.map((artifact) => (
            <ChatArtifactCard key={`${artifact.type}-${artifact.job_id}-${artifact.artifact_id || artifact.filename}`} artifact={artifact} />
          ))}
        </div>
      )}
```

Add this component at the bottom of the file:

```javascript
function ChatArtifactCard({ artifact }) {
  if (artifact.type !== 'tailored_cv_latex') return null
  return (
    <section className="chat-artifact-card">
      <div>
        <p>Tailored CV export</p>
        <h3>{artifact.filename || 'tailored-cv.tex'}</h3>
        {artifact.selected_length && <span>{artifact.selected_length.replace('_', ' ')}</span>}
        {artifact.length_reason && <small>{artifact.length_reason}</small>}
      </div>
      <div className="chat-artifact-actions">
        {artifact.pdf_available && artifact.artifact_id && (
          <a href={tailoredCvLatexPdfUrl(artifact.job_id, artifact.artifact_id)} download={artifact.pdf_filename || undefined}>Download PDF</a>
        )}
        <Link to={`/jobs/${artifact.job_id}/tailor-cv`}>Open CV pane</Link>
      </div>
      {artifact.warnings?.length > 0 && (
        <ul>
          {artifact.warnings.map((warning) => <li key={warning}>{warning}</li>)}
        </ul>
      )}
    </section>
  )
}
```

- [ ] **Step 5: Run frontend build**

Run:

```bash
pnpm run build
```

from `apps/web`.

Expected: production build exits 0.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add apps/web/src/App.jsx apps/web/src/features/chat/chatStreamReducer.js apps/web/src/features/chat/ChatMessage.jsx
git commit -m "feat: render chat CV artifacts"
```

## Task 5: Final Verification And Graph Update

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run full Python safe check**

Run:

```bash
uv run python -m compileall main.py apps packages
```

Expected: exits 0. Output can be noisy because it may traverse `apps/web/node_modules`, but there must be no Python syntax errors.

- [ ] **Step 2: Run web build again**

Run:

```bash
pnpm run build
```

from `apps/web`.

Expected: exits 0.

- [ ] **Step 3: Run graphify update**

Run:

```bash
graphify update .
```

Expected: graph update completes. Generated `graphify-out` files are ignored and should not be committed.

- [ ] **Step 4: Check status and recent commits**

Run:

```bash
git status --short
git log --oneline -8
```

Expected: working tree is clean and recent commits include Tasks 1-4.

- [ ] **Step 5: Report final result**

Tell the user:

```text
Implemented chat-first CV orchestration milestone.

Commits:
- feat: add chat artifact shape
- feat: resolve chat job references
- feat: route chat CV tailoring
- feat: render chat CV artifacts

Verification:
- chat schema smoke check passed
- resolver smoke check passed
- backend graph shape smoke check passed
- uv compileall passed
- web production build passed
- graphify update completed
```
