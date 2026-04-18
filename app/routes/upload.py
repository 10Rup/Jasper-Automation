import os
import platform
from pathlib import Path

from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pdf2image import convert_from_bytes
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import ApiMaster, Uploadfile, CropImages
from datetime import datetime, timezone


router = APIRouter(prefix='/upload', tags=['API'])
templates = Jinja2Templates("app/templates")
IMAGE_DIR = 'app/images'
CROP_IMAGE_DIR = 'app/cropped_images'


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.get('/sample')
def api_settings(request: Request, db: Session = Depends(get_db)):

    return templates.TemplateResponse(
        request,
        'uploadsample.html'
    )


@router.post('/add-sample')
async def report_sample_upload(request: Request, reportname: str = Form(...), samplefile: UploadFile = File(...), db: Session = Depends(get_db)):
    
    pdf_bytes = await samplefile.read()
    osModel = platform.system()

    filename = samplefile.filename
    name, ext = os.path.splitext(samplefile.filename)
    print(ext)
    # pdf to image process
    if ext==".pdf":
        if osModel != "Windows":
            images = convert_from_bytes(pdf_bytes, poppler_path="/usr/bin")
        else:
            images = convert_from_bytes(pdf_bytes)
        image_path = os.path.join(IMAGE_DIR, f"{reportname}.png")
        images[0].save(image_path, "PNG")

    new_file = Uploadfile(displayname=reportname, filename=filename, filetype=ext.replace(".",""), filepath=f'/images/{reportname}.png', created_at=datetime.now(timezone.utc))
    db.add(new_file)
    db.commit()

    
    return RedirectResponse(
        url='/reports',
        status_code=303
    )
