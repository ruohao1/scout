# Classic Compact CV Length Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit one-page, two-page, and automatic length selection to Classic Compact tailored CV LaTeX generation.

**Architecture:** Keep the current two-layer flow: `application_materials.py` generates evidence-backed CV content, and `application_latex.py` plans and renders layout. Add a deterministic length planner in `application_latex.py`, expose `length` through API schemas/routes, and return `selected_length` plus `length_reason` in the LaTeX response.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, uv workspace packages, LaTeX string rendering.

---

## File Structure

- Modify `apps/api/schemas.py`: add request/response fields and `Literal` typing for CV length.
- Modify `apps/api/routes/jobs.py`: pass `request.length` into `draft_tailored_cv_latex`.
- Modify `packages/services/src/services/application_latex.py`: add length types/constants, deterministic planner, dynamic limits, planner metadata in the response, and length-aware warnings.
- Do not modify `packages/services/src/services/application_materials.py` unless implementation reveals a direct layout-output bug.

## Task 1: Add API Length Fields

**Files:**
- Modify: `apps/api/schemas.py`

- [ ] **Step 1: Update `TailoredCVLatexRequest` and `TailoredCVLatexRead`**

In `apps/api/schemas.py`, `Literal` is already imported on line 4. Replace the current `TailoredCVLatexRequest` and extend `TailoredCVLatexRead` like this:

```python
class TailoredCVLatexRequest(TailoredCVRequest):
    template_id: str | None = None
    length: Literal["one_page", "two_page", "auto"] = "auto"


class TailoredCVLatexRead(BaseModel):
    filename: str
    latex: str
    template_id: str
    selected_length: Literal["one_page", "two_page"]
    length_reason: str
    warnings: list[str] = Field(default_factory=list)
    artifact_id: str | None = None
    validation: dict[str, Any] | None = None
    compile: dict[str, Any] | None = None
    compiled: bool = False
    pdf_filename: str | None = None
    pdf_available: bool = False
```

- [ ] **Step 2: Run schema import check**

Run:

```bash
uv run python - <<'PY'
from apps.api.schemas import TailoredCVLatexRead, TailoredCVLatexRequest

request = TailoredCVLatexRequest(length="auto")
assert request.length == "auto"

response = TailoredCVLatexRead(
    filename="candidate.tex",
    latex="\\documentclass{article}",
    template_id="classic_cv",
    selected_length="one_page",
    length_reason="Explicit one-page CV requested.",
)
assert response.selected_length == "one_page"
print("schema ok")
PY
```

Expected: command exits 0 and prints `schema ok`.

- [ ] **Step 3: Commit schema change**

Run:

```bash
git add apps/api/schemas.py
git commit -m "feat: expose CV length fields"
```

## Task 2: Pass Length Through The Route

**Files:**
- Modify: `apps/api/routes/jobs.py`

- [ ] **Step 1: Pass request length to the service**

In `apps/api/routes/jobs.py`, update the `draft_tailored_cv_latex` call in `tailor_cv_latex_for_job` to include `length=request.length`:

```python
        return draft_tailored_cv_latex(
            str(job_id),
            target_profile_id=str(request.target_profile_id) if request.target_profile_id else None,
            instruction=request.instruction,
            evidence_limit=request.evidence_limit,
            template_id=request.template_id,
            length=request.length,
        )
```

- [ ] **Step 2: Run route import check**

Run:

```bash
uv run python - <<'PY'
from apps.api.routes.jobs import tailor_cv_latex_for_job

assert callable(tailor_cv_latex_for_job)
print("route ok")
PY
```

Expected: command exits 0 and prints `route ok`.

- [ ] **Step 3: Commit route change**

Run:

```bash
git add apps/api/routes/jobs.py
git commit -m "feat: pass CV length to latex renderer"
```

## Task 3: Add Deterministic Length Planner

**Files:**
- Modify: `packages/services/src/services/application_latex.py`

- [ ] **Step 1: Add length constants near the existing constants**

Replace the existing one-page constants block with length-aware constants:

