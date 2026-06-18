# Classic Compact CV Length Design

## Purpose

Improve tailored CV generation output by making the Classic Compact LaTeX export more polished and predictable for both one-page and two-page CVs. The first improvement targets layout and output behavior, not model prompt quality or frontend editing flows.

## Current State

The backend generates tailored CV content in `packages/services/src/services/application_materials.py` and renders LaTeX in `packages/services/src/services/application_latex.py`. The current LaTeX renderer always plans for a one-page output by applying fixed limits for bullets, education, projects, achievements, skills, and description length. The API exposes `POST /jobs/{job_id}/tailored-cv/latex` through `apps/api/routes/jobs.py`, with request and response schemas in `apps/api/schemas.py`.

## Goals

- Keep the existing `classic_cv` template direction: conservative, ATS-friendly, compact, and suitable for professional submission.
- Add explicit CV length control with `length: "one_page" | "two_page" | "auto"`.
- Make `auto` default to one page unless seniority or strong evidence volume justifies two pages.
- Return `selected_length` and `length_reason` so automatic behavior is easy to understand.
- Preserve current LaTeX bridge behavior: generated `.tex` should still be returned when validation or PDF compilation is unavailable.

## Non-Goals

- No new frontend preview or editing workflow in this iteration.
- No new user-facing template ID unless the implementation needs an internal distinction.
- No second model call to choose length or layout.
- No changes to candidate evidence indexing, retrieval embeddings, or target profile matching.

## API Design

Extend `TailoredCVLatexRequest` with:

```python
length: Literal["one_page", "two_page", "auto"] = "auto"
```

Extend `TailoredCVLatexRead` with:

```python
selected_length: Literal["one_page", "two_page"]
length_reason: str
```

Invalid length values should be rejected by Pydantic before reaching service code.

## Planner Design

Add a deterministic planner in `services.application_latex`. The planner accepts the requested length, job metadata, generated draft, and ranked evidence items. It returns:

- `selected_length`: `one_page` or `two_page`
- `length_reason`: human-readable explanation
- layout limits for bullets, education, projects, achievements, skills, and evidence description length

For `one_page`, use strict limits similar to the current behavior.

For `two_page`, allow more content while keeping the same Classic Compact visual language. Suggested initial limits are more bullets, more projects, more achievements, more education entries, and more skills, but still capped to prevent runaway output.

For `auto`, select one page by default. Select two pages when either of these is true:

- The job seniority appears senior, lead, principal, staff, head, manager, director, or similar.
- The retrieved/generated evidence volume is high enough to support a substantial CV without padding.

If both signals are weak or moderate, choose one page.

## Rendering Design

Keep the `classic_cv` template ID. Internally, pass the selected planner result into `_latex_context` and render the same sections with different limits.

One-page rendering should remain compact and omission-heavy when necessary.

Two-page rendering should include more evidence-backed content but stay conservative. It should not add decorative sidebar layouts, colors, or visual structures that reduce ATS friendliness.

Section order remains:

1. Header
2. Profile
3. Experience
4. Projects
5. Education
6. Achievements
7. Skills

## Warnings

Keep existing omission warnings for bullets, evidence items, and skills. The warning text should continue to explain that lower-priority content was omitted for the selected length.

When `auto` chooses one page, the response should still include a `length_reason` explaining why two pages were not selected.

## Error Handling

- Unknown template IDs continue to raise `TailoredCVLatexTemplateError`.
- Missing jobs and missing candidate evidence keep existing error behavior.
- LaTeX bridge failures remain non-fatal and return warnings.
- Invalid `length` values are schema validation errors.

## Testing And Verification

Add focused service-level tests if a test harness is available. The important cases are:

- Explicit `one_page` always selects one page.
- Explicit `two_page` always selects two pages.
- `auto` selects one page for moderate evidence and non-senior roles.
- `auto` selects two pages for senior roles or high evidence volume.
- The API response includes `selected_length` and `length_reason`.
- Existing LaTeX bridge skip behavior still returns generated `.tex` with a warning.

If there is no test harness, run the repository safe check:

```bash
uv run python -m compileall main.py apps packages
```

Also run a small direct Python smoke check of the planner behavior from the repo root.

## Implementation Boundary

This is primarily a backend service and schema change. Files expected to change are:

- `apps/api/schemas.py`
- `apps/api/routes/jobs.py`
- `packages/services/src/services/application_latex.py`

Avoid unrelated prompt changes in `application_materials.py` unless the implementation reveals a direct layout-output need.
