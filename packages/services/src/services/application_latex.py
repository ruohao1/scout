from __future__ import annotations

import re
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from db.candidate import CandidateRepository
from db.jobs import JobRepository

from .application_materials import draft_tailored_cv


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


class TailoredCVLatexTemplateError(ValueError):
    pass


SectionRenderer = Callable[[dict[str, Any]], str]


def draft_tailored_cv_latex(
    job_id: str,
    *,
    target_profile_id: str | None = None,
    instruction: str | None = None,
    evidence_limit: int = 8,
    template_id: str | None = None,
    length: str = DEFAULT_CV_LENGTH,
) -> dict[str, Any]:
    selected_template = template_id or DEFAULT_TEMPLATE_ID
    if selected_template not in TEMPLATES:
        raise TailoredCVLatexTemplateError(f"Unknown LaTeX template: {selected_template}")

    jobs = JobRepository()
    job = jobs.get(job_id)
    draft = draft_tailored_cv(
        job_id,
        target_profile_id=target_profile_id,
        instruction=instruction,
        evidence_limit=evidence_limit,
        jobs=jobs,
    )
    candidate = CandidateRepository().get()
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


def tailored_cv_latex_pdf_path(artifact_id: str) -> Path | None:
    if not re.fullmatch(r"[a-f0-9-]{36}", artifact_id):
        return None
    artifact_dir = _latex_output_dir() / artifact_id
    if not artifact_dir.exists():
        return None
    pdfs = sorted(path for path in artifact_dir.glob("*.pdf") if path.is_file())
    return pdfs[0] if pdfs else None


def _validate_and_compile_latex(*, latex: str, filename: str) -> dict[str, Any]:
    artifact_id = str(uuid4())
    artifact_dir = _latex_output_dir() / artifact_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    tex_path = artifact_dir / filename
    tex_path.write_text(latex, encoding="utf-8")

    relative_path = f"{artifact_id}/{filename}"
    bridge_result, warning = _call_latex_bridge(relative_path)
    warnings = [warning] if warning else []
    validation = bridge_result.get("validation") if bridge_result else None
    compile_result = bridge_result.get("compile") if bridge_result else None
    compiled = bool(compile_result and compile_result.get("success"))
    pdf_path = tex_path.with_suffix(".pdf")
    return {
        "artifact_id": artifact_id,
        "filename": filename,
        "warnings": warnings,
        "validation": validation,
        "compile": compile_result,
        "compiled": compiled,
        "pdf_filename": pdf_path.name if compiled else None,
        "pdf_available": compiled and pdf_path.exists(),
    }


