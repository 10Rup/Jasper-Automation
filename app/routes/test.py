import os
import platform
import xml.etree.ElementTree as ET
from PIL import Image

from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pdf2image import convert_from_bytes
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import ApiMaster, Uploadfile, CropImages, XmlCode, CompileReport
from datetime import datetime, timezone

from ..services import ollmaService, pdfPharse



router = APIRouter(prefix='/ollama', tags=['Jrxml'])
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


@router.get('/testing/{report_id}')
def testing(report_id: int, db: Session = Depends(get_db)):
    # report = db.query(Uploadfile).filter(Uploadfile.id == report_id).first()
    # image_Url = os.path.join(IMAGE_DIR, f'{report.filepath}')
    # image_path = Image.open(image_Url)
    pdf_path = "app/templates/pdf/provitional_report_igu.pdf"
    print(pdf_path)

    
    # result = ollmaService.ollamaClient(prompt1, image_Url)
    layout_data = pdfPharse.readPdf(pdf_path)

    prompt = f"""
        ROLE:
        You are an expert JasperReports JRXML generator.

        TASK:
        Generate valid JRXML.

        LAYOUT_DATA:
        {layout_data}

        RULES:

        1. OUTPUT
        - Return ONLY valid JRXML
        - No markdown
        - No comments
        - No explanations
        - No UUID

        2. ROOT STRUCTURE
        Output format MUST be:

        <summary>
            <band height="HEIGHT">
                ...
            </band>
        </summary>

        3. ELEMENT RULES

        Use:
        - <staticText> for labels/headings
        - <textField> for dynamic values

        Dynamic values include:
        - marks
        - totals
        - percentages
        - names
        - numbers
        - values

        4. FIELD MAPPING

        If text matches a field name semantically:
        Example:
        - TOTAL MARKS -> TOTAL_MARKS
        - STUDENT NAME -> STUDENT_NAME

        Use:

        <textField>
            <reportElement x="" y="" width="" height=""/>
            <textElement textAlignment="Center" verticalAlignment="Middle">
                <font size="10"/>
            </textElement>
            <textFieldExpression><![CDATA[$F{{FIELD_NAME}}]]></textFieldExpression>
        </textField>

        If no field exists:
        Use <staticText>

        5. STYLING
        - Default font size = 10
        - Use textAlignment="Center"
        - Use verticalAlignment="Middle"
        - Keep layout inside A4 width
        - Use boxes only when visually required

        6. BOX FORMAT

        Use ONLY this format:

        <box>
            <topPen lineWidth="1.0" lineColor="#000000"/>
            <leftPen lineWidth="1.0" lineColor="#000000"/>
            <bottomPen lineWidth="1.0" lineColor="#000000"/>
            <rightPen lineWidth="1.0" lineColor="#000000"/>
        </box>

        7. IMAGE FORMAT

        If signature/logo exists:

        <image hAlign="Center" vAlign="Middle" onErrorType="Blank">
            <reportElement x="" y="" width="" height=""/>
            <imageExpression><![CDATA["IMAGE_PATH"]]></imageExpression>
        </image>

        8. FORBIDDEN
        Do NOT use:
        - textAdjust
        - topIndent
        - <text value="">
        - forecolor inside <font>

        9. IMPORTANT
        - Generate accurate x/y coordinates
        - Preserve table alignment
        - Preserve visual structure
        - Keep elements non-overlapping

    """

    system_prompt = """
        You are an expert JasperReports JRXML generator.
        Generate only valid JRXML.
        Never output markdown.
    """
    result = ollmaService.vectorOllama(prompt, system_prompt)
    
    with open("app/generated_reports/output.xml", "w", encoding="utf-8") as f:
        f.write(result)
    # print(result)
    return "done"