from __future__ import annotations

import re


_SKILL_PATTERNS: list[tuple[str, str]] = [
    # Engineering and data
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
    ("Machine Learning", r"\b(machine learning|ml)\b"),
    ("Data Analysis", r"\b(data analysis|data analytics|analytics)\b"),
    ("Business Intelligence", r"\b(business intelligence|bi reporting|power bi|tableau)\b"),
    # Marketing and communications. Avoid generic "communication skills" here.
    ("SEO", r"\b(seo|search engine optimization)\b"),
    ("SEM", r"\b(sem|search engine marketing)\b"),
    ("Google Ads", r"\b(google ads|google adwords)\b"),
    ("Meta Ads", r"\b(meta ads|facebook ads|instagram ads)\b"),
    ("Content Marketing", r"\bcontent marketing\b"),
    ("Email Marketing", r"\bemail marketing\b"),
    ("Campaign Management", r"\b(campaign management|marketing campaigns?|campaigns? activation)\b"),
    ("Marketing Analytics", r"\b(marketing analytics|campaign analytics|web analytics)\b"),
    ("Growth Marketing", r"\b(growth marketing|growth hacking)\b"),
    ("Brand Management", r"\b(brand management|branding|brand strategy)\b"),
    ("Market Research", r"\b(market research|consumer insights?)\b"),
    ("Social Media", r"\b(social media|community management|community manager)\b"),
    ("Copywriting", r"\b(copywriting|copywriter|editorial content)\b"),
    ("Public Relations", r"\b(public relations|\bpr\b)\b"),
    ("Media Relations", r"\b(media relations|press relations|press office)\b"),
    ("Internal Communications", r"\binternal communications?\b"),
    ("Corporate Communications", r"\bcorporate communications?\b"),
    ("Event Management", r"\b(event management|event planning|events coordination)\b"),
    # Sales and customer-facing roles
    ("Business Development", r"\b(business development|\bbdr\b|\bsdr\b)\b"),
    ("Lead Generation", r"\blead generation\b"),
    ("Account Management", r"\baccount management\b"),
    ("Customer Success", r"\bcustomer success\b"),
    ("Salesforce", r"\bsalesforce\b"),
    ("CRM", r"\bcrm\b"),
    # Finance and accounting
    ("Accounting", r"\b(accounting|bookkeeping)\b"),
    ("Audit", r"\b(audit|auditing)\b"),
    ("Financial Analysis", r"\b(financial analysis|financial analyst|financial planning|fp&a)\b"),
    ("Financial Modeling", r"\bfinancial model(?:ing|ling)\b"),
    ("Controlling", r"\b(controlling|financial control)\b"),
    ("Budgeting", r"\b(budgeting|budget management|forecasting)\b"),
    ("Accounts Payable", r"\baccounts payable\b"),
    ("Accounts Receivable", r"\baccounts receivable\b"),
    # HR and people operations
    ("Recruitment", r"\b(recruitment|recruiting|sourcing candidates?)\b"),
    ("Talent Acquisition", r"\btalent acquisition\b"),
    ("Onboarding", r"\bonboarding\b"),
    ("Payroll", r"\bpayroll\b"),
    ("Employee Relations", r"\bemployee relations\b"),
    ("HRIS", r"\bhris\b"),
    ("Learning and Development", r"\b(learning and development|l&d|training programs?)\b"),
    # Legal and compliance
    ("Compliance", r"\b(compliance|regulatory compliance)\b"),
    ("Contract Law", r"\b(contract law|commercial contracts?)\b"),
    ("Contract Drafting", r"\b(contract drafting|drafting contracts?)\b"),
    ("Legal Research", r"\blegal research\b"),
    ("GDPR", r"\bgdpr\b"),
    ("Data Privacy", r"\b(data privacy|privacy law)\b"),
    # Design and product-adjacent work
    ("UX", r"\b(ux|user experience)\b"),
    ("UI", r"\b(ui|user interface)\b"),
    ("Figma", r"\bfigma\b"),
    ("Adobe Photoshop", r"\b(photoshop|adobe photoshop)\b"),
    ("Adobe Illustrator", r"\b(illustrator|adobe illustrator)\b"),
    ("Graphic Design", r"\bgraphic design\b"),
    ("Wireframing", r"\bwirefram(?:e|ing|es)\b"),
    ("Prototyping", r"\bprototyp(?:e|ing|es)\b"),
    ("User Research", r"\buser research\b"),
    # Operations and project delivery
    ("Supply Chain", r"\bsupply chain\b"),
    ("Logistics", r"\blogistics\b"),
    ("Procurement", r"\b(procurement|purchasing)\b"),
    ("Inventory Management", r"\binventory management\b"),
    ("Project Management", r"\bproject management\b"),
    ("Process Improvement", r"\bprocess improvement\b"),
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
