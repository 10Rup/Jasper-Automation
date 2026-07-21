from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from ...databases.db import conn
from ...models.model import Upload, Process, Dbcredentials, SshKey
from datetime import datetime, timezone
from ...services.dbconn.dbTesting import test_connection,list_tables, save_key_file_to_disk, write_temp_ssh_key
from ...services.dbconn.sshkeys import save_ssh_key


import os,json
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from typing import Optional

appname = os.getenv("APP_NAME")


router = APIRouter(prefix='/db', tags=['Connections'])
templates = Jinja2Templates(f"{appname}/templates/dbconn")

# ----------------------------------------------------------------------------------
@router.get('/keys')
def list_ssh_keys(db: Session = Depends(conn)):
    keys = (db.query(SshKey)
              .filter(SshKey.deleted_at.is_(None))
              .order_by(SshKey.uploaded_at.desc())
              .all())
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
    in_use = (db.query(Dbcredentials)
                .filter(Dbcredentials.ssh_key_id == id, Dbcredentials.deleted_at.is_(None))
                .count())
    if in_use:
        raise HTTPException(400, f"this key is used by {in_use} connection(s) — remove it from those first")
    key.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}

# ------------------------------------Test For Db Connections-----------------------------------------------------------------------------------------------------------------
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
    

@router.delete('/{id}')
def delete_connection(request: Request, id: int, db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id).first()
    if not connection:
        return JSONResponse(status_code=404, content={'status': 'error', 'message': 'Connection not found.'})

    # db.delete(connection)
    connection.deleted_at = datetime.now(timezone.utc)
    db.commit()

    return {'ok': True, 'status': 'success', 'message': 'Database connection deleted successfully.'}

@router.post('/{id}/test')
def testing_connection(request: Request, id: int, db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id).first()

    if not connection:
        return JSONResponse(status_code=404, content={'status': 'error', 'message': 'Connection not found.'})

    payload = {
        "type": connection.type,
        "host": connection.host,
        "port": connection.port,
        "db": connection.db,
        "user": connection.user,
        "dbpass": connection.dbpass if connection.dbpass else None,
        "ssl": connection.ssl,
        "sshHost": connection.sshHost,
        "sshPort": connection.sshPort,
        "sshUser": connection.sshUser,
        "authMode": connection.authMode,
        "sshPass": connection.sshPass if connection.sshPass else None,
        "keyPass": connection.keyPass if connection.keyPass else None,
        "ssh_key_path": connection.ssh_key.storage_path if connection.ssh_key else None,
    }

    test_result = test_connection(payload)   # {"ok": True, "latency_ms": ...} or {"ok": False, "error": ...}

    connection.status = 'active' if test_result["ok"] else 'error'
    connection.last_tested_at = datetime.now(timezone.utc)
    db.commit()

    if test_result["ok"]:
        return {
            "ok": True,
            "latency_ms": test_result.get("latency_ms"),
            "status": connection.status,
        }
    else:
        return JSONResponse(status_code=200, content={
            "ok": False,
            "error": test_result["error"],
            "status": connection.status,
        })









# ... build/save the Dbcredentials row from `payload`, and if key_file_bytes
# is present, store the .ppk (convert to OpenSSH format here or at test-time,
# per the earlier note about puttygen)

@router.get("/{id}/tables")
def get_connection_tables(id: int, db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id).first()
    if not connection:
        raise HTTPException(404, "connection not found")

    c = {
        "type": connection.type,
        "host": connection.host,
        "port": connection.port,
        "db": connection.db,
        "user": connection.user,
        "dbpass": connection.dbpass if connection.dbpass else None,
        "ssl": connection.ssl,
        "sshHost": connection.sshHost,
        "sshPort": connection.sshPort,
        "sshUser": connection.sshUser,
        "authMode": connection.authMode,
        "sshPass": connection.sshPass if connection.sshPass else None,
        "keyPass": connection.keyPass if connection.keyPass else None,
        "ssh_key_path": connection.ssh_key.storage_path if connection.ssh_key else None,
    }

    try:
        return list_tables(c)
    except Exception as e:
        raise HTTPException(502, f"couldn't list tables: {e}")