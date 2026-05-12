import os
import platform
import xml.etree.ElementTree as ET
import json

from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pdf2image import convert_from_bytes
from sqlalchemy import JSON, func
from sqlalchemy.orm import Session
from ...database import SessionLocal
from ...models import ApiMaster, Uploadfile, CropImages, XmlCode, CompileReport, TableDetails
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
def home(request: Request, db: Session = Depends(get_db)):
    tables = db.query(TableDetails).all()
    
    return templates.TemplateResponse(
        request,
        'tables/home.html',
        {
            'tables': tables
        }
    )

@router.get('/add-table')
def home(request: Request):

    
    return templates.TemplateResponse(
        request,
        'tables/add.html'
    )


@router.get('/edit-table/{table_id}')
def edit_table(request: Request):

    return templates.TemplateResponse(
        request,
        'tables/edit.html'
    )
    
    

@router.post('/save-table')
def save_table_data(request: Request, columnlist: str = Form(...), dbname: str = Form(...), tbname: str = Form(...), descpt: str = Form(...), db: Session = Depends(get_db)):

    columnlist = [col.strip() for col in columnlist.split(',') if col.strip()]
    table = TableDetails(databasename = dbname, tablename = tbname, columnlist = columnlist, discription = descpt)
    db.add(table)
    db.commit()

    return RedirectResponse(
        url='/tables/',
        status_code=303
    )