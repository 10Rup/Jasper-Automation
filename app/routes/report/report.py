import platform
import os
import json
from pyexpat import model
import pandas as pd
from pdf2image import convert_from_bytes
from PIL import Image
from google import genai


from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from ...database import SessionLocal
from ...models import ApiMaster, Uploadfile, CropImages, XmlCode, TableDetails
from datetime import datetime, timezone


router = APIRouter(prefix='/corrections', tags=['Test'])
templates = Jinja2Templates("app/templates")
IMAGE_DIR = 'app/images'
CROP_IMAGE_DIR = 'app/cropped_images'
UPLOAD_DIR = "app/TableStructure"
REFERENCE = "app/reference"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.get('/correction')
def jrxml_Upload(request: Request):



    return templates.TemplateResponse(
        request, 
        'report/correection.html'
    )