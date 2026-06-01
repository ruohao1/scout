from __future__ import annotations

import re


_SKILL_PATTERNS: list[tuple[str, str]] = [
    ("Python", r"\bpython\b"),
    ("FastAPI", r"\bfastapi\b"),
    ("Django", r"\bdjango\b"),
    ("Flask", r"\bflask\b"),
    ("PostgreSQL", r"\b(postgresql|postgres)\b"),
    ("MySQL", r"\bmysql\b"),
    ("MongoDB", r"\bmongodb\b"),
    ("SQL", r"\bsql\b"),
    ("Docker", r"\bdocker\b"),
    ("Kubernetes", r"\b(kubernetes|k8s)\b"),
    ("AWS", r"\b(aws|amazon web services)\b"),
    ("Azure", r"\bazure\b"),
    ("GCP", r"\b(gcp|google cloud)\b"),
    ("React", r"\breact\b"),
    ("TypeScript", r"\btypescript\b"),
    ("JavaScript", r"\bjavascript\b"),
    ("Node.js", r"\b(node\.js|nodejs)\b"),
    ("Java", r"\bjava\b"),
    ("C#", r"(?<!\w)c#(?!\w)"),
    ("C++", r"(?<!\w)c\+\+(?!\w)"),
    ("Go", r"\b(golang|go developer|go engineer|go programming|go services?)\b"),
    ("Rust", r"\brust\b"),
    ("Linux", r"\blinux\b"),
    ("Git", r"\bgit\b"),
    ("Terraform", r"\bterraform\b"),
    ("Redis", r"\bredis\b"),
    ("GraphQL", r"\bgraphql\b"),
    ("REST", r"\b(rest|restful)\b"),
    ("CI/CD", r"\b(ci/cd|cicd|continuous integration|continuous delivery)\b"),
    ("Pandas", r"\bpandas\b"),
    ("NumPy", r"\bnumpy\b"),
    ("PyTorch", r"\bpytorch\b"),
    ("TensorFlow", r"\btensorflow\b"),
]


def extract_job_skills(text: str) -> list[str]:
    return [skill for skill, pattern in _SKILL_PATTERNS if re.search(pattern, text, flags=re.IGNORECASE)]


def enrich_job_skills(job: dict) -> dict:
    existing = [skill for skill in job.get("skills", []) if isinstance(skill, str) and skill.strip()]
    seen = {skill.strip().lower() for skill in existing}
    text = "\n".join(str(job.get(key) or "") for key in ("title", "description"))
    skills = [skill.strip() for skill in existing]
    for skill in extract_job_skills(text):
        key = skill.lower()
        if key not in seen:
            skills.append(skill)
            seen.add(key)
    return {**job, "skills": skills}
