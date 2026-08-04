from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...databases.db import conn
from ...models.model import Upload, Process, Dbcredentials

from datetime import datetime, timezone

import os
import json
from dotenv import load_dotenv
from sql_metadata import Parser
from pydantic import BaseModel, ConfigDict
from typing import Optional


processed = os.getenv("PROCESS_DIR")
appname = os.getenv("APP_NAME")


router = APIRouter(prefix='/db', tags=['Connections'])
templates = Jinja2Templates(f"{appname}/templates/dbconn")


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
    ssh_key_id: Optional[int] = None
    keyFileName: Optional[str] = None
    

@router.get('/view', response_model=list[ConnectionOut])
def view_connections(db: Session = Depends(conn)):
    return db.query(Dbcredentials).filter(Dbcredentials.deleted_at.is_(None)).all()



@router.get('/')
def view_connections(request: Request, db: Session = Depends(conn)):

    return templates.TemplateResponse(
        request,
        'view.html'
    )

