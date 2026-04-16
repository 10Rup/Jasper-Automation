from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import ApiMaster, Uploadfile, CropImages
from datetime import datetime, timezone




import platform
import os
import json
from pdf2image import convert_from_bytes
from PIL import Image
import openai  # Add this
from openai import OpenAI
import base64  # Ensure this is imported
from google import genai





router = APIRouter(prefix='/jasper', tags=['Jaspers'])
# router = APIRouter()
templates = Jinja2Templates("app/templates")
IMAGE_DIR = 'app/images'
CROP_IMAGE_DIR = 'app/cropped_images'

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get('/set-api')
def set_api(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, 
        "manage_api.html"
    )

@router.post('/add-api-key')
def add_api(request: Request, username: str = Form(...), apiname: str = Form(...), apikey: str = Form(...), db: Session =  Depends(get_db)):

    new_api = ApiMaster(username=username, apiname=apiname, apikey=apikey, created_at=datetime.now(timezone.utc))
    db.add(new_api)
    db.commit()

    return RedirectResponse(
        url='/jasper/report-sample',
        status_code=303
    )


@router.get("/upload-sample")
def report_sample_upload(request: Request):

    return templates.TemplateResponse(
        request,
        'upload.html'
    ) 


@router.post('/upload-sample')
async def report_sample_upload(request: Request, reportname: str = Form(...), samplefile: UploadFile = File(...), db: Session = Depends(get_db)):
    
    pdf_bytes = await samplefile.read()
    osModel = platform.system()

    if osModel != "Windows":
        images = convert_from_bytes(pdf_bytes, poppler_path="/usr/bin")
    else:
        images = convert_from_bytes(pdf_bytes)
    image_path = os.path.join(IMAGE_DIR, f"{reportname}.png")
    images[0].save(image_path, "PNG")

    new_image = Uploadfile(filename=reportname, filepath=f"{reportname}.png", created_at=datetime.now(timezone.utc))
    db.add(new_image)
    db.commit()

    
    return RedirectResponse(
        url='/jasper/report-samples',
        status_code=303
    )


@router.get('/report-samples')
def get_images(request: Request, db: Session = Depends(get_db)):
    image_dir = 'images'
    # images = db.query(Uploadfile.filename, Uploadfile.filename, func.max(Uploadfile.created_at).label("created_at")).group_by(Uploadfile.filename).order_by(func.max(Uploadfile.created_at).desc()).all()

    images = db.query(Uploadfile).order_by(Uploadfile.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        'report_samples.html',
        {
            'images': images,
            'image_dir': image_dir
        }
    )





@router.get('/report-sample-image/{image_id}')
def get_images(request: Request, image_id: int, db: Session = Depends(get_db)):
    image_dir = 'images'
    image = db.query(Uploadfile).filter(Uploadfile.id == image_id).first()

    # return {'message': f"Image path: {image.filepath}"}
    return templates.TemplateResponse(
        request,
        'crop_image.html',
        {
            'image': image,
            'image_dir': image_dir
        }
    )

@router.post("/report-sample-image/save-regions")
async def save_regions(request: Request, db: Session = Depends(get_db)):
    data = await request.json()

    file_id = data["file_id"]
    regions = data["regions"]
    file_name = data["file_name"]

    image_path = os.path.join(IMAGE_DIR, f"{file_name}.png")
    folder = os.path.join(CROP_IMAGE_DIR, f'{file_id}-{file_name}')
    os.makedirs(folder, exist_ok=True)

    img = Image.open(image_path)
    ##### img = img.resize((800, 800))

    results = []

    for i, r in enumerate(regions):
        x, y, w, h = int(r["x"]), int(r["y"]), int(r["width"]), int(r["height"])

        # Normalize coordinates (VERY IMPORTANT FIX)
        x1 = x if w >= 0 else x + w
        y1 = y if h >= 0 else y + h
        x2 = x + w if w >= 0 else x
        y2 = y + h if h >= 0 else y

        crop = img.crop((x1, y1, x2, y2))

        ###### filename = f'{r["band"]}{i}.png'

        # Insert crop image record in DB
        new_crop_image = CropImages(uploadfile_id = file_id, bandname = r['band'])
        db.add(new_crop_image)
        db.commit()
        db.refresh(new_crop_image)
        new_crop_image.filepath = f'{new_crop_image.id}{new_crop_image.bandname}.png'
        db.commit()

        path = os.path.join(folder, new_crop_image.filepath)
        crop.save(path)
        print(f"Saved cropped image: {path}")
  
        # results.append({"band": r["band"], "file": filename})

    # with open(os.path.join(folder, "metadata.json"), "w") as f:
    #     json.dump(results, f)

    return {"status": "saved"}