```python
DEFAULT_TEMPLATE_ID = "classic_cv"
DEFAULT_LATEX_ENGINE = "pdflatex"
DEFAULT_CV_LENGTH = "auto"
CV_LENGTHS = {"one_page", "two_page", "auto"}
SENIORITY_TWO_PAGE_TERMS = (
    "senior",
    "lead",
    "principal",
    "staff",
    "head",
    "manager",
    "director",
    "vp",
    "chief",
)

ONE_PAGE_LIMITS = {
    "bullets": 6,
    "education": 1,
    "projects": 2,
    "achievements": 2,
    "skills": 20,
    "description_limit": 160,
}
TWO_PAGE_LIMITS = {
    "bullets": 8,
    "education": 2,
    "projects": 4,
    "achievements": 4,
    "skills": 32,
    "description_limit": 260,
}
AUTO_TWO_PAGE_EVIDENCE_THRESHOLD = 10
AUTO_TWO_PAGE_BULLET_THRESHOLD = 7
```

- [ ] **Step 2: Update the service signature and response metadata**

Change `draft_tailored_cv_latex` to accept `length` and return planner metadata:

```python
def draft_tailored_cv_latex(
    job_id: str,
    *,
    target_profile_id: str | None = None,
    instruction: str | None = None,
    evidence_limit: int = 8,
    template_id: str | None = None,
    length: str = DEFAULT_CV_LENGTH,
) -> dict[str, Any]:
```

Then change the context call and return body:

```python
    context = _latex_context(draft=draft, job=job or {}, candidate=candidate or {}, requested_length=length)
    latex = _render_template(selected_template, context)
    artifact = _validate_and_compile_latex(latex=latex, filename=_latex_filename(job=job or {}, candidate=candidate or {}))
    return {
        "filename": artifact["filename"],
        "latex": latex,
        "template_id": selected_template,
        "selected_length": context["selected_length"],
        "length_reason": context["length_reason"],
        "warnings": [
            "Generated from retrieved candidate evidence. Review and compile externally before submitting.",
            *context["warnings"],
            *artifact["warnings"],
        ],
        "artifact_id": artifact["artifact_id"],
        "validation": artifact["validation"],
        "compile": artifact["compile"],
        "compiled": artifact["compiled"],
        "pdf_filename": artifact["pdf_filename"],
        "pdf_available": artifact["pdf_available"],
    }
```

- [ ] **Step 3: Add planner helpers below `_latex_output_dir`**

Insert these helpers before `_latex_context`:

```python
def _latex_context(*, draft: dict[str, Any], job: dict[str, Any], candidate: dict[str, Any], requested_length: str) -> dict[str, Any]:
    evidence_items = _ranked_evidence_items(draft)
    plan = _cv_length_plan(requested_length=requested_length, job=job, draft=draft, evidence_items=evidence_items)
    planned = _plan_cv(draft=draft, job=job, evidence_items=evidence_items, limits=plan["limits"])
    return {
        "candidate": candidate,
        "job": job,
        "draft": draft,
        "selected_length": plan["selected_length"],
        "length_reason": plan["length_reason"],
        "bullets": planned["bullets"],
        "evidence_by_type": _group_evidence_by_type(planned["evidence_items"]),
        "skills": planned["skills"],
        "warnings": planned["warnings"],
    }


def _cv_length_plan(*, requested_length: str, job: dict[str, Any], draft: dict[str, Any], evidence_items: list[dict[str, Any]]) -> dict[str, Any]:
    if requested_length not in CV_LENGTHS:
        requested_length = DEFAULT_CV_LENGTH
    if requested_length == "one_page":
        return {
            "selected_length": "one_page",
            "length_reason": "Explicit one-page CV requested.",
            "limits": ONE_PAGE_LIMITS,
        }
    if requested_length == "two_page":
        return {
            "selected_length": "two_page",
            "length_reason": "Explicit two-page CV requested.",
            "limits": TWO_PAGE_LIMITS,
        }

    seniority_reason = _two_page_seniority_reason(job)
    evidence_count = len(evidence_items)
    bullet_count = len(draft.get("bullets") or [])
    if seniority_reason:
        return {
            "selected_length": "two_page",
            "length_reason": seniority_reason,
            "limits": TWO_PAGE_LIMITS,
        }
    if evidence_count >= AUTO_TWO_PAGE_EVIDENCE_THRESHOLD or bullet_count >= AUTO_TWO_PAGE_BULLET_THRESHOLD:
        return {
            "selected_length": "two_page",
            "length_reason": f"Auto-selected two pages because the draft has {bullet_count} bullets and {evidence_count} ranked evidence items.",
            "limits": TWO_PAGE_LIMITS,
        }
    return {
        "selected_length": "one_page",
        "length_reason": f"Auto-selected one page because the role is not marked senior and the draft has {bullet_count} bullets with {evidence_count} ranked evidence items.",
        "limits": ONE_PAGE_LIMITS,
    }


def _two_page_seniority_reason(job: dict[str, Any]) -> str | None:
    seniority_text = " ".join(str(value or "") for value in [job.get("seniority"), job.get("title")]).lower()
    matched = next((term for term in SENIORITY_TWO_PAGE_TERMS if re.search(rf"\b{re.escape(term)}\b", seniority_text)), None)
    if not matched:
        return None
    return f"Auto-selected two pages because the role appears senior-level from '{matched}'."
```

