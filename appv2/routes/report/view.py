from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session



from ...databases.db import conn
from ...models.model import Upload

from datetime import datetime, timezone

from ...services.report.upload import pdfToImg
import os
from dotenv import load_dotenv


appname = os.getenv("APP_NAME")


router = APIRouter(prefix='/report', tags=['Report'])
templates = Jinja2Templates("appv2/templates/report")

@router.get('/')
def home(request: Request):

    return templates.TemplateResponse(
        request,
        'view.html'
    )


@router.get('/view')
def upload(request: Request, db: Session = Depends(conn)):

    reports = db.query(Upload).all()
    return templates.TemplateResponse(
        request,
        'view.html',
        {
            'reports': reports,
            'appname': appname
        }
    )