def _call_latex_bridge(relative_path: str) -> tuple[dict[str, Any] | None, str | None]:
    bridge_url = os.environ.get("LATEX_BRIDGE_URL")
    if not bridge_url:
        return None, "LaTeX MCP bridge is not configured; skipped validation and PDF compilation."

    payload = json.dumps(
        {
            "file_path": relative_path,
            "engine": os.environ.get("LATEX_COMPILE_ENGINE") or DEFAULT_LATEX_ENGINE,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{bridge_url.rstrip('/')}/validate-compile",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=float(os.environ.get("LATEX_BRIDGE_TIMEOUT", "90"))) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return None, f"LaTeX MCP bridge failed with HTTP {exc.code}: {detail}"
    except (OSError, TimeoutError, json.JSONDecodeError) as exc:
        return None, f"LaTeX MCP bridge unavailable: {exc}"


def _latex_output_dir() -> Path:
    return Path(os.environ.get("LATEX_OUTPUT_DIR", "latex-output")).resolve()


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


def _render_template(template_id: str, context: dict[str, Any]) -> str:
    template = TEMPLATES[template_id]
    sections = [SECTION_RENDERERS[name](context) for name in template["sections"]]
    body = "\n\n".join(section for section in sections if section.strip())
    return f"{_classic_preamble()}\n\n{body}\n\n\\end{{document}}\n"


def _classic_preamble() -> str:
    return r"""
\documentclass[a4paper,11pt]{article}

\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[left=1.5cm,right=1.5cm,top=1.5cm,bottom=1.5cm]{geometry}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage[hidelinks]{hyperref}
\usepackage{parskip}
\usepackage{tabularx}
\usepackage{xcolor}
\usepackage{fontawesome5}
\newcommand{\cvhighlight}[1]{\textbf{#1}}
\newcommand{\cvExperience}[2]{\noindent\begin{tabularx}{\linewidth}{@{}Xr@{}}\textbf{#1} & #2\end{tabularx}\vspace{-0.6em}}
\newcommand{\cvProject}[2]{\noindent\begin{tabularx}{\linewidth}{@{}Xr@{}}\textbf{#1} & #2\end{tabularx}\vspace{-0.6em}}
\newcommand{\sep}{\hspace{1.2em}\textbar\hspace{1.2em}}
\definecolor{rulegray}{HTML}{555555}

\pagenumbering{gobble}

\titleformat{\section}{\large\bfseries}{}{0em}{}[{\color{rulegray}\titlerule[0.4pt]}]
\titlespacing*{\section}{0pt}{0.8em}{0.45em}
\setlist[itemize]{noitemsep, topsep=1pt, partopsep=0pt, parsep=0pt, leftmargin=1.2em}

\begin{document}
""".strip()


def _render_header(context: dict[str, Any]) -> str:
    candidate = context["candidate"]
    candidate_name = _latex_escape(candidate.get("display_name") or "Candidate")
    headline = _first_value(candidate, "headline")
    headline_line = f"    {_latex_escape(headline)} " + r"\\" + "\n    \\vspace{2pt}\n" if headline else ""
    contact_block = _candidate_contact_block(candidate)
    return rf"""
%====================
% HEADER
%====================
\begin{{center}}
    {{\LARGE \textbf{{{candidate_name}}}}} \\
{headline_line}{contact_block}\end{{center}}
""".strip()


def _render_summary(context: dict[str, Any]) -> str:
    summary = _clean_cv_text(context["draft"].get("summary") or context["candidate"].get("summary"))
    if not summary:
        return ""
    return rf"""
%====================
% PROFILE
%====================
\section*{{Profile}}
{_latex_escape(summary)}
""".strip()


def _render_education(context: dict[str, Any]) -> str:
    items = context["evidence_by_type"].get("education", [])
    return _section_lines("Education", [_dated_heading(item) for item in items])


def _render_experience(context: dict[str, Any]) -> str:
    entries, loose_bullets = _experience_entries(context)
    if not entries and not loose_bullets:
        return ""
    entry_lines = "\n\n".join(entries)
    loose_lines = ""
    if loose_bullets and not entries:
        bullet_lines = "\n".join(f"    \\item {bullet}" for bullet in loose_bullets)
        loose_lines = rf"""
\begin{{itemize}}
{bullet_lines}
\end{{itemize}}
""".strip()
    body = "\n\n".join(line for line in [entry_lines, loose_lines] if line.strip())
    return rf"""
%====================
% EXPERIENCE
%====================
\section*{{Experience}}
{body}
""".strip()


def _experience_entries(context: dict[str, Any]) -> tuple[list[str], list[str]]:
    experiences = context["evidence_by_type"].get("experience", [])
    by_id = {str(item.get("evidence_id") or ""): item for item in experiences}
    all_by_id = _evidence_by_id(context)
    grouped: dict[str, list[str]] = {evidence_id: [] for evidence_id in by_id}
    loose_bullets = []
    seen_bullets: set[str] = set()

    for bullet in context["bullets"]:
        text = _latex_escape(_clean_cv_text(_bullet_text(bullet)))
        if not text or text in seen_bullets:
            continue
        matched_id = _first_referenced_experience_id(bullet, by_id)
        if matched_id:
            grouped[matched_id].append(text)
        elif not _has_referenced_evidence(bullet, all_by_id):
            loose_bullets.append(text)
        seen_bullets.add(text)

    entries = []
    for evidence_id, item in by_id.items():
        bullets = grouped.get(evidence_id) or []
        if not bullets:
            continue
        bullet_lines = "\n".join(f"    \\item {bullet}" for bullet in bullets)
        entries.append(
            rf"""
{_experience_heading(item)}
\begin{{itemize}}
{bullet_lines}
\end{{itemize}}
""".strip()
        )
    return entries, loose_bullets


def _first_referenced_experience_id(bullet: object, by_id: dict[str, dict[str, Any]]) -> str | None:
    return _first_referenced_evidence_id(bullet, by_id)


def _first_referenced_evidence_id(bullet: object, by_id: dict[str, dict[str, Any]]) -> str | None:
    if not isinstance(bullet, dict):
        return None
    for evidence_id in bullet.get("evidence_ids") or []:
        key = str(evidence_id)
        if key in by_id:
            return key
    return None


def _has_referenced_evidence(bullet: object, by_id: dict[str, dict[str, Any]]) -> bool:
    return _first_referenced_evidence_id(bullet, by_id) is not None


def _render_projects(context: dict[str, Any]) -> str:
    entries = _project_entries(context)
    if entries:
        return _section_lines("Projects", entries)
    items = context["evidence_by_type"].get("project", [])
    return _section_lines("Projects", [_dated_heading(item) for item in items])


def _project_entries(context: dict[str, Any]) -> list[str]:
    projects = context["evidence_by_type"].get("project", [])
    by_id = {str(item.get("evidence_id") or ""): item for item in projects}
    grouped: dict[str, list[str]] = {evidence_id: [] for evidence_id in by_id}
    seen_bullets: set[str] = set()

    for bullet in context["bullets"]:
        text = _latex_escape(_clean_cv_text(_bullet_text(bullet)))
        if not text or text in seen_bullets:
            continue
        matched_id = _first_referenced_evidence_id(bullet, by_id)
        if matched_id:
            grouped[matched_id].append(text)
            seen_bullets.add(text)

    entries = []
    for evidence_id, item in by_id.items():
        bullets = grouped.get(evidence_id) or []
        if not bullets:
            continue
        bullet_lines = "\n".join(f"    \\item {bullet}" for bullet in bullets)
        entries.append(
            rf"""
{_project_heading(item)}
\begin{{itemize}}
{bullet_lines}
\end{{itemize}}
""".strip()
        )
    return entries


def _render_achievements(context: dict[str, Any]) -> str:
    items = [
        *context["evidence_by_type"].get("certification", []),
        *context["evidence_by_type"].get("achievement", []),
    ]
    return _section_lines("Achievements", [_compact_heading(item) for item in items])


def _render_skills(context: dict[str, Any]) -> str:
    skills = context["skills"]
    if not skills:
        return ""
    skills_line = ", ".join(_latex_escape(item) for item in skills)
    return rf"""
%====================
% SKILLS
%====================
\section*{{Skills}}
{skills_line}
""".strip()


def _section_lines(title: str, lines: list[str]) -> str:
    body = "\n\n".join(line for line in lines if line.strip())
    if not body:
        return ""
    return rf"""
%====================
% {title.upper()}
%====================
\section*{{{title}}}
{body}
""".strip()


def _dated_heading(item: dict[str, Any]) -> str:
    title = _latex_escape(item.get("title") or item.get("type") or "Candidate evidence")
    organization = _latex_escape(item.get("organization") or "")
    location = _latex_escape(item.get("location") or "")
    dates = _date_range(item)
    detail = _latex_escape(_clean_cv_text(item.get("description") or ""))
    org_line = " -- ".join(part for part in [organization, location] if part)
    heading = rf"\textbf{{{title}}}"
    if dates:
        heading += rf" \hfill {dates}"
    if org_line:
        heading += " " + r"\\" + "\n" + org_line
    if detail:
        heading += " " + r"\\" + "\n" + rf"\textit{{{detail}}}"
    return heading


def _experience_heading(item: dict[str, Any]) -> str:
    title = _latex_escape(item.get("title") or "Experience")
    organization = _latex_escape(item.get("organization") or "")
    location = _latex_escape(item.get("location") or "")
    dates = _date_range(item)
    organization_line = " -- ".join(part for part in [organization, location] if part)
    detail = " ".join(part for part in [dates, organization_line] if part)
    return rf"\cvExperience{{{title}}}{{{detail}}}"


def _project_heading(item: dict[str, Any]) -> str:
    title = _latex_escape(item.get("title") or "Project")
    organization = _latex_escape(item.get("organization") or "")
    location = _latex_escape(item.get("location") or "")
    dates = _date_range(item)
    organization_line = " -- ".join(part for part in [organization, location] if part)
    detail = " ".join(part for part in [dates, organization_line] if part)
    return rf"\cvProject{{{title}}}{{{detail}}}"


def _compact_heading(item: dict[str, Any]) -> str:
    title = _latex_escape(item.get("title") or item.get("type") or "Candidate evidence")
    organization = _latex_escape(item.get("organization") or "")
    dates = _date_range(item)
    parts = [title, organization]
    line = rf"\cvhighlight{{{' -- '.join(part for part in parts if part)}}}"
    if dates:
        line += rf" \hfill {dates}"
    return line


def _candidate_contact_block(candidate: dict[str, Any]) -> str:
    items = []
    email = _first_value(candidate, "email", "contact_email")
    phone = _first_value(candidate, "phone", "phone_number")
    location = _first_value(candidate, "location", "current_location")
    website = _first_value(candidate, "website", "portfolio_url", "url")
    github = _first_value(candidate, "github", "github_url")
    linkedin = _first_value(candidate, "linkedin", "linkedin_url")
    if email:
        escaped = _latex_escape(email)
        items.append(rf"\faEnvelope \; \href{{mailto:{escaped}}}{{{escaped}}}")
    if phone:
        items.append(rf"\faPhone \; {_latex_escape(phone)}")
    if location:
        items.append(rf"\faMapMarker* \; {_latex_escape(location)}")
    if website:
        items.append(rf"\faGlobe \; \href{{{_latex_escape(website)}}}{{{_latex_escape(_display_url(website))}}}")
    if github:
        items.append(rf"\faGithub \; \href{{{_latex_escape(github)}}}{{{_latex_escape(_display_url(github))}}}")
    if linkedin:
        items.append(rf"\faLinkedin \; \href{{{_latex_escape(linkedin)}}}{{{_latex_escape(_display_url(linkedin))}}}")
    if not items:
        return ""
    return "    " + r" \sep ".join(items) + r" \\" + "\n"


def _ranked_evidence_items(draft: dict[str, Any]) -> list[dict[str, Any]]:
    used_items = draft.get("evidence_used") or []
    retrieved_items = sorted(draft.get("retrieved_evidence") or [], key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return _unique_evidence_items([*used_items, *retrieved_items])


def _plan_cv(*, draft: dict[str, Any], job: dict[str, Any], evidence_items: list[dict[str, Any]], limits: dict[str, int]) -> dict[str, Any]:
    bullets = list(draft.get("bullets") or [])[: limits["bullets"]]
    grouped = _group_evidence_by_type(evidence_items)
    referenced_items = _referenced_evidence_items(bullets, evidence_items)
    referenced_experiences = _unique_evidence_items([item for item in referenced_items if _evidence_type(item) == "experience"])
    referenced_projects = _unique_evidence_items([item for item in referenced_items if _evidence_type(item) == "project"])
    selected_evidence = [
        *_fit_evidence_items(referenced_experiences, description_limit=limits["description_limit"]),
        *_fit_evidence_items(grouped.get("education", [])[: limits["education"]], description_limit=limits["description_limit"]),
        *_fit_evidence_items(referenced_projects[: limits["projects"]], description_limit=limits["description_limit"]),
        *grouped.get("certification", [])[: limits["achievements"]],
    ]
    remaining_achievement_slots = limits["achievements"] - len([item for item in selected_evidence if _evidence_type(item) == "certification"])
    if remaining_achievement_slots > 0:
        selected_evidence.extend(grouped.get("achievement", [])[:remaining_achievement_slots])

    skills = _unique_skills(job=job, evidence_items=[*referenced_items, *selected_evidence])
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


def _fit_evidence_items(items: list[dict[str, Any]], *, description_limit: int) -> list[dict[str, Any]]:
    return [_fit_evidence_item(item, description_limit=description_limit) for item in items]


def _fit_evidence_item(item: dict[str, Any], *, description_limit: int) -> dict[str, Any]:
    description = _clean_cv_text(item.get("description") or "")
    if len(description) <= description_limit:
        return item
    return {**item, "description": description[: description_limit - 1].rstrip() + "..."}


def _referenced_evidence_items(bullets: list[Any], evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    referenced_ids = []
    for bullet in bullets:
        if not isinstance(bullet, dict):
            continue
        for evidence_id in bullet.get("evidence_ids") or []:
            referenced_ids.append(str(evidence_id))
    by_id = {str(item.get("evidence_id") or ""): item for item in evidence_items}
    return [by_id[evidence_id] for evidence_id in referenced_ids if evidence_id in by_id]


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


def _unique_evidence_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique = []
    seen = set()
    for item in items:
        evidence_id = str(item.get("evidence_id") or item.get("chunk_id") or item.get("title") or "")
        if not evidence_id or evidence_id in seen:
            continue
        seen.add(evidence_id)
        unique.append(item)
    return unique


def _evidence_by_id(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_id = {}
    for items in context["evidence_by_type"].values():
        for item in items:
            evidence_id = str(item.get("evidence_id") or "")
            if evidence_id:
                by_id[evidence_id] = item
    return by_id


def _group_evidence_by_type(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = str(item.get("type") or "").strip().lower()
        if key:
            grouped.setdefault(key, []).append(item)
    return grouped


def _evidence_type(item: dict[str, Any]) -> str:
    return str(item.get("type") or "").strip().lower()


def _unique_skills(*, job: dict[str, Any], evidence_items: list[dict[str, Any]]) -> list[str]:
    skills = []
    for value in job.get("skills") or []:
        if isinstance(value, str) and value.strip():
            skills.append(value.strip())
    for item in evidence_items:
        for value in item.get("skills") or []:
            if isinstance(value, str) and value.strip():
                skills.append(value.strip())
    unique = []
    seen = set()
    for skill in skills:
        key = skill.lower()
        if key not in seen:
            seen.add(key)
            unique.append(skill)
    return unique


def _bullet_text(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("text") or "")
    return str(item)


def _job_label(job: dict[str, Any]) -> str:
    parts = [job.get("title"), job.get("company"), job.get("location")]
    return " -- ".join(str(part) for part in parts if part) or "selected role"


def _clean_cv_text(value: object) -> str:
    text = str(value or "").strip()
    replacements = [
        (r"\b[Ss]trong match for [^.]+\.\s*", ""),
        (r"\b[Tt]ailored for:?\s*[^.]+\.\s*", ""),
        (r"\b[Tt]ailored experience\s*[-–—:]\s*", ""),
        (r"\b[Tt]his was a focused prototype rather than [^.]+\.\s*", ""),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _date_range(item: dict[str, Any]) -> str:
    start = item.get("start_date")
    end = item.get("end_date") or ("Present" if item.get("is_current") else None)
    if start and end:
        return f"{_latex_escape(start)} -- {_latex_escape(end)}"
    if start:
        return _latex_escape(start)
    if end:
        return _latex_escape(end)
    return ""


def _latex_filename(*, job: dict[str, Any], candidate: dict[str, Any]) -> str:
    base = "-".join(
        part
        for part in (
            candidate.get("display_name") or "candidate",
            job.get("company") or None,
            job.get("title") or "tailored-cv",
        )
        if part
    )
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return f"{slug or 'tailored-cv'}.tex"


def _first_value(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _display_url(value: str) -> str:
    return re.sub(r"^https?://", "", value).rstrip("/")


def _latex_escape(value: object) -> str:
    text = str(value or "")
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


SECTION_RENDERERS: dict[str, SectionRenderer] = {
    "header": _render_header,
    "summary": _render_summary,
    "education": _render_education,
    "experience": _render_experience,
    "projects": _render_projects,
    "achievements": _render_achievements,
    "skills": _render_skills,
}


TEMPLATES: dict[str, dict[str, Any]] = {
    DEFAULT_TEMPLATE_ID: {
        "sections": ["header", "summary", "experience", "projects", "education", "achievements", "skills"],
    }
}
