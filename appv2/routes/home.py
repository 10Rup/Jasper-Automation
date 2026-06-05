from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..databases.db import conn
from ..models.model import Upload
from datetime import datetime, timezone

import os
from dotenv import load_dotenv


appname = os.getenv("APP_NAME")



router = APIRouter()
templates = Jinja2Templates(f"{appname}/templates")

@router.get('/')
def home(request: Request):

    return templates.TemplateResponse(
        request,
        'home.html'
    )