from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile, Body, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError



from ...databases.db import conn
from ...models.model import Upload, Process, Dbcredentials, SavedQuery

from datetime import datetime, timezone, date

#from ...services.report.generate import generateReport 
#from ...services.report.ocr_generate import imgToOcr, buildJson
from ...services.report.geminie_generate import imgToCode
from ...services.report.cleanXml import clean_sql
from ...services.dbconn.connections import build_conn_dict
from ...services.dbconn.dbTesting import get_sample_data, get_sample_data_mongo,build_sqlalchemy_url, maybe_ssh_tunnel
from ...services.query.build import call_claude

import os
import json
import base64
from dotenv import load_dotenv
from sql_metadata import Parser

processed = os.getenv("PROCESS_DIR")
appname = os.getenv("APP_NAME")
apikey = os.getenv("API_KEY")
apikeygeminie = os.getenv("API_KEY_GEMINIE")
output = os.getenv("OUTPUT_DIR")
reference = os.getenv("REFERENCE_DIR")

router = APIRouter(prefix='/query', tags=['Query'])
templates = Jinja2Templates(f"{appname}/templates/query")



@router.get('/')
def create_query(request: Request, db: Session = Depends(conn)):

    
    return templates.TemplateResponse(
        request, 
        'build.html'
    ) 




@router.get('/saved')
def list_saved_queries(db: Session = Depends(conn)):
    rows = db.query(SavedQuery).order_by(SavedQuery.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "dataset_name": r.dataset_name,
            "report_type": r.report_type,
            "sql_text": r.sql_text,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]








from ...services.query.sample_cache import get_cached_sample, save_cached_sample
@router.post("/sample-data")
def sample_data(payload: dict = Body(...), db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == int(payload["connection_id"])).first()
    if not connection:
        raise HTTPException(404, "connection not found")

    tables = payload.get("tables") or []
    if not tables:
        raise HTTPException(400, "no tables specified")

    force_refresh = bool(payload.get("force_refresh"))
    connection_id = connection.id

    cached_results = {}
    missing_tables = tables if force_refresh else []
    if not force_refresh:
        for t in tables:
            cached = get_cached_sample(connection_id, t)
            if cached is not None:
                cached_results[t] = cached
            else:
                missing_tables.append(t)

    fresh_results = {}
    if missing_tables:
        c = build_conn_dict(connection)
        try:
            if c["type"] == "mongodb":
                fresh_results = get_sample_data_mongo(c, missing_tables)
            else:
                fresh_results = get_sample_data(c, missing_tables)
        except Exception as e:
            raise HTTPException(502, f"couldn't fetch sample data: {e}")

        for t, rows in fresh_results.items():
            save_cached_sample(connection_id, t, rows)

    return {**cached_results, **fresh_results}















from sql_metadata import Parser

def validate_generated_tables(sql: str, allowed_tables: list[str]) -> list[str]:
    """
    Returns a list of tables/views referenced in the generated SQL that weren't
    part of the sample data given to the model. A non-empty list means the model
    hallucinated a join — the query should not be returned to the user as-is.
    """
    try:
        referenced = set(Parser(sql).tables)
    except Exception:
        return []  # if the parser itself can't handle this SQL, don't block on it — not this check's job

    # normalize both sides: strip backticks, compare case-insensitively
    def norm(t): return t.strip("`").lower()
    allowed = {norm(t) for t in allowed_tables}
    unknown = [t for t in referenced if norm(t) not in allowed]
    return unknown




MAX_IMAGE_BYTES = 5 * 1024 * 1024  # Claude's vision input limit is comfortably above typical screenshots