Then delete the old `_latex_context` function to avoid duplicate definitions.

- [ ] **Step 4: Replace `_plan_one_page_cv` with `_plan_cv`**

Replace the existing `_plan_one_page_cv` function with:

```python
def _plan_cv(*, draft: dict[str, Any], job: dict[str, Any], evidence_items: list[dict[str, Any]], limits: dict[str, int]) -> dict[str, Any]:
    bullets = list(draft.get("bullets") or [])[: limits["bullets"]]
    grouped = _group_evidence_by_type(evidence_items)
    selected_evidence = [
        *_fit_evidence_items(grouped.get("education", [])[: limits["education"]], description_limit=limits["description_limit"]),
        *_fit_evidence_items(grouped.get("project", [])[: limits["projects"]], description_limit=limits["description_limit"]),
        *grouped.get("certification", [])[: limits["achievements"]],
    ]
    remaining_achievement_slots = limits["achievements"] - len([item for item in selected_evidence if _evidence_type(item) == "certification"])
    if remaining_achievement_slots > 0:
        selected_evidence.extend(grouped.get("achievement", [])[:remaining_achievement_slots])

    skills = _unique_skills(job=job, evidence_items=[*_referenced_evidence_items(bullets, evidence_items), *selected_evidence])
    warnings = _cv_length_warnings(
        original_bullet_count=len(draft.get("bullets") or []),
        rendered_bullet_count=len(bullets),
        original_evidence_count=len(evidence_items),
        rendered_evidence_count=len(selected_evidence),
        original_skill_count=len(_unique_skills(job=job, evidence_items=evidence_items)),
        rendered_skill_count=min(len(skills), limits["skills"]),
    )
    return {
        "bullets": bullets,
        "evidence_items": selected_evidence,
        "skills": skills[: limits["skills"]],
        "warnings": warnings,
    }
```

- [ ] **Step 5: Make evidence fitting length-aware**

Replace `_fit_evidence_items` and `_fit_evidence_item` with:

```python
def _fit_evidence_items(items: list[dict[str, Any]], *, description_limit: int) -> list[dict[str, Any]]:
    return [_fit_evidence_item(item, description_limit=description_limit) for item in items]


def _fit_evidence_item(item: dict[str, Any], *, description_limit: int) -> dict[str, Any]:
    description = _clean_cv_text(item.get("description") or "")
    if len(description) <= description_limit:
        return item
    return {**item, "description": description[: description_limit - 1].rstrip() + "..."}
```

- [ ] **Step 6: Rename warning helper and make text length-neutral**

Replace `_one_page_warnings` with `_cv_length_warnings`:

```python
def _cv_length_warnings(
    *,
    original_bullet_count: int,
    rendered_bullet_count: int,
    original_evidence_count: int,
    rendered_evidence_count: int,
    original_skill_count: int,
    rendered_skill_count: int,
) -> list[str]:
    warnings = []
    if original_bullet_count > rendered_bullet_count:
        warnings.append(f"Omitted {original_bullet_count - rendered_bullet_count} lower-priority CV bullets to keep the PDF within the selected length.")
    if original_evidence_count > rendered_evidence_count:
        warnings.append(f"Omitted {original_evidence_count - rendered_evidence_count} lower-priority evidence items to keep the PDF within the selected length.")
    if original_skill_count > rendered_skill_count:
        warnings.append(f"Omitted {original_skill_count - rendered_skill_count} lower-priority skills to keep the PDF within the selected length.")
    return warnings
```

- [ ] **Step 7: Run planner smoke check**

Run:

