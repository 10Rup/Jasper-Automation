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

    xml_path = "app/templates/test.jrxml"
    records = db.query(CropImages).join(XmlCode, XmlCode.crop_id == CropImages.id).filter(CropImages.uploadfile_id == report_id, XmlCode.deleted_at == None).with_entities(XmlCode.codes, CropImages.bandname).all()

    tree = ET.parse(xml_path)
    root = tree.getroot()

    for record in records:

        band_name = record.bandname
        new_xml = record.codes
        # print(f'{band_name} \n {new_xml}')
        try:
            new_tag = ET.fromstring(new_xml)
            # # ✅ FIX: add namespace
            # def add_ns(elem):
            #     if not elem.tag.startswith("{"):
            #         elem.tag = f"{{{NS}}}{elem.tag}"
            #     for child in elem:
            #         add_ns(child)

            # add_ns(new_tag)

        except ET.ParseError:
            print(f"❌ Invalid XML for band: {band_name}")
            continue

        old_tag = root.find(band_name)

        
        if old_tag is not None:
            # sequence maintain
            index = list(root).index(old_tag)
            root.remove(old_tag)
            root.insert(index, new_tag)
        else:
            # if missing then add
            root.append(new_tag)

    
    # print(ET.tostring(root, encoding="unicode"))


    root.tag = f"{{{NS}}}jasperReport"
    root.set("xmlns", NS)
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set(
        "xsi:schemaLocation",
        "http://jasperreports.sourceforge.net/jasperreports http://jasperreports.sourceforge.net/xsd/jasperreport.xsd"
    )
    root.set("name", f"report_{report_id}")
    root.set("pageWidth", "595")
    root.set("pageHeight", "842")
    root.set("columnWidth", "555")
    root.set("leftMargin", "20")
    root.set("rightMargin", "20")
    root.set("topMargin", "20")
    root.set("bottomMargin", "20")
    root.set("uuid", "1a3ec0e9-a736-460b-81a4-fa0e06798b78")




    os.makedirs(OUTPUT_DIR, exist_ok=True)
    file_path = os.path.join(OUTPUT_DIR, f"report_{report_id}.jrxml")
    # ✅ Save NEW file instead of overwriting base
    tree.write(file_path, encoding="utf-8", xml_declaration=True)

    print('generating')
    return 



# update_bands_from_db("report.xml", db_data)
# band_name = record["band_name"]
# new_xml = record["xml_content"]
# db_data = db.query(CropImages).filter(CropImages.report_id == report_id).all()