@router.post("/generate")
async def generate_query(request: Request, db: Session = Depends(conn)):
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        dataset_name = form.get("dataset_name", "")
        report_type = form.get("report_type", "")
        description = form.get("description", "")
        tables = json.loads(form.get("tables", "[]"))
        sample_json = form.get("sample_json", "")
        connection_id = form.get("connection_id")
        image_file = form.get("reportImage")
        image_bytes = await image_file.read() if image_file else None
        image_mime = image_file.content_type if image_file else None
        report_text = None
    else:
        body = await request.json()
        dataset_name = body.get("dataset_name", "")
        report_type = body.get("report_type", "")
        description = body.get("description", "")
        tables = body.get("tables", [])
        sample_json = body.get("sample_json")
        if not isinstance(sample_json, str):
            sample_json = json.dumps(sample_json, ensure_ascii=False)
        connection_id = body.get("connection_id")
        report_format = body.get("report_format", {})
        report_text = report_format.get("text", "")
        image_bytes = None
        image_mime = None

    # ---- validation (unchanged) ----
    if not connection_id:
        raise HTTPException(400, "connection_id is required")
    if not tables:
        raise HTTPException(400, "at least one table is required")
    if not sample_json or not sample_json.strip():
        raise HTTPException(400, "sample_json is required")
    if image_bytes and len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "report image is too large (max 5MB)")
    try:
        json.loads(sample_json)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"sample_json is not valid JSON: {e}")

    # ---- build the user turn — description appended only when the user gave one ----
    user_text = (
        f"Dataset name: {dataset_name}\n"
        f"Report type: {report_type}\n"
        f"Table(s): {', '.join(tables)}\n"
        f"Sample data (JSON): {sample_json}\n"
    )
    if description and description.strip():
        user_text += f"Additional context from the user: {description.strip()}\n"

    content_blocks = []
    if image_bytes:
        user_text += "Report format: see attached image."
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_mime or "image/png",
                "data": base64.b64encode(image_bytes).decode(),
            },
        })
    else:
        user_text += f"Report format: {report_text}"

    content_blocks.append({"type": "text", "text": user_text})

    sql_text = call_claude(content_blocks)
    
    sql_text = call_claude(content_blocks)

    unknown_tables = validate_generated_tables(sql_text, tables)
    if unknown_tables:
        raise HTTPException(
            502,
            f"the generated query references table(s) not in your sample data: {', '.join(unknown_tables)} — "
            f"this usually means a requested report field has no matching source table. "
            f"Try removing that field from the report format, or add the missing table to your selection."
        )

    return {"sql": sql_text}




