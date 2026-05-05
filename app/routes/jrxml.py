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


router = APIRouter(prefix='/jrxmls', tags=['Jrxml'])
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


NS = "http://jasperreports.sourceforge.net/jasperreports"
namespaces = {"jr": NS}

@router.post('/compile/{report_id}')
def compile_report(data: dict, request: Request, report_id: int, db: Session = Depends(get_db)):
    file_name = data.get('filename')
    report = db.query(CompileReport).filter(CompileReport.uploadfile_id == report_id, CompileReport.is_processed== True).first()
    if report:
        return {'status':'Report Already Compiled', 'redirect':'/reports/Combine'}

    new_report = CompileReport(uploadfile_id = report_id, filename = file_name, is_processed = True, created_at=datetime.now(timezone.utc) )
    db.add(new_report)
    db.commit()
    return {'status':'Report Compiled', 'redirect':'/reports/Combine'}
 


@router.post('/generate/{report_id}')
def generate_jrxml(report_id: int, db: Session = Depends(get_db)):

    xml_path = "app/templates/baseA4Report.jrxml"

    record = db.query(Uploadfile)\
        .filter(Uploadfile.id == report_id, Uploadfile.deleted_at == None)\
        .first()

    # 1. Read base file
    with open(xml_path, "r", encoding="utf-8") as f:
        base_xml = f.read()

    # 2. Build final XML (for now just base)
    final_xml = base_xml

    # Update xml code with band codes
    final_xml += f'\n{record.queryString}'
    final_xml += f'\n{record.title}'
    final_xml += f'\n{record.pageHeader}'
    final_xml += f'\n{record.columnHeader}'
    final_xml += f'\n{record.detail}'
    final_xml += f'\n{record.columnFooter}'
    final_xml += f'\n{record.pageFooter}'
    final_xml += f'\n{record.summary}'


    # 3. Ensure closing tag exists
    if not final_xml.strip().endswith("</jasperReport>"):
        final_xml += "\n</jasperReport>"

    # 4. Save file
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    file_path = os.path.join(OUTPUT_DIR, f"report_{report_id}.jrxml")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_xml)

    return {
        "status": "success",
        "file_path": file_path
    }



# update_bands_from_db("report.xml", db_data)
# band_name = record["band_name"]
# new_xml = record["xml_content"]
# db_data = db.query(CropImages).filter(CropImages.report_id == report_id).all()

