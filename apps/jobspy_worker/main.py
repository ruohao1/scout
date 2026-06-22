from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class ScrapeRequest(BaseModel):
    site_name: list[str] | str
    search_term: str
    results_wanted: int = Field(default=10, ge=1, le=50)
    location: str | None = None
    distance: int | None = None
    job_type: str | None = None
    is_remote: bool | None = None
    hours_old: int | None = None
    country_indeed: str | None = "UK"
    description_format: str = "markdown"
    verbose: int = 0


app = FastAPI(title="Scout JobSpy Worker")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scrape")
def scrape(request: ScrapeRequest) -> dict[str, Any]:
    try:
        from jobspy import scrape_jobs
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="python-jobspy is not installed in the worker") from exc

    try:
        jobs = scrape_jobs(**_scrape_params(request))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"JobSpy scrape failed: {exc}") from exc

    records = jobs.where(jobs.notnull(), None).to_dict(orient="records")
    return {"jobs": [_json_safe(record) for record in records]}


def _scrape_params(request: ScrapeRequest) -> dict[str, Any]:
    params: dict[str, Any] = {
        "site_name": request.site_name,
        "search_term": request.search_term,
        "results_wanted": request.results_wanted,
        "description_format": request.description_format,
        "verbose": request.verbose,
    }
    if request.country_indeed:
        params["country_indeed"] = request.country_indeed
    if request.location:
        params["location"] = request.location
    if request.distance is not None:
        params["distance"] = request.distance
    if request.job_type:
        params["job_type"] = request.job_type
    if request.is_remote is not None:
        params["is_remote"] = request.is_remote
    if request.hours_old is not None:
        params["hours_old"] = request.hours_old
    return params


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value