@router.post("/save")
def save_query(payload: dict = Body(...), db: Session = Depends(conn)):
    connection_id = payload.get("connection_id")
    dataset_name = (payload.get("dataset_name") or "").strip()
    report_type = (payload.get("report_type") or "").strip()
    sql_text = (payload.get("sql") or "").strip()
    tables = payload.get("tables") or []

    if not connection_id:
        raise HTTPException(400, "connection_id is required")
    if not dataset_name:
        raise HTTPException(400, "dataset_name is required")
    if not sql_text:
        raise HTTPException(400, "sql is required")
    if not tables:
        raise HTTPException(400, "at least one table is required")

    connection = db.query(Dbcredentials).filter(Dbcredentials.id == int(connection_id)).first()
    if not connection:
        raise HTTPException(404, "connection not found")

    # sample_json arrives as a JSON string from the frontend (same shape /generate validates) —
    # parse it so it's stored as structured JSON, not a string-of-a-string
    sample_json_raw = payload.get("sample_json")
    sample_json = None
    if sample_json_raw:
        try:
            sample_json = json.loads(sample_json_raw) if isinstance(sample_json_raw, str) else sample_json_raw
        except json.JSONDecodeError:
            sample_json = None  # don't fail the save over an unparseable sample — it's reference data, not critical

    row = SavedQuery(
        connection_id=int(connection_id),
        dataset_name=dataset_name,
        report_type=report_type,
        description=(payload.get("description") or "").strip() or None,
        tables=tables,
        sample_json=sample_json,
        sql_text=sql_text,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return JSONResponse(status_code=201, content={
        "id": row.id,
        "dataset_name": row.dataset_name,
        "report_type": row.report_type,
        "tables": row.tables,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    })


# run the query generated
import re
import time
from decimal import Decimal
MAX_ROWS = 500
CONNECT_TIMEOUT = 5  # keep this in sync with the constant used in dbTesting.py

# Blocks anything that isn't a pure read. WITH is allowed since CTEs are part of your
# generated query pattern (pivoting via CASE WHEN inside a CTE per the system prompt).
FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
    r"REPLACE|MERGE|CALL|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)


def json_safe(value):
    if isinstance(value, Decimal): return float(value)
    if isinstance(value, (datetime, date)): return value.isoformat()
    if isinstance(value, (bytes, bytearray)): return value.decode(errors="replace")
    return value


def coerce_param(value):
    """Params arrive from the frontend as plain strings (text inputs) — try int/float
    so numeric comparisons in WHERE clauses bind correctly, otherwise leave as string."""
    if value is None or value == "":
        return None
    for cast in (int, float):
        try:
            return cast(value)
        except (TypeError, ValueError):
            continue
    return value


def enforce_row_limit(sql: str) -> str:
    """Defensive cap even if the generated query doesn't already end in a LIMIT."""
    stripped = sql.strip().rstrip(";")
    if re.search(r"\bLIMIT\s+\d+\s*$", stripped, re.IGNORECASE):
        return stripped
    return f"{stripped}\nLIMIT {MAX_ROWS}"


@router.post("/run")
def run_query(payload: dict = Body(...), db: Session = Depends(conn)):
    connection_id = payload.get("connection_id")
    sql = (payload.get("sql") or "").strip()
    params = payload.get("params") or {}

    if not connection_id:
        raise HTTPException(400, "connection_id is required")
    if not sql:
        raise HTTPException(400, "sql is required")

    connection = db.query(Dbcredentials).filter(Dbcredentials.id == int(connection_id)).first()
    if not connection:
        raise HTTPException(404, "connection not found")

    c = build_conn_dict(connection)

    if c["type"] in ("mongodb", "redis"):
        # the generation prompt is MySQL-specific right now, so non-relational
        # connections shouldn't reach this route at all
        return {"error": f"{c['type']} connections don't support SQL execution"}

    # ---- read-only guard ----
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, re.IGNORECASE):
        return {"error": "only SELECT statements can be run from this tool"}
    
    # if not re.match(r"^\s*(--[^\n]*\n|\s)*\b(SELECT|WITH)\b", sql, re.IGNORECASE):
    #     return {"error": "only SELECT statements can be run from this tool"}
    
    if FORBIDDEN_KEYWORDS.search(sql):
        return {"error": "query contains a disallowed statement type"}
    if ";" in sql.rstrip(";"):
        return {"error": "multiple statements are not allowed"}

    bound_params = {k: coerce_param(v) for k, v in params.items()}
    safe_sql = enforce_row_limit(sql)

    try:
        with maybe_ssh_tunnel(c) as (host, port):
            engine = create_engine(
                build_sqlalchemy_url(c, host, port),
                connect_args={"connect_timeout": CONNECT_TIMEOUT},
            )
            try:
                start = time.perf_counter()
                with engine.connect() as db_conn:
                    result = db_conn.execute(text(safe_sql), bound_params)
                    columns = list(result.keys())
                    rows = result.fetchmany(MAX_ROWS)
                execution_ms = round((time.perf_counter() - start) * 1000)
            finally:
                engine.dispose()
    except SQLAlchemyError as e:
        # e.orig is the underlying DBAPI error — usually the actually useful message
        return {"error": str(getattr(e, "orig", e))}
    except Exception as e:
        return {"error": str(e)}

    return {
        "columns": columns,
        "rows": [[json_safe(v) for v in row] for row in rows],
        "row_count": len(rows),
        "execution_ms": execution_ms,
    }



@router.get("/uploads")
def list_query_uploads(db: Session = Depends(conn)):
    uploads = (
        db.query(Upload)
        .filter(Upload.deleted_at.is_(None))
        .order_by(Upload.created_at.desc())
        .all()
    )
    return [
        {
            "id": u.id,
            "filename": u.displayname or u.name,
            "url": f"/uploads/file/{u.id}",
            "uploaded_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in uploads
    ]


@router.get("/uploads/file/{id}")
def get_upload_file(id: int, db: Session = Depends(conn)):
    upload = db.query(Upload).filter(Upload.id == id).first()
    if not upload:
        raise HTTPException(404, "upload not found")
    if not os.path.exists(upload.path):
        raise HTTPException(404, "file is missing on disk")
    return FileResponse(upload.path)