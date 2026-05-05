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
    report_id = data['report_id']
    
    report = db.query(Uploadfile).filter(Uploadfile.id == report_id, Uploadfile.deleted_at == None).first()
    report_fields = report.fields

    image_path = os.path.join(CROP_IMAGE_DIR,reportpath)

    if not os.path.exists(image_path):
        return {'status':'error', 'message':'file is missing'}
    
    try:
        # Load the image
        img = Image.open(image_path)

        prompt = f"""
        You are a JasperReports expert.

        A. Use the following reference JRXML or xml code as a STYLE GUIDE only, Do NOT copy blindly. Adapt based on the image.
            Example Output:
                <{band}>
                    <band height="125" splitType="Stretch">
                        <textField isStretchWithOverflow="true" isBlankWhenNull="true">
                            <reportElement x="80" y="15" width="141" height="51" uuid="7c4acc13-1103-42c2-8a37-35c6f9d1314d"/>
                            <box>
                                <topPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                                <leftPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                                <bottomPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                                <rightPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                            </box>
                            <textElement textAlignment="Center" verticalAlignment="Middle"/>
                            <textFieldExpression><![CDATA["Text Field"]]></textFieldExpression>
                        </textField>
                    </band>
                </{band}>

        --------------------------------------------------
        B. AVAILABLE DATA FIELDS (VERY IMPORTANT):
            {report_fields}
            FIELD USAGE RULES:
            1. If any label in the image represents dynamic data (marks, totals, values, numbers), you MUST use <textField>
            2. Use this format strictly:
            <textField>
                <reportElement x="" y="" width="" height=""/>
                <box><pen lineWidth="1.0" lineColor="#000000"/></box>
                <textElement textAlignment="Center" verticalAlignment="Middle">
                    <font/>
                </textElement>
                <textFieldExpression><![CDATA[$F{{FIELD_NAME}}]]></textFieldExpression>
            </textField>

            3. Match labels with fields intelligently:
            - "TOTAL THEO MARKS" → TOTAL_THEO_MARKS
            - "TOTAL THEO OBTAINED" → TOTAL_THEO_OBT_MARKS

            4. If no matching field is found → use <staticText>
                
        --------------------------------------------------

        C. Now analyze the image and generate JRXML for <{band}>.

            Mandatory Rules:
            1. Use <staticText> for labels/headings
            2. Use <textField> for dynamic values (based on fields above)
            3. Proper (x, y, width, height)
            4. Use <box> only if required and use following format example:-
                <box>
                    <topPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                    <leftPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                    <bottomPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                    <rightPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                </box>

            5. STRICT font hierarchy:
                <textElement><font/></textElement>
            6. textAlignment="Center", verticalAlignment="Middle"
            7. Extract exact text
            8. NO UUID
            9. NO comments
            10. NO markdown
            11. CRITICAL STRUCTURE RULE:
                <{band}>
                    <band height="AUTO">
                        ...YOUR CONTENT...
                    </band>
                </{band}>

                - NEVER skip <band>
                - NEVER omit <band>
                - NEVER return only inner elements
                - Output is INVALID if <band> is missing
                - Always include height attribute in <band>
                - Use a reasonable height based on content (e.g., 50–200)
                - Use font size to 10 by default else increase or decrease according to requirement.

            12. Keep layout within A4 bounds (Strickly).

            13. DO NOT use:
                - <text value="text" />
                - textAdjust
                - forecolor inside <font/> tag
                - topIndent



            14. If Image or signature is present inside the report image use following format, 
            Example:-
                <image hAlign="Center" vAlign="Middle" onErrorType="Blank">
                    <reportElement x="390" y="10" width="140" height="30" uuid="7426c6e3-4bb6-416d-8e66-a9cd22df6de6"/>
                    <imageExpression><![CDATA["Image_path"]]></imageExpression>
                </image>

            15. If  "forecolor" is required then use following format as example :-
                <reportElement x="10" y="105" width="545" height="15" forecolor="#350EE6"/>
        --------------------------------------------------

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
    report_id = data.get('report_id')
    xml = data.get('xml')
    xml = xml.replace("```xml", "").replace("```", "").strip()

    report = db.query(Uploadfile).filter(Uploadfile.id == report_id, Uploadfile.deleted_at == None).first()

    if not report:
        return {'status': 'error', 'message':'Report file not Found!'}

    if band=="title":
        report.title = xml

    elif band=="pageHeader":
        report.pageHeader = xml

    elif band=="columnHeader":
        report.columnHeader = xml

    elif band=="detail":
        report.detail = xml

    elif band=="columnFooter":
        report.columnFooter = xml

    elif band=="pageFooter":
        report.pageFooter = xml

    elif band=="summary":
        report.summary = xml

    else:
        return {'status': 'error', 'message':f'Unknown Band Name - {band}!'}
    
    
    db.commit()
    return {'status': 'success', 'message':'Xml Code Updated Successfully!'}

    # xml_code = db.query(XmlCode).filter(XmlCode.crop_id == crop_id).first()

    # if xml_code:
    #     xml_code.codes = xml
    #     db.commit()
    #     return {'status': 'success', 'message':'Xml Code Updated Successfully!'}

    # else:
    #     new_code = XmlCode(crop_id = crop_id, bandname = band, codes = xml )
    #     db.add(new_code)
    #     db.commit()
    #     return {'status': 'success', 'message':'Xml Code Saved Successfully!'}

    # return {'status': 'error', 'message':'Some Issue in Saving Xml Code!'}



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
            - No duplicate value or fields
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
            record.fields = columns
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