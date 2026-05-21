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


router = APIRouter(prefix='/tests', tags=['Test'])
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



@router.get('/correction/{report_id}')
def correction(report_id: int, db: Session = Depends(get_db)):

    api_key = db.query(ApiMaster).filter(ApiMaster.apiname == 'geminie').first()
    if not api_key:
        return {'status': 'error', 'message':'issue with api key'}

    jrxml_path = os.path.join(REFERENCE, 'NEP_MARKSHEET_DURG.jrxml')

    with open(jrxml_path, "r", encoding="utf-8") as f:
        existing_jrxml = f.read()

    extra = """
        1. Report size changed to A4 landscape
        2. 
    """

    try:
        
        prompt = f"""
            You are a JasperReports JRXML expert.

            You are given:

            1. Existing JRXML report
            2. Output reference image showing expected design

            Your task:
            Modify the EXISTING JRXML to match the reference image as accurately as possible.

            IMPORTANT RULES:
            1. Preserve existing JRXML structure whenever possible
            2. Modify ONLY required sections
            3. Keep existing field names and expressions if already correct
            4. Correct:
            - alignment
            - spacing
            - fonts
            - borders
            - widths/heights
            - table structure
            - labels
            - dynamic fields
            5. Use <textField> for dynamic data
            6. Use <staticText> for labels/headings
            7. Do NOT generate UUID
            8. Do NOT generate comments
            9. Do NOT generate markdown
            10. Output ONLY valid JRXML XML
            11. Keep JRXML schema valid
            12. Preserve band structure
            13. Do not remove fields unless necessary


            ADDITIONAL CORRECTIONS:
            {extra}

            EXISTING JRXML:
            ------------------------
            {existing_jrxml}
            ------------------------

            Now analyze the image carefully and return the corrected JRXML.
        """

        filepath ="durg_marksheet_new_format.png"
        image_path = os.path.join(REFERENCE,filepath) 
        
        img = Image.open(image_path)


        client = genai.Client(api_key=api_key.apikey)
        model = "gemini-3-flash-preview"
        
        response = client.models.generate_content(
            model=model,
            contents=[prompt, img]
        )

        raw_text = response.text.strip()

        # 🔥 Clean possible markdown
        # raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        print(raw_text)
        return raw_text
        
        
    except Exception as e:
        print("Gemini Error:", e)
        return {'status':'error', 'message': 'Gemini Error'}