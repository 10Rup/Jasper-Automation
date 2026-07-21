import os
import json
import time
from pathlib import Path

CACHE_DIR = Path(os.getenv("SAMPLE_CACHE_DIR", "storage/jsondata"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Schema changes (new/renamed/dropped columns) aren't reflected until the cache
# expires — keep this short enough that stale schemas don't linger for long.
CACHE_TTL_SECONDS = int(os.getenv("SAMPLE_CACHE_TTL_SECONDS", 6 * 60 * 60))  # 6 hours


def _cache_path(connection_id: int) -> Path:
    # one file per connection — e.g. storage/jsondata/5.json — holding every
    # cached table's sample rows together, so it's readable at a glance rather
    # than scattered across dozens of tiny per-table files
    return CACHE_DIR / f"{connection_id}.json"


def _load_cache_file(connection_id: int) -> dict:
    path = _cache_path(connection_id)
    if not path.exists():
        return {"connection_id": connection_id, "tables": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"connection_id": connection_id, "tables": {}}  # corrupted — start fresh
    data.setdefault("tables", {})
    return data


def _save_cache_file(connection_id: int, data: dict) -> None:
    path = _cache_path(connection_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def get_cached_sample(connection_id: int, table: str) -> list | None:
    """Returns cached rows if present and not expired, otherwise None (a cache miss)."""
    data = _load_cache_file(connection_id)
    entry = data["tables"].get(table)
    if not entry:
        return None
    if time.time() - entry.get("cached_at", 0) > CACHE_TTL_SECONDS:
        return None  # expired
    return entry.get("rows")


def save_cached_sample(connection_id: int, table: str, rows: list) -> None:
    data = _load_cache_file(connection_id)
    data["tables"][table] = {
        "cached_at": time.time(),
        "cached_at_readable": time.strftime("%Y-%m-%d %H:%M:%S"),  # human-friendly, since this file is meant to be readable
        "rows": rows,
    }
    _save_cache_file(connection_id, data)


def invalidate_connection_cache(connection_id: int) -> None:
    """Call this when a connection's credentials/host change — old samples may no longer be valid."""
    path = _cache_path(connection_id)
    if path.exists():
        path.unlink()