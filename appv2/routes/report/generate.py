from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CropImages



from ...databases.db import conn
from ...models.model import Upload, Process

from datetime import datetime, timezone

from ...services.report.generate import generateReport 
from ...services.report.ocr_generate import imgToOcr, buildJson
from ...services.report.geminie_generate import imgToCode
import os
import json
from dotenv import load_dotenv


processed = os.getenv("PROCESS_DIR")
appname = os.getenv("APP_NAME")
apikey = os.getenv("API_KEY")
apikeygeminie = os.getenv("API_KEY_GEMINIE")
output = os.getenv("OUTPUT_DIR")
reference = os.getenv("REFERENCE_DIR")

router = APIRouter(prefix='/report', tags=['Report'])
templates = Jinja2Templates(f"{appname}/templates/report")

@router.get('/generate-ocr/{report_id}')
def generate_report_ocr(request: Request, report_id : int, db: Session = Depends(conn)):
    file = db.query(Upload).filter(Upload.id == report_id).first()
    reports = db.query(Process).filter(Process.upload_id == report_id).all()

    band_images = {}
    
    for report in reports:
       
        band_images[report.bandname] = os.path.join(appname,processed, report.path)   

    print(band_images['detail'])

    lines, width, height  = imgToOcr(band_images['detail']) 

    result = buildJson(band_images['detail'], lines, width, height)
   
    return {'message': 'OCR Report generated','report': result}



@router.get('/generate/{report_id}')
async def generate_report(request: Request, report_id : int, db: Session = Depends(conn)):
    file = db.query(Upload).filter(Upload.id == report_id).first()
    reports = db.query(Process).filter(Process.upload_id == report_id).all()
    fields = {
        "STUDENT_NAME": "string",
        "TOTAL_THEO_MARKS": "integer",
        "TOTAL_THEO_OBT_MARKS": "integer",
    }
    config = {"pagesize": file.size}  # A4
    jrxml_bands = {
        'queryString': "",
        'title': "",
        'pageHeader': "",
        'columnHeader': "",
        'detail': "",
        'columnFooter': "",
        'pageFooter': "",
        'summary': ""
    }
    band_images = {}
    
    for report in reports:
       
        band_images[report.bandname] = os.path.join(appname,processed, report.path)   

    print(band_images)


    result = generateReport(band_images, fields, config, apikey)
    

    # 1. Fetch base jrxml report
    if config.get('pagesize') == "A4":
        base_code = os.path.join(appname,reference, "baseA4Report.jrxml")
    else:
        base_code = os.path.join(appname,reference, "baseA4Report.jrxml") # defaulting to A4 for now    

    # 2. Read base file
    with open(base_code, "r", encoding="utf-8") as f:
        base_xml = f.read()

    # 3. Build final XML (for now just base)
    final_xml = base_xml

    # 4. Update xml code with band codes
    for band, image in band_images.items():
        final_xml += f'\n{result[band]}'
        print(f"Added band {band} to final XML")


    # # final_xml += f'\n{result["queryString"]}'
    # # final_xml += f'\n{result["title"]}'
    # # final_xml += f'\n{result["pageHeader"]}'
    # # final_xml += f'\n{result["columnHeader"]}'
    # # final_xml += f'\n{result["detail"]}'
    # # final_xml += f'\n{result["columnFooter"]}'
    # # final_xml += f'\n{result["pageFooter"]}'
    # # final_xml += f'\n{result["summary"]}'


    print("Building jzxml report......")

    # 5. Ensure closing tag exists
    if not final_xml.strip().endswith("</jasperReport>"):
        final_xml += "\n</jasperReport>"

    # 6. Save file
    # os.makedirs(OUTPUT_DIR, exist_ok=True)
    download_path_name = f"report_{report_id}.jrxml"
    file_path = os.path.join(appname, output, download_path_name )
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_xml)

    print(f"Report compiled successfully at {file_path}")


    # return {'message': 'Report generated','report': final_xml}

    return FileResponse(
        path=file_path, 
        filename=download_path_name,  # The name the user will see
        media_type="application/pdf"
    )




@router.get('/generate/geminie/{report_id}')
def generate_report(request: Request, report_id: int, db: Session = Depends(conn)):

    processed_reports = db.query(Process).filter(Process.upload_id == report_id).all()

    return templates.TemplateResponse(
        request,
        'generate.html',
        {
            'reports': processed_reports
        }

    )


@router.get('/generate-geminie/{report_id}')
def generate_report(request: Request, report_id: int, db: Session = Depends(conn)):

    file = db.query(Upload).filter(Upload.id == report_id).first()
    # reports = db.query(Process).filter(Process.upload_id == report_id).all()
    fields = {
        "STUDENT_NAME": "string",
        "TOTAL_THEO_MARKS": "integer",
        "TOTAL_THEO_OBT_MARKS": "integer",
    }
    config = {"pagesize": file.size}  # A4
    jrxml_bands = {
        'queryString': "",
        'title': "",
        'pageHeader': "",
        'columnHeader': "",
        'detail': "",
        'columnFooter': "",
        'pageFooter': "",
        'summary': ""
    }

    band_images = {}
    result = ""
    
    for band in jrxml_bands.keys():
       

        report = db.query(Process).filter(Process.upload_id == report_id, Process.bandname == band).first()

        if not report:
            continue


        band_images[band] = os.path.join(appname,processed, report.path)

        if report and report.code:
            print(f"Band {report.bandname} already has code, skipping generation.")
            continue  # Skip if code already exists

        print(f"Generating code for band {report.bandname}")
        result = imgToCode(report.bandname, fields, config, band_images[band], apikeygeminie)
        report.code = result  # Save the generated code to the database
        db.commit()  # Commit the changes to the database
        print("✓")



    # 1. Fetch base jrxml report
    if config.get('pagesize') == "A4":
        base_code = os.path.join(appname,reference, "baseA4Report.jrxml")
    else:
        base_code = os.path.join(appname,reference, "baseA4Report.jrxml") # defaulting to A4 for now    

    # 2. Read base file
    with open(base_code, "r", encoding="utf-8") as f:
        base_xml = f.read()

    # 3. Build final XML (for now just base)
    final_xml = base_xml

    # 4. Update xml code with band codes
    for band, image in band_images.items():
        report = db.query(Process).filter(Process.upload_id == report_id, Process.bandname == band).first()
        final_xml += f'\n{report.code}'
        print(f"Added band {band} to final XML")


    print("Building jzxml report......")

    # 5. Ensure closing tag exists
    if not final_xml.strip().endswith("</jasperReport>"):
        final_xml += "\n</jasperReport>"

    # 6. Save file
    # os.makedirs(OUTPUT_DIR, exist_ok=True)
    download_path_name = f"report_{report_id}.jrxml"
    file_path = os.path.join(appname, output, download_path_name )
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_xml)

    print(f"Report compiled successfully at {file_path}")


    # return {'message': 'Report generated','report': final_xml}

    return FileResponse(
        path=file_path, 
        filename=download_path_name,  # The name the user will see
        media_type="application/pdf"
    )



