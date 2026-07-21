from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from ...databases.db import conn
from ...models.model import Upload, Process, Dbcredentials
from datetime import datetime, timezone
from ...services.dbconn.dbTesting import test_connection,list_tables, save_key_file_to_disk, write_temp_ssh_key
import os,json
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from typing import Optional

appname = os.getenv("APP_NAME")


router = APIRouter(prefix='/db', tags=['Connections'])
templates = Jinja2Templates(f"{appname}/templates/dbconn")

# -----------------------------------------------------------------------------------------------------------------------------------------------------
@router.post('/test')
async def test_connection_endpoint(request: Request, db: Session = Depends(conn)):
    content_type = request.headers.get("content-type", "")
    cleanup_paths = []  # every temp file this request creates, removed in finally regardless of outcome

    try:
        if content_type.startswith("multipart/form-data"):
            data = await request.form()
            payload = {
                "name": data.get("name"),
                "type": data.get("type"),
                "host": data.get("host"),
                "port": data.get("port"),
                "db": data.get("db"),
                "user": data.get("user"),
                "dbpass": data.get("pass"),
                "ssl": str(data.get('ssl')).lower() == 'true',
                "sshHost": data.get("sshHost"),
                "sshPort": data.get("sshPort"),
                "sshUser": data.get("sshUser"),
                "authMode": data.get("authMode"),
                "sshPass": data.get("sshPass"),
                "keyPass": data.get("keyPass"),
                "ssh_key_path": None,
            }

            key_file = data.get("keyFile")
            if key_file:
                key_file_bytes = await key_file.read()
                key_result = write_temp_ssh_key(key_file.filename, key_file_bytes)
                payload["ssh_key_path"] = key_result["usable_path"]
                cleanup_paths.extend(key_result["cleanup_paths"])

                if payload["authMode"] == "key" and not key_result["converted_ok"]:
                    # don't even attempt the tunnel — surface a clear reason instead of
                    # a confusing paramiko auth failure caused by an unreadable key
                    return JSONResponse(status_code=200, content={
                        "ok": False,
                        "error": "the uploaded file doesn't look like a valid .pem private key "
                                 "(it should start with '-----BEGIN')",
                    })
        else:
            raw_body = await request.body()
            if not raw_body:
                raise HTTPException(400, "request body is empty — expected a JSON connection payload")
            try:
                payload = json.loads(raw_body)
            except json.JSONDecodeError as e:
                raise HTTPException(400, f"request body is not valid JSON: {e}")

            # frontend sends the DB password as "pass"; test_connection's testers read "dbpass" —
            # normalize here so JSON-path tests (password auth / no SSL) don't KeyError
            payload["dbpass"] = payload.pop("pass", payload.get("dbpass"))
            payload.setdefault("ssh_key_path", None)

        test_result = test_connection(payload)

        if test_result["ok"]:
            return {"ok": True, "latency_ms": test_result.get("latency_ms")}
        else:
            return JSONResponse(status_code=200, content={"ok": False, "error": test_result["error"]})

    finally:
        for path in cleanup_paths:
            if path and os.path.exists(path):
                os.remove(path)
# -----------------------------------------------------------------------------------------------------------------------------------------------------
@router.post('/add')
async def add_connection(request: Request, db: Session = Depends(conn)):
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        data = await request.form()
        key_file = data.get("keyFile")
        key_file_bytes = await key_file.read() if key_file else None
        key_file_name = key_file.filename if key_file else None
    else:
        raw_body = await request.body()
        if not raw_body:
            raise HTTPException(400, "request body is empty — expected a JSON connection payload")
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"request body is not valid JSON: {e}")
        key_file_bytes = None
        key_file_name = None

    new_db = Dbcredentials(
        type=data.get('type'),
        name=data.get('name'),
        host=data.get('host'),
        port=data.get('port'),
        db=data.get('db'),
        user=data.get('user'),
        dbpass=data.get('pass'),
        ssl=str(data.get('ssl')).lower() == 'true' if content_type.startswith("multipart/form-data") else bool(data.get('ssl')),
        sshHost=data.get('sshHost') or None,
        sshPort=int(data['sshPort']) if data.get('sshPort') else None,
        sshUser=data.get('sshUser') or None,
        authMode=data.get('authMode') or 'password',
        sshPass=data.get('sshPass') or None,
        keyPass=data.get('keyPass') or None,
    )
    db.add(new_db)
    db.flush()  # need new_db.id before writing the key file to disk

    if key_file_bytes:
        save_key_file_to_disk(new_db.id, key_file_name, key_file_bytes, db)

    db.commit()

    return {'ok': True, 'status': 'success', 'message': 'Database connection added successfully.'}


