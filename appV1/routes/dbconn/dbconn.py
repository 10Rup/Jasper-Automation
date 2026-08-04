from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile, HTTPException, Body
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...databases.db import conn
from ...models.model import Upload, Process, Dbcredentials, SshKey
from ...services.dbconn.connections import build_conn_dict
from ...services.dbconn.dbTesting import (
    test_connection, list_tables, save_key_file_to_disk, write_temp_ssh_key,
    get_plain_sample_rows, get_plain_sample_rows_mongo, get_sample_data, get_sample_data_mongo,
)
from ...services.dbconn.sshkeys import save_ssh_key
from ...services.dbconn.describe import generate_table_description
from ...services.dbconn.table_meta import (
    load_table_descriptions, save_table_descriptions,
    load_default_descriptions, save_default_descriptions, bare_table_name,
)
from ...services.query.sample_cache import get_cached_sample, save_cached_sample

from datetime import datetime, timezone
import os
import json
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from typing import Optional

appname = os.getenv("APP_NAME")
MIN_DESCRIBE_ROWS = 5

router = APIRouter(prefix='/db', tags=['Connections'])
templates = Jinja2Templates(f"{appname}/templates/dbconn")


# ================= SSH KEYS =================

@router.get('/keys')
def list_ssh_keys(db: Session = Depends(conn)):
    keys = (
        db.query(SshKey)
        .filter(SshKey.deleted_at.is_(None))
        .order_by(SshKey.uploaded_at.desc())
        .all()
    )
    return [
        {"id": k.id, "name": k.name, "filename": k.original_filename,
         "uploaded_at": k.uploaded_at.isoformat() if k.uploaded_at else None}
        for k in keys
    ]


@router.post('/keys/add')
async def add_ssh_key(request: Request, db: Session = Depends(conn)):
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("multipart/form-data"):
        raise HTTPException(400, "expected multipart/form-data with a name and keyFile")

    data = await request.form()
    name = data.get("name")
    key_file = data.get("keyFile")
    if not name:
        raise HTTPException(400, "give this key a name")
    if not key_file:
        raise HTTPException(400, "a .pem file is required")

    key_file_bytes = await key_file.read()
    try:
        row = save_ssh_key(name, key_file.filename, key_file_bytes, db)
    except ValueError as e:
        raise HTTPException(400, str(e))

    db.commit()
    return JSONResponse(status_code=201, content={
        "ok": True, "id": row.id, "name": row.name, "filename": row.original_filename,
    })


@router.delete('/keys/{id}')
def delete_ssh_key(id: int, db: Session = Depends(conn)):
    key = db.query(SshKey).filter(SshKey.id == id).first()
    if not key:
        raise HTTPException(404, "key not found")
    in_use = (
        db.query(Dbcredentials)
        .filter(Dbcredentials.ssh_key_id == id, Dbcredentials.deleted_at.is_(None))
        .count()
    )
    if in_use:
        raise HTTPException(400, f"this key is used by {in_use} connection(s) — remove it from those first")
    key.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


# ================= CONNECTIONS: CRUD =================

@router.post('/add')
async def add_connection(request: Request, db: Session = Depends(conn)):
    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(400, "request body is empty — expected a JSON connection payload")
    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"request body is not valid JSON: {e}")

    new_db = Dbcredentials(
        type=data.get('type'),
        name=data.get('name'),
        host=data.get('host'),
        port=data.get('port'),
        db=data.get('db'),
        user=data.get('user'),
        dbpass=data.get('pass'),
        ssl=bool(data.get('ssl')),
        sshHost=data.get('sshHost') or None,
        sshPort=int(data['sshPort']) if data.get('sshPort') else None,
        sshUser=data.get('sshUser') or None,
        authMode=data.get('authMode') or 'password',
        sshPass=data.get('sshPass') or None,
        keyPass=data.get('keyPass') or None,
        ssh_key_id=int(data['ssh_key_id']) if data.get('ssh_key_id') else None,
    )
    db.add(new_db)
    db.commit()

    return {'ok': True, 'status': 'success', 'message': 'Database connection added successfully.'}


@router.put('/{id}')
async def update_connection(id: int, request: Request, db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id).first()
    if not connection:
        return JSONResponse(status_code=404, content={'status': 'error', 'message': 'Connection not found.'})

    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(400, "request body is empty — expected a JSON connection payload")
    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"request body is not valid JSON: {e}")

    connection.type = data.get('type', connection.type)
    connection.name = data.get('name', connection.name)
    connection.host = data.get('host', connection.host)
    connection.port = int(data['port']) if data.get('port') else connection.port
    connection.db = data.get('db', connection.db)
    connection.user = data.get('user', connection.user)
    connection.ssl = bool(data.get('ssl'))
    connection.sshHost = data.get('sshHost') or None
    connection.sshPort = int(data['sshPort']) if data.get('sshPort') else None
    connection.sshUser = data.get('sshUser') or None
    connection.authMode = data.get('authMode') or 'password'
    connection.ssh_key_id = int(data['ssh_key_id']) if data.get('ssh_key_id') else None

    if data.get('pass'):
        connection.dbpass = data.get('pass')
    if data.get('sshPass'):
        connection.sshPass = data.get('sshPass')
    if data.get('keyPass'):
        connection.keyPass = data.get('keyPass')

    connection.status = 'untested'
    db.commit()

    return {'ok': True, 'status': 'success', 'message': 'Database connection updated successfully.'}


