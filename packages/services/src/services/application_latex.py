from __future__ import annotations

import re
from typing import Any

from db.candidate import CandidateRepository
from db.jobs import JobRepository

from .application_materials import draft_tailored_cv


DEFAULT_TEMPLATE_ID = "classic_cv"


class TailoredCVLatexTemplateError(ValueError):
    pass


def draft_tailored_cv_latex(
    job_id: str,
    *,
    target_profile_id: str | None = None,
    instruction: str | None = None,
    evidence_limit: int = 8,
    template_id: str | None = None,
) -> dict[str, Any]:
    selected_template = template_id or DEFAULT_TEMPLATE_ID
    if selected_template != DEFAULT_TEMPLATE_ID:
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
    latex = _render_classic_cv(draft=draft, job=job or {}, candidate=candidate or {})
    return {
        "filename": _latex_filename(job=job or {}, candidate=candidate or {}),
        "latex": latex,
        "template_id": selected_template,
        "warnings": [
            "Generated from retrieved candidate evidence. Review and compile externally before submitting.",
        ],
    }


def _render_classic_cv(*, draft: dict[str, Any], job: dict[str, Any], candidate: dict[str, Any]) -> str:
    candidate_name = _latex_escape(candidate.get("display_name") or "Candidate")
    target = _latex_escape(_job_label(job))
    summary = _latex_escape(draft.get("summary") or "")
    bullets = "\n".join(f"    \\item {_latex_escape(_bullet_text(item))}" for item in draft.get("bullets") or [])
    evidence = "\n".join(_evidence_line(item) for item in (draft.get("evidence_used") or [])[:6])
    cautions = "\n".join(f"    \\item {_latex_escape(str(item))}" for item in draft.get("gaps_or_cautions") or [])
    headline_line = _headline_line(candidate)
    contact_block = _candidate_contact_block(candidate)
    evidence_section = _itemized_section("Evidence Used", evidence)
    caution_section = _itemized_section("Gaps or Cautions", cautions)
    skills_section = _skills_section(job=job, evidence_items=draft.get("evidence_used") or [])

    return rf"""
\documentclass[a4paper,11pt]{{article}}

\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage[left=1.5cm,right=1.5cm,top=1.5cm,bottom=1.5cm]{{geometry}}
\usepackage{{enumitem}}
\usepackage{{titlesec}}
\usepackage[hidelinks]{{hyperref}}
\usepackage{{parskip}}
\usepackage{{tabularx}}
\usepackage{{xcolor}}
\usepackage{{fontawesome5}}
\newcommand{{\cvhighlight}}[1]{{\textbf{{#1}}}}
\newcommand{{\sep}}{{\hspace{{1.2em}}\textbar\hspace{{1.2em}}}}

\pagenumbering{{gobble}}

\titleformat{{\section}}{{\large\bfseries}}{{}}{{0em}}{{}}[\titlerule]
\setlist[itemize]{{noitemsep, topsep=2pt}}

\begin{{document}}

%====================
% HEADER
%====================
\begin{{center}}
    {{\LARGE \textbf{{{candidate_name}}}}} \\
{headline_line}{contact_block}
\end{{center}}

%====================
% SUMMARY
%====================
\section*{{Summary}}
\cvhighlight{{Tailored for: {target}}}\\[0.35em]
{summary}

%====================
% EXPERIENCE
%====================
\section*{{Experience}}
\textbf{{Tailored Experience -- {target}}}
\begin{{itemize}}
{bullets}
\end{{itemize}}

{evidence_section}

{caution_section}

{skills_section}

\end{{document}}
""".strip() + "\n"


def _headline_line(candidate: dict[str, Any]) -> str:
    headline = candidate.get("headline")
    if not headline:
        return ""
    escaped = _latex_escape(headline)
    return f"    {escaped} \\\\\n    \\vspace{{2pt}}\n"


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
    return "\n    " + r" \sep ".join(items[:3]) + r" \\" + "\n"


def _itemized_section(title: str, body: str) -> str:
    if not body:
        return ""
    return rf"""
\section*{{{title}}}
\begin{{itemize}}
{body}
\end{{itemize}}
""".strip()


def _skills_section(*, job: dict[str, Any], evidence_items: list[dict[str, Any]]) -> str:
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
    if not unique:
        return ""
    midpoint = (len(unique) + 1) // 2
    left = ", ".join(_latex_escape(item) for item in unique[:midpoint])
    right = ", ".join(_latex_escape(item) for item in unique[midpoint:]) or left
    return rf"""
%====================
% SKILLS
%====================
\section*{{Skills}}
\begin{{tabularx}}{{\textwidth}}{{X X}}
\textbf{{Relevant Skills:}} {left} &
\textbf{{Additional Signals:}} {right} \\
\end{{tabularx}}
""".strip()


def _evidence_line(item: dict[str, Any]) -> str:
    title = item.get("title") or item.get("type") or "Candidate evidence"
    organization = item.get("organization")
    reason = item.get("reason")
    parts = [str(title)]
    if organization:
        parts.append(str(organization))
    if reason:
        parts.append(str(reason))
    return f"    \\item {_latex_escape(' -- '.join(parts))}"


def _bullet_text(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("text") or "")
    return str(item)


def _job_label(job: dict[str, Any]) -> str:
    parts = [job.get("title"), job.get("company"), job.get("location")]
    return " -- ".join(str(part) for part in parts if part) or "selected role"


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