# ------------------------------------------------------------------------------
class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    type: str
    host: str
    port: Optional[int] = None
    db: Optional[str] = None
    user: Optional[str] = None
    status: Optional[str] = "untested"
    ssl: bool = False
    sshHost: Optional[str] = None
    sshPort: Optional[int] = None
    sshUser: Optional[str] = None
    authMode: Optional[str] = "password"
    keyFileName: Optional[str] = None
    last_tested_at: Optional[str] = None

@router.put('/{id}')
async def update_connection(id: int, request: Request, db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id).first()
    if not connection:
        return JSONResponse(status_code=404, content={'status': 'error', 'message': 'Connection not found.'})

    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        data = await request.form()
        key_file = data.get("keyFile")
        key_file_bytes = await key_file.read() if key_file else None
        key_file_name = key_file.filename if key_file else None
        ssl_value = str(data.get('ssl')).lower() == 'true'
    else:
        raw_body = await request.body()
        if not raw_body:
            raise HTTPException(400, "request body is empty — expected a JSON connection payload")
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"request body is not valid JSON: {e}")
        key_file_bytes = None
        key_file_name = None
        ssl_value = bool(data.get('ssl'))

    # non-sensitive fields — always safe to overwrite from the form
    connection.type = data.get('type', connection.type)
    connection.name = data.get('name', connection.name)
    connection.host = data.get('host', connection.host)
    connection.port = int(data['port']) if data.get('port') else connection.port
    connection.db = data.get('db', connection.db)
    connection.user = data.get('user', connection.user)
    connection.ssl = ssl_value
    connection.sshHost = data.get('sshHost') or None
    connection.sshPort = int(data['sshPort']) if data.get('sshPort') else None
    connection.sshUser = data.get('sshUser') or None
    connection.authMode = data.get('authMode') or 'password'

    # password-like fields — the frontend deliberately leaves these blank when opening
    # the edit form (it never ships stored secrets back to the browser), so a blank
    # value here means "leave unchanged", not "clear it"
    if data.get('pass'):
        connection.dbpass = data.get('pass')
    if data.get('sshPass'):
        connection.sshPass = data.get('sshPass')
    if data.get('keyPass'):
        connection.keyPass = data.get('keyPass')

    # editing invalidates whatever the last test result was
    connection.status = 'untested'

    if key_file_bytes:
        save_key_file_to_disk(connection.id, key_file_name, key_file_bytes, db)

    db.commit()

    return {'ok': True, 'status': 'success', 'message': 'Database connection updated successfully.'}




@router.delete('/{id}')
def delete_connection(request: Request, id: int, db: Session = Depends(conn)):
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id).first()
    if not connection:
        return JSONResponse(status_code=404, content={'status': 'error', 'message': 'Connection not found.'})

    # db.delete(connection)
    connection.deleted_at = datetime.now(timezone.utc)
    db.commit()

    return {'ok': True, 'status': 'success', 'message': 'Database connection deleted successfully.'}






# class ConnectionTest(BaseModel):
#     model_config = ConfigDict(from_attributes=True)

#     name: str
#     type: str
#     host: str
#     port: Optional[int] = None
#     db: Optional[str] = None
#     user: str
#     dbpass: str
#     status: Optional[str] = "untested"
#     ssl: bool = False







@router.post('/{id}/test')
def testing_connection(request: Request, id: int, db: Session= Depends(conn)):
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
        "keyPass": connection.keyPass if connection.keyPass else None
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
        "keyPass": connection.keyPass if connection.keyPass else None
    }

    try:
        return list_tables(c)
    except Exception as e:
        raise HTTPException(502, f"couldn't list tables: {e}")