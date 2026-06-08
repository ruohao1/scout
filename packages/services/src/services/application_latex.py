from __future__ import annotations

import re
from typing import Any, Callable

from db.candidate import CandidateRepository
from db.jobs import JobRepository

from .application_materials import draft_tailored_cv


DEFAULT_TEMPLATE_ID = "classic_cv"


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
    context = _latex_context(draft=draft, job=job or {}, candidate=candidate or {})
    latex = _render_template(selected_template, context)
    return {
        "filename": _latex_filename(job=job or {}, candidate=candidate or {}),
        "latex": latex,
        "template_id": selected_template,
        "warnings": [
            "Generated from retrieved candidate evidence. Review and compile externally before submitting.",
        ],
    }


def _latex_context(*, draft: dict[str, Any], job: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    evidence_items = _unique_evidence_items([*(draft.get("evidence_used") or []), *(draft.get("retrieved_evidence") or [])])
    return {
        "candidate": candidate,
        "job": job,
        "draft": draft,
        "evidence_by_type": _group_evidence_by_type(evidence_items),
        "skills": _unique_skills(job=job, evidence_items=evidence_items),
    }


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
\newcommand{\sep}{\hspace{1.2em}\textbar\hspace{1.2em}}
\definecolor{rulegray}{HTML}{555555}

\pagenumbering{gobble}

\titleformat{\section}{\large\bfseries}{}{0em}{}[{\color{rulegray}\titlerule[0.4pt]}]
\titlespacing*{\section}{0pt}{0.8em}{0.45em}
\setlist[itemize]{noitemsep, topsep=2pt, leftmargin=1.2em}

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
    bullets = [_latex_escape(_clean_cv_text(_bullet_text(item))) for item in context["draft"].get("bullets") or []]
    if not bullets:
        return ""
    bullet_lines = "\n".join(f"    \\item {bullet}" for bullet in bullets)
    return rf"""
%====================
% EXPERIENCE
%====================
\section*{{Experience}}
\begin{{itemize}}
{bullet_lines}
\end{{itemize}}
""".strip()


def _render_projects(context: dict[str, Any]) -> str:
    items = context["evidence_by_type"].get("project", [])
    return _section_lines("Projects", [_dated_heading(item) for item in items])


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


def _group_evidence_by_type(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        key = str(item.get("type") or "").strip().lower()
        if key:
            grouped.setdefault(key, []).append(item)
    return grouped


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
        "sections": ["header", "summary", "education", "experience", "projects", "achievements", "skills"],
    }
}