```bash
uv run python - <<'PY'
from services.application_latex import _cv_length_plan

moderate = _cv_length_plan(
    requested_length="auto",
    job={"title": "Python Developer", "seniority": "mid"},
    draft={"bullets": [{"text": "a"}] * 4},
    evidence_items=[{"evidence_id": str(i), "type": "project"} for i in range(4)],
)
assert moderate["selected_length"] == "one_page", moderate

senior = _cv_length_plan(
    requested_length="auto",
    job={"title": "Senior Python Developer", "seniority": None},
    draft={"bullets": [{"text": "a"}] * 4},
    evidence_items=[{"evidence_id": str(i), "type": "project"} for i in range(4)],
)
assert senior["selected_length"] == "two_page", senior

rich = _cv_length_plan(
    requested_length="auto",
    job={"title": "Python Developer", "seniority": "mid"},
    draft={"bullets": [{"text": "a"}] * 8},
    evidence_items=[{"evidence_id": str(i), "type": "project"} for i in range(10)],
)
assert rich["selected_length"] == "two_page", rich

forced = _cv_length_plan(
    requested_length="two_page",
    job={"title": "Python Developer"},
    draft={"bullets": []},
    evidence_items=[],
)
assert forced["selected_length"] == "two_page", forced
print("planner ok")
PY
```

Expected: command exits 0 and prints `planner ok`.

- [ ] **Step 8: Run full syntax/import check**

Run:

```bash
uv run python -m compileall main.py apps packages
```

Expected: command exits 0. Output may be noisy if it traverses installed frontend dependencies under `apps/web/node_modules`, but there must be no Python syntax errors.

- [ ] **Step 9: Commit planner change**

Run:

```bash
git add packages/services/src/services/application_latex.py
git commit -m "feat: plan CV latex length"
```

## Task 4: Final Integration Verification

**Files:**
- Verify: `apps/api/schemas.py`
- Verify: `apps/api/routes/jobs.py`
- Verify: `packages/services/src/services/application_latex.py`

- [ ] **Step 1: Run response-shape smoke check with faked dependencies**

Run this direct service check from the repo root. It avoids the database and model provider by monkey-patching the dependencies inside `services.application_latex`:

```bash
uv run python - <<'PY'
from services import application_latex

class FakeJobs:
    def get(self, job_id):
        return {
            "id": job_id,
            "title": "Senior Python Developer",
            "company": "Example Ltd",
            "location": "London",
            "seniority": None,
            "skills": ["Python", "FastAPI"],
        }

class FakeCandidate:
    def get(self):
        return {"display_name": "Candidate", "email": "candidate@example.com"}

def fake_draft_tailored_cv(*args, **kwargs):
    return {
        "job_id": args[0],
        "target_profile_id": None,
        "headline": "Python Developer",
        "summary": "Builds reliable Python services for product teams.",
        "bullets": [{"text": f"Delivered evidence-backed service improvement {i}.", "evidence_ids": [str(i)]} for i in range(8)],
        "evidence_used": [],
        "gaps_or_cautions": [],
        "retrieved_evidence": [
            {"evidence_id": str(i), "type": "project", "title": f"Project {i}", "description": "Built a relevant system.", "skills": ["Python"], "score": 0.9}
            for i in range(10)
        ],
    }

def fake_validate_and_compile_latex(*, latex, filename):
    return {
        "artifact_id": "00000000-0000-0000-0000-000000000000",
        "filename": filename,
        "warnings": ["LaTeX MCP bridge is not configured; skipped validation and PDF compilation."],
        "validation": None,
        "compile": None,
        "compiled": False,
        "pdf_filename": None,
        "pdf_available": False,
    }

application_latex.JobRepository = FakeJobs
application_latex.CandidateRepository = FakeCandidate
application_latex.draft_tailored_cv = fake_draft_tailored_cv
application_latex._validate_and_compile_latex = fake_validate_and_compile_latex

result = application_latex.draft_tailored_cv_latex("job-1", length="auto")
assert result["selected_length"] == "two_page", result
assert "length_reason" in result and result["length_reason"], result
assert result["template_id"] == "classic_cv", result
assert result["latex"].strip().endswith("\\end{document}"), result["latex"]
print("integration ok")
PY
```

Expected: command exits 0 and prints `integration ok`.

- [ ] **Step 2: Run final status and diff checks**

Run:

```bash
git status --short
git diff --stat HEAD~3..HEAD
```

Expected: working tree is clean, and recent commits cover schema, route, and service changes.

- [ ] **Step 3: Report final result**

Tell the user:

```text
Implemented Classic Compact CV length selection.

Commits:
- feat: expose CV length fields
- feat: pass CV length to latex renderer
- feat: plan CV latex length

Verification:
- schema smoke check passed
- route import check passed
- planner smoke check passed
- compileall passed
- integration smoke check passed
```
