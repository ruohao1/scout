from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from apps.api.schemas import AdzunaImportRequest, ProviderImportResult, ProviderImportRunRead
from db.provider_import_runs import ProviderImportRunRepository
from services import AdzunaJobProviderAdapter, AdzunaJobProviderClient, import_jobs


router = APIRouter(prefix="/providers", tags=["providers"])


@router.post("/adzuna/import", response_model=ProviderImportResult)
def import_adzuna_jobs(request: AdzunaImportRequest) -> dict:
    runs = ProviderImportRunRepository()
    query = _adzuna_query(request)
    try:
        result = import_jobs(
            client=AdzunaJobProviderClient(
                country=request.country,
                what=request.what,
                where=request.where,
                results_per_page=request.results_per_page,
            ),
            adapter=AdzunaJobProviderAdapter(),
            count=request.count,
            should_index=request.index,
        )
    except ValueError as exc:
        _record_failed_run(runs, provider="adzuna", query=query, requested_count=request.count, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        _record_failed_run(runs, provider="adzuna", query=query, requested_count=request.count, error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        _record_failed_run(runs, provider="adzuna", query=query, requested_count=request.count, error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    run = runs.create(
        {
            "provider": "adzuna",
            "query": query,
            "requested_count": request.count,
            "created_count": len(result.created),
            "skipped_count": result.skipped,
            "indexed_count": result.indexed,
            "status": "completed",
            "error": None,
        }
    )

    return {
        "import_run_id": run["id"],
        "source": "adzuna",
        "created": len(result.created),
        "skipped": result.skipped,
        "indexed": result.indexed,
        "job_ids": [job["id"] for job in result.created],
    }


@router.get("/import-runs", response_model=list[ProviderImportRunRead])
def list_import_runs(
    provider: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    return ProviderImportRunRepository().list(provider=provider, limit=limit)


def _adzuna_query(request: AdzunaImportRequest) -> dict:
    return {
        "country": request.country,
        "what": request.what,
        "where": request.where,
        "count": request.count,
        "index": request.index,
        "results_per_page": request.results_per_page,
    }


def _record_failed_run(
    runs: ProviderImportRunRepository,
    *,
    provider: str,
    query: dict,
    requested_count: int,
    error: str,
) -> None:
    runs.create(
        {
            "provider": provider,
            "query": query,
            "requested_count": requested_count,
            "created_count": 0,
            "skipped_count": 0,
            "indexed_count": 0,
            "status": "failed",
            "error": error,
        }
    )
