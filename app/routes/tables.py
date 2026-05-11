import os
import platform
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pdf2image import convert_from_bytes
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import ApiMaster, Uploadfile, CropImages, XmlCode, CompileReport
from datetime import datetime, timezone




router = APIRouter(prefix='/tables', tags=['Table'])
templates = Jinja2Templates("app/templates")
IMAGE_DIR = 'app/images'
CROP_IMAGE_DIR = 'app/cropped_images'
OUTPUT_DIR = "app/generated_reports"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.get('/')
def home(request: Request):

    return templates.TemplateResponse(
        request,
        'addtable.html'
    )