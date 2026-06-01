from __future__ import annotations

import os


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://scout:scout@127.0.0.1:5432/scout")