@router.delete('/{id}')
def delete_connection(request: Request, id: int, db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id).first()
    if not connection:
        return JSONResponse(status_code=404, content={'status': 'error', 'message': 'Connection not found.'})

    connection.deleted_at = datetime.now(timezone.utc)
    db.commit()

    return {'ok': True, 'status': 'success', 'message': 'Database connection deleted successfully.'}


# ================= CONNECTIONS: TESTING =================

@router.post('/test')
async def test_connection_endpoint(request: Request, db: Session = Depends(conn)):
    raw_body = await request.body()
    if not raw_body:
        raise HTTPException(400, "request body is empty — expected a JSON connection payload")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"request body is not valid JSON: {e}")

    payload["dbpass"] = payload.pop("pass", payload.get("dbpass"))

    if payload.get("authMode") == "key":
        key_id = payload.get("ssh_key_id")
        if not key_id:
            return JSONResponse(status_code=200, content={"ok": False, "error": "select a private key"})
        key = db.query(SshKey).filter(SshKey.id == int(key_id)).first()
        if not key:
            return JSONResponse(status_code=200, content={"ok": False, "error": "selected key not found"})
        payload["ssh_key_path"] = key.storage_path
    else:
        payload["ssh_key_path"] = None

    test_result = test_connection(payload)

    if test_result["ok"]:
        return {"ok": True, "latency_ms": test_result.get("latency_ms")}
    else:
        return JSONResponse(status_code=200, content={"ok": False, "error": test_result["error"]})


@router.post('/{id}/test')
def testing_connection(request: Request, id: int, db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id).first()
    if not connection:
        return JSONResponse(status_code=404, content={'status': 'error', 'message': 'Connection not found.'})

    payload = build_conn_dict(connection)
    test_result = test_connection(payload)

    connection.status = 'active' if test_result["ok"] else 'error'
    connection.last_tested_at = datetime.now(timezone.utc)
    db.commit()

    if test_result["ok"]:
        return {"ok": True, "latency_ms": test_result.get("latency_ms"), "status": connection.status}
    else:
        return JSONResponse(status_code=200, content={
            "ok": False, "error": test_result["error"], "status": connection.status,
        })


# ================= TABLES =================

@router.get("/{id}/tables")
def get_connection_tables(id: int, db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id).first()
    if not connection:
        raise HTTPException(404, "connection not found")

    c = build_conn_dict(connection)  # was a manually rebuilt dict here — reuse the shared helper instead
    try:
        return list_tables(c)
    except Exception as e:
        raise HTTPException(502, f"couldn't list tables: {e}")


# ================= TABLE DESCRIPTIONS =================
# GET  /table-descriptions/default         -> the shared, bare-table-name library
# GET  /{id}/table-descriptions            -> this connection's own saved descriptions
# PUT  /{id}/table-descriptions            -> saves both: this connection's copy (exact,
#      possibly schema-qualified keys) AND write-through to the shared library (bare keys),
#      so another connection with a same-named table gets it as a starting point.
# POST /{id}/tables/{table_name}/describe  -> AI-drafts a description from real sample data.
#      Cache-first: reuses the Query Builder's sample cache if it already has >= 5 rows,
#      otherwise pulls a fresh plain LIMIT-5 sample (bypassing the anchor/repeat logic
#      that's specific to query generation) and refreshes the cache with it.

@router.get('/table-descriptions/default')
def get_default_table_descriptions():
    return load_default_descriptions()


@router.get('/{id}/table-descriptions')
def get_table_descriptions(id: int, db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id, Dbcredentials.deleted_at.is_(None)).first()
    if not connection:
        raise HTTPException(404, "connection not found")
    return load_table_descriptions(id)


@router.put('/{id}/table-descriptions')
def put_table_descriptions(id: int, payload: dict = Body(...), db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id, Dbcredentials.deleted_at.is_(None)).first()
    if not connection:
        raise HTTPException(404, "connection not found")

    tables = payload.get("tables", {})
    save_table_descriptions(id, tables)

    bare_entries = {bare_table_name(name): desc for name, desc in tables.items() if desc and desc.strip()}
    if bare_entries:
        save_default_descriptions(bare_entries)

    return {"ok": True}


@router.post('/{id}/tables/{table_name}/describe')
def describe_table(id: int, table_name: str, db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id, Dbcredentials.deleted_at.is_(None)).first()
    if not connection:
        raise HTTPException(404, "connection not found")

    c = build_conn_dict(connection)

    cached = get_cached_sample(id, table_name)
    rows = cached if cached and len(cached) >= MIN_DESCRIBE_ROWS else None

    if rows is None:
        try:
            if c["type"] == "mongodb":
                rows = get_plain_sample_rows_mongo(c, table_name, MIN_DESCRIBE_ROWS)
            else:
                rows = get_plain_sample_rows(c, table_name, MIN_DESCRIBE_ROWS)
        except Exception as e:
            raise HTTPException(502, f"couldn't fetch sample data: {e}")

        if rows:
            save_cached_sample(id, table_name, rows)

    if not rows:
        raise HTTPException(400, "no sample data available for this table")

    try:
        description = generate_table_description(table_name, rows[:MIN_DESCRIBE_ROWS])
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    return {"description": description}