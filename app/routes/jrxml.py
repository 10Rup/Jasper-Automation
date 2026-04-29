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
from ..models import ApiMaster, Uploadfile, CropImages, XmlCode
from datetime import datetime, timezone


router = APIRouter(prefix='/jrxmls', tags=['Jrxml'])
templates = Jinja2Templates("app/templates")
IMAGE_DIR = 'app/images'
CROP_IMAGE_DIR = 'app/cropped_images'


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Namespace for JRXML
NS = "http://jasperreports.sourceforge.net/jasperreports"
namespaces = {"jr": NS}


def clean_ai_xml(xml):
    return xml.replace("```xml", "").replace("```", "").strip()


def replace_band(root, new_xml_str, band_name):
    try:
        new_elem = ET.fromstring(new_xml_str)
    except Exception as e:
        print(f"Invalid XML for {band_name}: {e}")
        return

    # find existing band node
    old_elem = root.find(f".//jr:{band_name}", namespaces)

    if old_elem is None:
        print(f"{band_name} not found in base template")
        return

    # find parent of old element
    parent = root.find(f".//jr:{band_name}/..", namespaces)

    if parent is None:
        print(f"Parent not found for {band_name}")
        return

    # remove old and insert new
    parent.remove(old_elem)
    parent.append(new_elem)



@router.get('/')
def reports(request: Request, db: Session = Depends(get_db)):

    records = db.query(XmlCode).filter(XmlCode.deleted_at == None).first()

    # for record in records:
        # print(record)

    print(records.bandname)
    return {
        'status':'success',
        'tablecode': records.codes
    }
    # return templates.TemplateResponse(
    #     request,
    #     'test_view.html'
    # )



@router.get('/{report_id}')
def generate_jrxml(report_id: int, db: Session = Depends(get_db)):

    # 1. Load base template
    tree = ET.parse("app/templates/base.jrxml")
    root = tree.getroot()

    # 2. Fetch DB data
    crops = db.query(CropImages).filter(CropImages.uploadfile_id == report_id).all()

    for crop in crops:
        print(crop)

    return {
        'status':'success',
    }
    # # 3. Replace bands
    # for c in crops:
    #     if c.xml_code:
    #         xml = clean_ai_xml(c.xml_code)
    #         replace_band(root, xml, c.bandname)

    # # 4. Convert back to string
    # final_xml = ET.tostring(root, encoding="unicode")

    # return final_xml