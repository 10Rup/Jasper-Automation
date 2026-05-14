import platform
import os
import json
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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.get('/query/{report_id}')
def generate_query(report_id: int, db: Session = Depends(get_db)):

    relationships = [
        "TRPRINTSTUDENTDETAILS.TRCOURSECODE=TRCOURSEMASTER.TRCOURSECODE",
        "TRPRINTSTUDENTDETAILS.STUDENTCODE=TRPRINTSTUDENT_ROWS.STUDENTCODE","TRPRINTSTUDENTDETAILS.TRCOURSECODE=TRPRINTSTUDENT_ROWS.TRCOURSECODE",
        "TRPRINTSTUDENT_ROWS.TRCOURSECODE=TRCOURSEMASTER.TRCOURSECODE",
    ]

    record = db.query(TableDetails).filter(TableDetails.isactive == True).all()
    table_data = []

    for x in record:

        path = os.path.join(UPLOAD_DIR, x.filepath)

        df = pd.read_excel(path)

        columns = []

        for col, dtype in zip(df.columns, df.dtypes):
            columns.append({
                "column_name": col,
                "datatype": str(dtype)
            })

        # sample_data = df.head(3).to_dict(orient="records")
        sample_data = (df.head(3).fillna("").astype(str).to_dict(orient="records"))

        table_data.append({
            'database_name': x.databasename,
            "table_name": x.tablename,
            "columns": columns,
            "sample_data": sample_data
        })
    

    api_key = db.query(ApiMaster).filter(ApiMaster.apiname == 'geminie').first()
    if not api_key:
        return {'status': 'error', 'message':'issue with api key'}


    try:
        client = genai.Client(api_key=api_key.apikey)
        model = "gemini-3-flash-preview"

        prompt = f"""
            You are a Senior SQL Query Optimization Expert.

            Generate a production-ready optimized SQL query.

            Database:
            - MySQL
            - Database Name: demo

            Report Type:
            - Marksheet / Grade Card

            Primary Table:
            - TRPRINTSTUDENTDETAILS

            Relationships:
            {relationships}

            Rules:
            1. Use only provided tables and columns
            2. Never hallucinate columns
            3. Never use SELECT *
            4. Use optimized INNER JOIN or LEFT JOIN
            5. Use meaningful aliases
            6. Query should support large-scale data
            7. Avoid unnecessary nested queries
            8. Use aggregation only where required
            9. Use proper GROUP BY
            10. Return ONLY JSON
            11. No markdown
            12. No explanations
            13. Always use deleted_at is null check.

            Expected Output:
            - Student Name
            - Roll Number
            - Subject Name
            - Marks
            - Grade
            - Total
            - Percentage
            - Result
            - College Name
            - Course Name
            - Semester
            - Session

            Table Structures:
            {json.dumps(table_data, indent=2)}

            Return Format:
            "query": "SQL QUERY"
            
        """


        # Get image path from report_id
        report = db.query(Uploadfile).filter(Uploadfile.id == report_id, Uploadfile.deleted_at == None).first()
        
        image_path = os.path.join(IMAGE_DIR,report.filepath) 
        
        # Load the image
        img = Image.open(image_path)

        response = client.models.generate_content(
            model=model,
            contents=[prompt, img]
        )

        raw_text = response.text.strip()

        # 🔥 Clean possible markdown
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()

        return raw_text
        
        # return {'status':'error','message':'api unable to read the query'}
        
    except Exception as e:
        print("Gemini Error:", e)
        return {'status':'error', 'message': 'Gemini Error'}