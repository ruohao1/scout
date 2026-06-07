from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.api.schemas import RuntimeSettingsRead, RuntimeSettingsUpdate
from services import get_runtime_settings, update_runtime_settings


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/runtime", response_model=RuntimeSettingsRead)
def read_runtime_settings() -> dict:
    return get_runtime_settings()


@router.put("/runtime", response_model=RuntimeSettingsRead)
def write_runtime_settings(request: RuntimeSettingsUpdate) -> dict:
    try:
        return update_runtime_settings(request.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
