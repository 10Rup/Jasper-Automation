from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CropImages



from ...databases.db import conn
from ...models.model import Upload, Process

from datetime import datetime, timezone

from ...services.report.upload import pdfToImg 
from ...services.report.process import saveRegion
import os
from dotenv import load_dotenv


appname = os.getenv("APP_NAME")


router = APIRouter(prefix='/report', tags=['Report'])
templates = Jinja2Templates(f"{appname}/templates/report")


@router.get('/correction')
def correction(request: Request, db: Session = Depends(conn)):

    reports = db.query(Upload).filter(Upload.type == 'jrxml').order_by(Upload.id.desc()).all()
    return templates.TemplateResponse(
        request, 
        'correction.html',

        {
            'reports': reports
        }
    )