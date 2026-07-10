from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session




from ...databases.db import conn
from ...models.model import Upload, Process, Dbcredentials

from datetime import datetime, timezone
 
from ...services.dbconn.dbTesting import test_connection
import os
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from typing import Optional

appname = os.getenv("APP_NAME")


router = APIRouter(prefix='/db', tags=['Connections'])
templates = Jinja2Templates(f"{appname}/templates/dbconn")


@router.post('/add')
async def add_connection(request: Request, db: Session = Depends(conn)):
    data = await request.json()
    # 'type': 'mysql', 'name': 'localhost', 'host': 'localhost', 'port': '3306', 'db': '45435435', 'user': 'root', 'pass': '', 'ssl': False, 'sshHost': '', 'sshPort': '', 'sshUser': '', 'authMode': 'password', 'sshPass': '', 'keyPass': ''}

    # print(data)
    
    new_db = Dbcredentials(
        type=data.get('type'),
        name=data.get('name'),
        host=data.get('host'),
        port=data.get('port'),
        db=data.get('db'),
        user=data.get('user'),
        dbpass=data.get('pass')


    )
    db.add(new_db)
    db.commit()

    return {'ok': True, 'status': 'success', 'message': 'Database connection added successfully.'}


@router.put('/{id}')
async def update_connection(id: int, request: Request, db: Session = Depends(conn)):
    data = await request.json()
    connection = db.query(Dbcredentials).filter(Dbcredentials.id == id).first()
    if not connection:
        return JSONResponse(status_code=404, content={'status': 'error', 'message': 'Connection not found.'})

    connection.type = data.get('type', connection.type)
    connection.name = data.get('name', connection.name)
    connection.host = data.get('host', connection.host)
    connection.port = data.get('port', connection.port)
    connection.db = data.get('db', connection.db)
    connection.user = data.get('user', connection.user)
    connection.dbpass = data.get('pass', connection.dbpass)

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


class ConnectionTest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    type: str
    host: str
    port: Optional[int] = None
    db: Optional[str] = None
    user: str
    dbpass: str
    status: Optional[str] = "untested"
    ssl: bool = False

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