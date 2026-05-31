import platform
import os
import json
from pdf2image import convert_from_bytes
from PIL import Image
from google import genai

from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from ...database import SessionLocal
from ...models import ApiMaster, Uploadfile, CropImages, XmlCode
from datetime import datetime, timezone



# Services
from app.services.api import imgToCode, compile


router = APIRouter(prefix='/generates', tags=['Prepare'])
templates = Jinja2Templates("app/templates")
IMAGE_DIR = 'app/images'
CROP_IMAGE_DIR = 'app/cropped_images'


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.get('/report/{report_id}/{api_name}')
def prepare_report(api_name: str, report_id : int, request: Request, db: Session = Depends(get_db)):


    # Validate API Key
    key = db.query(ApiMaster).filter(ApiMaster.apiname == api_name).first()
    if key is None:
        return {'status':'error', 'message':'api key missing'}


    #Fetch Report Details
    report = db.query(Uploadfile).filter(Uploadfile.id == report_id, Uploadfile.deleted_at == None).first()

    report_config = {
        'pagesize': report.pagesize,
        'orientation': report.pagedimention,
        'reprot_type': report.filetype
    }

    report_fields = report.fields



    # Fetch Band Image Records
    records = db.query(CropImages).filter(CropImages.uploadfile_id == report_id, CropImages.deleted_at == None).all()




    # Initial JRXML bands with placeholders
    queryString_band = (report.queryString if report.queryString else """<queryString>
		<![CDATA[]]>
	</queryString>""")

    title_band='''<title>
        <band height="79" splitType="Stretch"/>
        </title>'''
    
    
    pageHeader_band='''<pageHeader>
        <band height="79" splitType="Stretch"/>
        </pageHeader>'''
    
    
    columnHeader_band='''<columnHeader>
        <band height="79" splitType="Stretch"/>
        </columnHeader>'''
    
    
    detail_band='''<detail>
        <band height="79" splitType="Stretch"/>
        </detail>'''
    
    
    columnFooter_band='''<columnFooter>
        <band height="79" splitType="Stretch"/>
        </columnFooter>'''
    
    
    pageFooter_band='''<pageFooter>
        <band height="79" splitType="Stretch"/>
        </pageFooter>'''
    
    
    summary_band='''<summary>
        <band height="79" splitType="Stretch"/>
        </summary>'''


    # jrxml_bands = {
    #     'queryString': queryString_band,
    #     'title': title_band,
    #     'pageHeader': pageHeader_band,
    #     'columnHeader': columnHeader_band,
    #     'detail': detail_band,
    #     'columnFooter': columnFooter_band,
    #     'pageFooter': pageFooter_band,
    #     'summary': summary_band
    # }

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

    
    try:
        import time
        for record in records:
    
            if record.bandname in jrxml_bands:


                # Validate Image Path
                image_path = os.path.join(CROP_IMAGE_DIR,record.filepath)

                if not os.path.exists(image_path):
                    return {'status':'error', 'message':'file is missing'}
                
                time.sleep(5) # To avoid hitting API rate limits
                code = imgToCode.img_code(record.bandname,report_fields,report_config,image_path, key.apikey)
                jrxml_bands[record.bandname] = code
                print(f"Processed band: {record.bandname}")
                time.sleep(15) # To avoid hitting API rate limits
                

    except Exception as e:
        return {"status": "error", "message": f"Error Message - {str(e)}"}       


    new_report = compile.compile_report(report_id,report_config, jrxml_bands)


    return new_report