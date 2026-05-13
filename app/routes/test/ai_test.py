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
from ...models import ApiMaster, Uploadfile, CropImages, XmlCode, TableDetails
from datetime import datetime, timezone


router = APIRouter(prefix='/tests', tags=['Test'])
templates = Jinja2Templates("app/templates")
IMAGE_DIR = 'app/images'
CROP_IMAGE_DIR = 'app/cropped_images'


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get('/query')
def generate_query(report_id: int, db: Session = Depends(get_db)):

    record = db.query(TableDetails).filter(TableDetails.isactive == True).first()
    query = record.report_query
    data =[]
    for x in query.split(','):
        data.append(x.strip())
    print(data)
    
    # api_key = db.query(ApiMaster).filter(ApiMaster.apiname == 'geminie').first()
    # if not api_key:
    #     return {'status': 'error', 'message':'issue with api key'}

    # try:
    #     client = genai.Client(api_key=api_key.apikey)
    #     model = "gemini-3-flash-preview"

    #     prompt = f"""
    #         You are a SQL parser.

    #         Extract ONLY column names from this SQL query.

    #         Rules:
    #         - Return ONLY a JSON array
    #         - No explanation
    #         - No extra text
    #         - No markdown
    #         - No code block
    #         - No duplicate value or fields
    #         - Only column names
    #         - Use alias if present (AS)
    #         - Remove table prefixes
    #         - Convert to UPPERCASE

    #         Example:
    #         Input: SELECT a.marks AS total, b.name FROM table
    #         Output: ["TOTAL", "NAME"]

    #         Query:
    #         {query}
    #     """

    #     response = client.models.generate_content(
    #         model=model,
    #         contents=prompt
    #     )

    #     raw_text = response.text.strip()

    #     # 🔥 Clean possible markdown
    #     raw_text = raw_text.replace("```json", "").replace("```", "").strip()

    #     columns = json.loads(raw_text)

    #     code = build_fields_from_db(query,columns)

    #     if columns:
    #         record.queryString = code
    #         record.fields = columns
    #         db.commit()
    #         # return columns
    #         return {'status':'success','message':'Query Read Successfully!'}

        
    #     return {'status':'error','message':'api unable to read the query'}
        
    # except Exception as e:
    #     print("Gemini Error:", e)
    #     return {'status':'error', 'message': 'Gemini Error'}