import os
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
from ..database import SessionLocal
from ..models import ApiMaster, Uploadfile, CropImages, XmlCode
from datetime import datetime, timezone


router = APIRouter(prefix='/prepare', tags=['Prepare'])
templates = Jinja2Templates("app/templates")
IMAGE_DIR = 'app/images'
CROP_IMAGE_DIR = 'app/cropped_images'


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.post('/image-to-xml')
async def image_to_xml(request: Request, db: Session = Depends(get_db)):
    
    data = await request.json()
    apiname = data['apiname']
    band = data['bandname']
    reportpath = data['reportpath']
    extra = data['extrapromt']
    

    image_path = os.path.join(CROP_IMAGE_DIR,reportpath)

    if not os.path.exists(image_path):
        return {'status':'error', 'message':'file is missing'}
    
    try:
        # Load the image
        img = Image.open(image_path)

        prompt = f"""
        You are a JasperReports expert.

        Use the following reference JRXML as a STYLE GUIDE only.
        Do NOT copy blindly. Adapt based on the image.
        If reference JRXML not found don't worry.


        


        Now analyze the image and generate JRXML for <{band}>.

        Mandatory Rules:
        1. Use <staticText> for all elements
        2. Proper (x, y, width, height)
        3. Use <box><pen lineWidth="1.0" lineColor="#000000"/></box> not for all, use it if it is required
        4. STRICT font hierarchy:
            <textElement><font/></textElement>
        5. textAlignment="Center", verticalAlignment="Middle"
        6. Extract exact text
        7. NO UUID
        8. NO comments
        9. NO markdown
        10. Output ONLY valid XML inside <{band}>...</{band}>
        11. If page size is mention then try to keed the desing with in the alloted width and height and by default the report page will be A4 size.
        12. Avoide using 
            <text value="text" />

        13. Correct Way
            <text value="text" /> this is correct way.
        



        {f"Additional instructions: {extra}" if extra else ""}
        """
        # Use the client to generate content
        if apiname == 'geminie':
            api_key = db.query(ApiMaster).filter(ApiMaster.apiname == apiname).first()
            if api_key is None:
                return {'status':'error', 'message':'api key missing'}


            # 🔐 Gemini Setup
            client = genai.Client(api_key=api_key.apikey)
            model = "gemini-3-flash-preview"
            response = client.models.generate_content(
                model=model, # or "gemini-1.5-flash"
                contents=[prompt, img]
            )
            
            # In the new SDK, the text is accessed via .text
            xml_content = response.text.strip()

            return {"status": "success", "xml": xml_content}

        return {'status':'error', 'message':f'{apiname} is missing'}
    except Exception as e:
        return {"status": "error", "message": f"Gemini API Exception: {str(e)}"}
        




@router.post('/save-xml')
def save_xml(data: dict, request: Request, db: Session = Depends(get_db)):

    crop_id = data.get('crop_id')
    band = data.get('band')
    xml = data.get('xml')
    xml = xml.replace("```xml", "").replace("```", "").strip()

    xml_code = db.query(XmlCode).filter(XmlCode.crop_id == crop_id).first()

    if xml_code:
        xml_code.codes = xml
        db.commit()
        return {'status': 'success', 'message':'Xml Code Updated Successfully!'}

    else:
        new_code = XmlCode(crop_id = crop_id, bandname = band, codes = xml )
        db.add(new_code)
        db.commit()
        return {'status': 'success', 'message':'Xml Code Saved Successfully!'}

    return {'status': 'error', 'message':'Some Issue in Saving Xml Code!'}



@router.post('/query/{report_id}')
def generate_query(report_id: int, db: Session = Depends(get_db)):

    record = db.query(Uploadfile).filter(Uploadfile.id == report_id, Uploadfile.deleted_at == None).first()
    query = record.report_query
    # return {'query':query}
    
    api_key = db.query(ApiMaster).filter(ApiMaster.apiname == 'geminie').first()
    if not api_key:
        return {'status': 'error', 'message':'issue with api key'}

    try:
        client = genai.Client(api_key=api_key.apikey)
        model = "gemini-3-flash-preview"

        prompt = f"""
            You are a SQL parser.

            Extract ONLY column names from this SQL query.

            Rules:
            - Return ONLY a JSON array
            - No explanation
            - No extra text
            - No markdown
            - No code block
            - Only column names
            - Use alias if present (AS)
            - Remove table prefixes
            - Convert to UPPERCASE

            Example:
            Input: SELECT a.marks AS total, b.name FROM table
            Output: ["TOTAL", "NAME"]

            Query:
            {query}
        """

        response = client.models.generate_content(
            model=model,
            contents=prompt
        )

        raw_text = response.text.strip()

        # 🔥 Clean possible markdown
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()

        columns = json.loads(raw_text)


        code = build_fields_from_db(query,columns)


        if columns:
            record.queryString = code
            db.commit()
            # return columns
            return {'status':'success','message':'Query Read Successfully!'}

        
        return {'status':'error','message':'api unable to read the query'}
        
    except Exception as e:
        print("Gemini Error:", e)
        return {'status':'error', 'message': 'Gemini Error'}



def build_fields_from_db(query, columns):

    xml = "<queryString>\n"
    xml += f"\t<![CDATA[{query}]]>\n"
    xml += "</queryString>\n\n"

    for col in columns:
        xml += f'''<field name="{col}" class="java.lang.String">
    <property name="com.jaspersoft.studio.field.label" value="{col}"/>
</field>\n'''

    return xml