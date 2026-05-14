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

    primary_table = "TRPRINTSTUDENTDETAILS"
    report_type = "Marks Sheet / Grade card"

    record = db.query(TableDetails).filter(TableDetails.isactive == True).all()
    schema_data = []

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

        schema_data.append({
            "table_name": x.tablename,
            "columns": columns,
            "sample_data": sample_data
        })
    

    api_key = db.query(ApiMaster).filter(ApiMaster.apiname == 'geminie').first()
    if not api_key:
        return {'status': 'error', 'message':'issue with api key'}


    try:
        
        prompt = f"""
            You are a Senior MySQL Database Architect with 15+ years of experience writing
            production queries for academic ERP systems. You never guess column names —
            you only use columns that are explicitly listed in the provided schema.

            ═══════════════════════════════════════════════
            TASK
            ═══════════════════════════════════════════════
            Generate a single, optimized, production-ready MySQL 8.0 or higher SELECT query for:
            • Database        : demo
            • Report type     : {report_type}
            • Primary table   : {primary_table}

            ═══════════════════════════════════════════════
            STEP 1 — ANALYZE THE REPORT IMAGE FIRST
            ═══════════════════════════════════════════════
            Before writing any SQL, study the attached report image carefully:
            1. Identify EVERY visible column header in the output table.
            2. Identify any grouping visible (e.g., subject-wise rows per student,
                semester-wise sections, course blocks).
            3. Identify any aggregate values shown (Total Marks, Percentage, Result).
            4. Note the ORDER in which rows appear (student → subject, or semester → student).
            5. Map each visible column to the schema below. If a column is calculated
                (e.g. Percentage = obtained/total * 100), derive it with SQL arithmetic.
                NEVER hallucinate columns not in the schema.

            ═══════════════════════════════════════════════
            STEP 2 — REQUIRED OUTPUT COLUMNS
            ═══════════════════════════════════════════════
            The final SELECT must produce (in this order, using meaningful aliases):
            student_name        — full name of the student
            roll_number         — enrollment / roll no
            college_name        — institution name
            course_name         — degree / program name
            semester            — current semester label
            session             — academic session (e.g. 2023-24)
            subject_name        — individual subject / paper name
            marks_obtained      — marks scored in that subject
            total_marks         — maximum marks for that subject
            grade               — letter grade for that subject
            percentage          — calculated as ROUND((marks_obtained / total_marks) * 100, 2)
            result              — PASS / FAIL or equivalent field

            If the report image shows additional columns not listed above, ADD them.
            If the report image omits any column above, STILL include it (it may be needed
            for grouping or filtering even if not displayed).

            ═══════════════════════════════════════════════
            STEP 3 — JOIN STRATEGY
            ═══════════════════════════════════════════════
            Use only these tables and their documented relationships:

            {json.dumps(relationships, indent=2)}

            Rules:
            • Use INNER JOIN when the relationship is mandatory (every student has a course).
            • Use LEFT JOIN when the related data might be missing (optional subjects, electives).
            • Always alias every table with a short, meaningful alias (e.g. sd, st, sb).
            • Never use implicit joins (comma syntax).
            • Never SELECT * — name every column explicitly.
            • Always add   <alias>.deleted_at IS NULL   for EVERY table that has a deleted_at
                column (check the schema; do not assume).

            ═══════════════════════════════════════════════
            STEP 4 — GROUP BY, GROUP_CONCAT & AGGREGATION
            ═══════════════════════════════════════════════
            Apply the following logic based on what you see in the report image:

            a) If the report shows ONE ROW per student (subjects merged into a single cell):
                → Use GROUP_CONCAT(sb.subject_name ORDER BY sb.subject_name SEPARATOR ', ')
                    and SUM / AVG for marks.
                → GROUP BY: student identifier columns + college + course + semester + session.

            b) If the report shows MULTIPLE ROWS per student (one per subject):
                → Do NOT use GROUP_CONCAT. Keep one row per subject.
                → GROUP BY: all non-aggregated SELECT columns.

            c) If the report shows TOTALS / GRAND TOTALS:
                → Add a secondary query or use WITH ROLLUP only if appropriate.
                → Prefer computing totals inline: SUM(...) OVER (PARTITION BY student_id)
                    as a window function if needed.

            d) Always apply GROUP BY to ALL non-aggregated columns in SELECT.
                Missing a column from GROUP BY is a fatal error.

            ═══════════════════════════════════════════════
            STEP 5 — ORDERING
            ═══════════════════════════════════════════════
            Apply ORDER BY to produce a report-ready result set:

            ORDER BY
                college_name   ASC,
                course_name    ASC,
                semester       ASC,
                session        ASC,
                roll_number    ASC,
                subject_name   ASC   -- remove if GROUP_CONCAT is used

            If the report image shows a different sort order, MATCH IT exactly.

            ═══════════════════════════════════════════════
            STEP 6 — PERFORMANCE RULES (10 000+ rows)
            ═══════════════════════════════════════════════
            Write the query so it can handle large datasets efficiently:

            1. Filter early: put the most selective WHERE conditions on the driving table
                ({primary_table}) to reduce rows before joining.
            2. Never wrap join-key columns in functions inside WHERE/JOIN ON
                (e.g. do NOT write WHERE YEAR(created_at) = 2024 — use a range instead).
            3. Use covering-index-friendly column order in WHERE and JOIN ON
                (match the likely index: student_id, semester, session).
            4. Avoid correlated subqueries — use JOINs or CTEs instead.
            5. If a derived column (e.g. percentage) is needed only in HAVING or ORDER BY,
                compute it once with a CTE or subquery alias — do not repeat the expression.
            6. Use CTEs (WITH ...) when the logic has more than 2 levels of nesting.
            7. Do NOT use SELECT DISTINCT as a substitute for a correct GROUP BY.

            ═══════════════════════════════════════════════
            SCHEMA (source of truth — use ONLY these columns)
            ═══════════════════════════════════════════════
            {schema_data}

            ═══════════════════════════════════════════════
            OUTPUT CONTRACT
            ═══════════════════════════════════════════════
            Return ONLY a single JSON object. No markdown. No backticks. No explanation.
            No preamble. No trailing text. The JSON must be valid and parseable.

            Schema:
            {{
            "query": "<full SQL string, newlines escaped as \\n>",
            "group_by_strategy": "per_subject | per_student_concat",
            "uses_group_concat": true | false,
            "aggregated_columns": ["list", "of", "aggregated", "aliases"],
            "join_count": <integer>,
            "notes": "<one sentence: any assumption made due to missing schema info>"
            }}
        """


        # Get image path from report_id
        report = db.query(Uploadfile).filter(Uploadfile.id == report_id, Uploadfile.deleted_at == None).first()
        
        image_path = os.path.join(IMAGE_DIR,report.filepath) 
        
        # Load the image
        img = Image.open(image_path)


        client = genai.Client(api_key=api_key.apikey)
        model = "gemini-3-flash-preview"
        
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