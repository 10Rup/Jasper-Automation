import os
import platform

from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pdf2image import convert_from_bytes
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import ApiMaster, Uploadfile, CropImages
from datetime import datetime, timezone


router = APIRouter(prefix='/process', tags=['Process'])
templates = Jinja2Templates("app/templates")
IMAGE_DIR = 'app/images'
CROP_IMAGE_DIR = 'app/cropped_images'


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.get('/')
def reports(request: Request):

    return templates.TemplateResponse(
        request,
        'processdemo.html'
    )



@router.get('/{report_id}')
def pdfreports(request: Request, report_id: int, db: Session = Depends(get_db)):

    report = db.query(Uploadfile).filter(Uploadfile.id==report_id).first()

    # print(report.filepath)
    return templates.TemplateResponse(
        request,
        'process.html',
        {
            'report': report
        }
    )
