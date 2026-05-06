import os
import platform
import xml.etree.ElementTree as ET
from PIL import Image

from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pdf2image import convert_from_bytes
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import ApiMaster, Uploadfile, CropImages, XmlCode, CompileReport
from datetime import datetime, timezone

from ..services import ollmaService


router = APIRouter(prefix='/ollama', tags=['Jrxml'])
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


@router.get('/testing/{report_id}')
def testing(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Uploadfile).filter(Uploadfile.id == report_id).first()
    image_Url = os.path.join(IMAGE_DIR, f'{report.filepath}')
    image_path = Image.open(image_Url)
    prompt = """
    You are a professional Jasper Report Developer,
    one image is shared to you use it and create a jrxml report.
    Provide cleane and accurate code,
    if have any doubt then send the doubt in the response for us to read and understand it and resolve the issue fast for next request to generate the report code.

    
    """

    prompt1 = 'wwhich model of yours is good for reading image file and using it to create a jrxml report.'
    p2 = 'i need the ollama api model name that can process image and then give me the jrxml code and if the api is cloud base then its very good'
    result = ollmaService.ollamaClient(prompt1, image_Url)
    return result