@router.get('/report-files/{file_id}')
def report_files(request: Request, file_id: int, db: Session = Depends(get_db)):
    file_dir = 'cropped_images'
    
    files = db.query(CropImages).filter(CropImages.uploadfile_id == file_id).order_by(CropImages.created_at.desc()).all()

    image = db.query(Uploadfile).filter(Uploadfile.id == file_id).first()

    return templates.TemplateResponse(
        request,
        'report_files.html',
        {
            'files': files,
            # 'filename': (image.filename).upper(),
            'filename': (image.filename),
            'imagepath': f'{image.id}-{image.filename}',
            'file_dir': file_dir
        }
    )

# ================= LOAD REFERENCE =================
def load_reference_by_band(band):
    reference_folder='app/reference'
    mapping = {
        "detail": "reference/detail.xml",
        "title": "reference/title.xml",
        "pageHeader": "reference/pageHeader.xml",
        "pageFooter": "reference/pageFooter.xml",
        "columnHeader": "reference/columnHeader.xml"
    }

    path = mapping.get(band)
    os.makedirs(reference_folder, exist_ok=True)

    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    return ""


@router.get("/process-crop/{file_id}/{filename}/{band}/{file_path}/{model}")
async def process_crop(file_id: str, filename: str, band: str, file_path: str, model: str, extra: str = Query(""), db: Session = Depends(get_db)):
    # Ensure this matches your global directory variable
    image_path = os.path.join(CROP_IMAGE_DIR, filename,file_path)


    if not os.path.exists(image_path):
        return JSONResponse({"status": "error", "message": f"File {filename} not found."})

    # print(image_path)
    # print(f"Processing crop: {filename} for band: {band}  for file: {file_path} with extra instructions: {extra}")
    
    try:
        # Load the image
        img = Image.open(image_path)
        
        # Base Prompt Construction
        # reference_xml = load_reference_by_band(band)
        # REFERENCE:
        # {reference_xml}

        prompt = f"""
        You are a JasperReports expert.

        Use the following reference JRXML as a STYLE GUIDE only.
        Do NOT copy blindly. Adapt based on the image.


        


        Now analyze the image and generate JRXML for <{band}>.

        Mandatory Rules:
        1. Use <staticText> for all elements
        2. Proper (x, y, width, height)
        3. Use <box><pen lineWidth="1.0" lineColor="#000000"/></box>
        4. STRICT font hierarchy:
        <textElement><font/></textElement>
        5. textAlignment="Center", verticalAlignment="Middle"
        6. Extract exact text
        7. NO UUID
        8. NO comments
        9. NO markdown
        10. Output ONLY valid XML inside <{band}>...</{band}>

        {f"Additional instructions: {extra}" if extra else ""}
        """

        if model == 'gemini':
            api_key = db.query(ApiMaster).filter(ApiMaster.apiname == 'gemini').first()

            # Use the client to generate content
            # 🔐 Gemini Setup
            # genai.configure(api_key="AIzaSyAcWnzx6Ny9SQVE_hcEtAG2qxB-S-0wB2k")
            client = genai.Client(api_key="AQ.Ab8RN6LObNr3cvP_ioDIyI9saWg0yJJ3Sf0Fi23HxT-p8qacgw")
            # model = genai.GenerativeModel("gemini-3-flash-preview")
            model = "gemini-3-flash-preview"
            response = client.models.generate_content(
                model=model, # or "gemini-1.5-flash"
                contents=[prompt, img]
            )
            
            # In the new SDK, the text is accessed via .text
            xml_content = response.text.strip()

            return JSONResponse({"status": "success", "xml": xml_content})

    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Gemini API Exception: {str(e)}"})

    
    return {'xml': ''}