# services/dbconn/table_meta.py
import os
import json
from pathlib import Path

appname = os.getenv("APP_NAME")
TABLE_META_DIR_NAME = os.getenv("TABLE_META_DIR", "table_meta")


def _dir() -> str:
    folder = os.path.join(appname, TABLE_META_DIR_NAME)
    os.makedirs(folder, exist_ok=True)
    return folder


def _path(connection_id: int) -> Path:
    return Path(_dir()) / f"{connection_id}.json"


def _default_path() -> Path:
    return Path(_dir()) / "default.json"


def bare_table_name(table_name: str) -> str:
    """'salesdb.students' -> 'students'; 'students' -> 'students' — the shared library
    is keyed without a schema/database prefix, since the whole point is reuse across
    connections that don't share a database name but do share a table name."""
    return table_name.split(".")[-1]


# ---- per-connection descriptions (unchanged) ----

def load_table_descriptions(connection_id: int) -> dict:
    path = _path(connection_id)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data.get("tables", {})


def save_table_descriptions(connection_id: int, descriptions: dict) -> None:
    cleaned = {t: d.strip() for t, d in descriptions.items() if d and d.strip()}
    with open(_path(connection_id), "w", encoding="utf-8") as f:
        json.dump({"connection_id": connection_id, "tables": cleaned}, f, ensure_ascii=False, indent=2)


# ---- shared default library (new) ----

def load_default_descriptions() -> dict:
    path = _default_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data.get("tables", {})


def save_default_descriptions(bare_named_entries: dict) -> None:
    """
    Merges the given {bare_table_name: description} entries into the shared file —
    only overwrites the keys provided, leaves every other table's shared entry alone.
    Always reflects whichever connection most recently saved a description for that
    bare table name; there's no per-connection ownership on this file.
    """
    existing = load_default_descriptions()
    for bare_name, desc in bare_named_entries.items():
        if desc and desc.strip():
            existing[bare_name] = desc.strip()
    with open(_default_path(), "w", encoding="utf-8") as f:
        json.dump({"tables": existing}, f, ensure_ascii=False, indent=2)