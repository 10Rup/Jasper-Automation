from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CropImages



from ...databases.db import conn
from ...models.model import Upload, Process

from datetime import datetime, timezone

from ...services.report.upload import pdfToImg,uploadExcelSave
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

@router.get('/correction-upload/{report_id}')
def upload_correction(request: Request, report_id: int):

    return templates.TemplateResponse(
        request,
        'correction_upload.html',
        {
            'report_id': report_id
        }
    )

@router.post('/correction-upload/{report_id}')
async def upload_correction(request: Request, reportname: str = Form(...), report_type: str = Form(...),  samplefile: UploadFile = File(...), db: Session = Depends(conn)):

    filename = samplefile.filename
    name, ext = os.path.splitext(samplefile.filename)
    content = await samplefile.read()
        
    file_path = uploadExcelSave(samplefile.filename, content, db)
    
    return {'msg':file_path}
    