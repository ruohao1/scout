from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str
    expires_at: float
    account_id: str | None = None

    @property
    def expired(self) -> bool:
        return self.expires_at <= time.time() + 30


class TokenStore:
    def __init__(self, *, auth_dir: Path | None = None) -> None:
        self.auth_dir = auth_dir or Path(os.environ.get("SCOUT_AUTH_DIR", ".auth"))
        self.path = self.auth_dir / "openai_auth.json"

    def load(self) -> OAuthTokens | None:
        if not self.path.exists():
            return None
        data = json.loads(self.path.read_text())
        if not isinstance(data, dict) or data.get("type") != "oauth":
            return None
        return OAuthTokens(
            access_token=str(data["access_token"]),
            refresh_token=str(data["refresh_token"]),
            expires_at=float(data["expires_at"]),
            account_id=_optional_str(data.get("account_id")),
        )

    def save(self, tokens: OAuthTokens) -> None:
        self.auth_dir.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {"type": "oauth", **asdict(tokens)}
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True))
        self.path.chmod(0o600)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
