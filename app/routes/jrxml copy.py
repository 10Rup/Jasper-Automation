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

# Namespace for JRXML
NS = "http://jasperreports.sourceforge.net/jasperreports"
namespaces = {"jr": NS}


def clean_ai_xml(xml):
    return xml.replace("```xml", "").replace("```", "").strip()

def add_namespace(elem):
    if not elem.tag.startswith("{"):
        elem.tag = f"{{{NS}}}{elem.tag}"
    for child in elem:
        add_namespace(child)

# v1
# def replace_band(root, new_xml_str, band_name):
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


# v2
# def replace_band(root, new_xml_str, band_name):
    try:
        new_elem = ET.fromstring(new_xml_str)
    except Exception as e:
        print(f"Invalid XML for {band_name}: {e}")
        return

    # find existing element
    old_elem = root.find(f".//jr:{band_name}", namespaces)

    if old_elem is None:
        print(f"{band_name} not found")
        return

    parent = root.find(f".//jr:{band_name}/..", namespaces)

    # find index of old element
    index = list(parent).index(old_elem)

    # remove old
    parent.remove(old_elem)

    # insert at SAME position
    parent.insert(index, new_elem)


def replace_band(root, new_xml_str, band_name):
    try:
        new_elem = ET.fromstring(new_xml_str)

        # ✅ ADD THIS LINE (THIS IS WHERE IT GOES)
        add_namespace(new_elem)

    except Exception as e:
        print(f"Invalid XML for {band_name}: {e}")
        return

    old_elem = root.find(f".//jr:{band_name}", namespaces)

    if old_elem is None:
        print(f"{band_name} not found in base template")
        return

    parent = root.find(f".//jr:{band_name}/..", namespaces)

    if parent is None:
        print(f"Parent not found for {band_name}")
        return

    # ✅ preserve correct position
    index = list(parent).index(old_elem)

    parent.remove(old_elem)
    parent.insert(index, new_elem)


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
 

# v1
# @router.post('/generate/{report_id}')
# def generate_jrxml(report_id: int, db: Session = Depends(get_db)):

    # 1. Load base template
    tree = ET.parse("app/templates/base.jrxml")
    root = tree.getroot()

    # 2. Fetch DB data
    crops = db.query(CropImages).join(XmlCode, XmlCode.crop_id == CropImages.id).filter(CropImages.uploadfile_id == report_id).with_entities(XmlCode.codes,XmlCode.crop_id,CropImages.bandname).all()


    
    # 3. Replace bands
    for c in crops:
        if c.codes:
            xml = clean_ai_xml(c.codes)
            replace_band(root, xml, c.bandname)

    # 4. Convert back to string
    final_xml = ET.tostring(root, encoding="unicode")


    # save report in storage
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    file_path = os.path.join(OUTPUT_DIR, f"report_{report_id}.jrxml")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_xml)
    
    # import xml.dom.minidom as md
    # pretty_xml = md.parseString(final_xml).toprettyxml()
    
    # return final_xml
    return {
        'status':'success',
        'file':final_xml,
        "download_url": f"/jrxmls/download/{report_id}"
    }

@router.post('/generate/{report_id}')
def generate_jrxml(report_id: int, db: Session = Depends(get_db)):

    # 1. Load base template
    tree = ET.parse("app/templates/base.jrxml")
    root = tree.getroot()

    # 2. Fetch DB data
    crops = db.query(CropImages)\
        .join(XmlCode, XmlCode.crop_id == CropImages.id)\
        .filter(CropImages.uploadfile_id == report_id)\
        .with_entities(XmlCode.codes, CropImages.bandname)\
        .all()

    # 3. GROUP BY BAND (IMPORTANT FIX)
    band_map = {}

    for c in crops:
        if c.codes:
            band_map.setdefault(c.bandname, []).append(c.codes)

    # 4. PROCESS EACH BAND
    for band, xml_list in band_map.items():

        combined_elements = []

        for xml in xml_list:
            clean = clean_ai_xml(xml)

            try:
                elem = ET.fromstring(clean)

                # find band content
                band_node = elem.find(".//band")

                if band_node is not None:
                    for child in list(band_node):
                        combined_elements.append(child)

            except Exception as e:
                print("Invalid XML block:", e)

        # skip empty
        if not combined_elements:
            continue

        # create new band wrapper
        band_root = ET.Element(band)
        band_child = ET.SubElement(band_root, "band")
        band_child.set("height", "60")
        band_child.set("splitType", "Stretch")

        for el in combined_elements:
            band_child.append(el)

        # convert to string
        new_xml = ET.tostring(band_root, encoding="unicode")

        # replace in base
        replace_band(root, new_xml, band)

    # 5. FINAL XML
    final_xml = ET.tostring(root, encoding="unicode")

    # 6. SAVE FILE
    OUTPUT_DIR = "app/generated_reports"
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    file_path = os.path.join(OUTPUT_DIR, f"report_{report_id}.jrxml")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_xml)

    return {
        "status": "success",
        "file_path": file_path,
        "download_url": f"/jrxmls/download/{report_id}"
    }



@router.get("/download/{report_id}")
def download_jrxml(report_id: int):
    file_path = f"app/generated_reports/report_{report_id}.jrxml"

    return FileResponse(
        file_path,
        media_type="application/xml",
        filename=f"report_{report_id}.jrxml"
    )