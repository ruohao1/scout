from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Any, Callable


MIN_USEFUL_DESCRIPTION_CHARS = 250


class JobDescriptionRefreshError(ValueError):
    pass


class JobDescriptionUnavailableError(JobDescriptionRefreshError):
    pass


InferTextField = Callable[[str], str | None]


def has_weak_job_description(job: dict[str, Any]) -> bool:
    description = _clean_text(str(job.get("description") or ""))
    if len(description) < MIN_USEFUL_DESCRIPTION_CHARS:
        return True
    fallback_parts = [job.get("title"), f"Company: {job.get('company')}", f"Location: {job.get('location')}"]
    fallback = _clean_text("\n".join(str(part) for part in fallback_parts if part and not str(part).endswith(": None")))
    return bool(fallback and description == fallback)


def enrich_weak_job_description(
    job: dict[str, Any],
    *,
    infer_seniority: InferTextField | None = None,
    infer_remote_policy: InferTextField | None = None,
) -> dict[str, Any]:
    description = extract_description_for_job(job)
    if description is None:
        return job

    raw_payload = dict(job.get("raw_payload") or {})
    raw_payload["description_refresh"] = {"source_url": job.get("url"), "description": description}
    text = f"{job.get('title') or ''}\n{description}"
    location_text = f"{text}\n{job.get('location') or ''}"
    return {
        **job,
        "description": description,
        "raw_payload": raw_payload,
        "seniority": infer_seniority(text) if infer_seniority else job.get("seniority"),
        "remote_policy": infer_remote_policy(location_text) if infer_remote_policy else job.get("remote_policy"),
    }


def extract_description_for_job(job: dict[str, Any]) -> str | None:
    if not has_weak_job_description(job):
        return str(job.get("description") or "")
    url = str(job.get("url") or "")
    if not url.startswith(("http://", "https://")):
        return None

    html_text = _fetch_url(url)
    description = extract_job_description_from_html(html_text)
    if len(description) < MIN_USEFUL_DESCRIPTION_CHARS:
        return None
    return description


def extract_job_description_from_html(html_text: str) -> str:
    for text in _json_ld_descriptions(html_text):
        cleaned = _clean_text(text)
        if len(cleaned) >= MIN_USEFUL_DESCRIPTION_CHARS:
            return cleaned

    for pattern in (
        r'<div[^>]+class="[^"]*show-more-less-html__markup[^"]*"[^>]*>(?P<body>.*?)</div>',
        r'<section[^>]+class="[^"]*description[^"]*"[^>]*>(?P<body>.*?)</section>',
        r'<div[^>]+class="[^"]*description[^"]*"[^>]*>(?P<body>.*?)</div>',
    ):
        for match in re.finditer(pattern, html_text, flags=re.IGNORECASE | re.DOTALL):
            cleaned = _clean_text(_html_to_text(match.group("body")))
            if len(cleaned) >= MIN_USEFUL_DESCRIPTION_CHARS:
                return cleaned

    main_text = _clean_text(_html_to_text(html_text))
    return _description_slice(main_text)


def _fetch_url(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Scout/0.1 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.8,fr;q=0.7",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise JobDescriptionUnavailableError(f"Original posting returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise JobDescriptionUnavailableError(f"Original posting request failed: {exc.reason}") from exc


def _json_ld_descriptions(html_text: str) -> list[str]:
    descriptions: list[str] = []
    for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(?P<body>.*?)</script>', html_text, flags=re.IGNORECASE | re.DOTALL):
        body = html.unescape(match.group("body")).strip()
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue
        for item in _walk_json(data):
            if isinstance(item, dict) and str(item.get("@type") or "").lower() in {"jobposting", "jobpostingposting"}:
                description = item.get("description")
                if isinstance(description, str):
                    descriptions.append(_html_to_text(description))
            elif isinstance(item, dict) and isinstance(item.get("description"), str):
                descriptions.append(_html_to_text(item["description"]))
    return descriptions


def _walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return parser.text()


def _description_slice(text: str) -> str:
    markers = ["Description du poste", "About the job", "Job description", "Description", "Votre mission"]
    lower = text.lower()
    starts = [lower.find(marker.lower()) for marker in markers if lower.find(marker.lower()) >= 0]
    if starts:
        text = text[min(starts):]
    return text[:12_000].strip()


def _clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag in {"br", "p", "div", "li", "section", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag in {"p", "div", "li", "section", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        return _clean_text("".join(self._parts))
