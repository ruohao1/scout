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
    candidate_headline = _latex_escape(candidate.get("headline") or draft.get("headline") or "")
    target = _latex_escape(_job_label(job))
    headline = _latex_escape(draft.get("headline") or "")
    summary = _latex_escape(draft.get("summary") or "")
    bullets = "\n".join(f"  \\item {_latex_escape(_bullet_text(item))}" for item in draft.get("bullets") or [])
    evidence = "\n".join(_evidence_line(item) for item in (draft.get("evidence_used") or [])[:6])
    cautions = "\n".join(f"  \\item {_latex_escape(str(item))}" for item in draft.get("gaps_or_cautions") or [])

    evidence_section = ""
    if evidence:
        evidence_section = rf"""
\\section*{{Evidence Used}}
\\begin{{itemize}}
{evidence}
\\end{{itemize}}
""".strip()

    caution_section = ""
    if cautions:
        caution_section = rf"""
\\section*{{Gaps or Cautions}}
\\begin{{itemize}}
{cautions}
\\end{{itemize}}
""".strip()

    return rf"""
\\documentclass[11pt,a4paper]{{article}}
\\usepackage[margin=1.8cm]{{geometry}}
\\usepackage{{enumitem}}
\\usepackage{{hyperref}}
\\usepackage{{titlesec}}
\\setlength{{\\parindent}}{{0pt}}
\\setlist[itemize]{{leftmargin=*, itemsep=0.35em, topsep=0.35em}}
\\titleformat{{\\section}}{{\\large\\bfseries}}{{}}{{0em}}{{}}

\\begin{{document}}

{{\\LARGE \\textbf{{{candidate_name}}}}}\\\\
{candidate_headline}\\\\[0.8em]
{{\\small Tailored for: {target}}}

\\section*{{Profile}}
\\textbf{{{headline}}}\\\\[0.35em]
{summary}

\\section*{{Selected Experience}}
\\begin{{itemize}}
{bullets}
\\end{{itemize}}

{evidence_section}

{caution_section}

\\end{{document}}
""".strip() + "\n"


def _evidence_line(item: dict[str, Any]) -> str:
    title = item.get("title") or item.get("type") or "Candidate evidence"
    organization = item.get("organization")
    reason = item.get("reason")
    parts = [str(title)]
    if organization:
        parts.append(str(organization))
    if reason:
        parts.append(str(reason))
    return f"  \\item {_latex_escape(' - '.join(parts))}"


def _bullet_text(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("text") or "")
    return str(item)


def _job_label(job: dict[str, Any]) -> str:
    parts = [job.get("title"), job.get("company"), job.get("location")]
    return " - ".join(str(part) for part in parts if part) or "selected role"


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
