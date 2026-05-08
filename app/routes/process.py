import os
import platform
import os
import json
from pdf2image import convert_from_bytes
from PIL import Image


from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import ApiMaster, Uploadfile, CropImages
from datetime import datetime, timezone


router = APIRouter(prefix='/process', tags=['Process'])
templates = Jinja2Templates("app/templates")
IMAGE_DIR = 'app/images'
CROP_IMAGE_DIR = 'app/cropped_images'


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get('/{report_id}')
def pdfreports(request: Request, report_id: int, db: Session = Depends(get_db)):

    report = db.query(Uploadfile).filter(Uploadfile.id==report_id, Uploadfile.deleted_at==None).first()

    # print(report.filepath)
    return templates.TemplateResponse(
        request,
        'process.html',
        {
            'report': report
        }
    )


@router.post('/save-region')
async def save_region(request: Request, db: Session = Depends(get_db)):
    data = await request.json()

    file_id = data['file_id']
    file_name = data['file_name']
    regions = data['regions']
    image_path = data['image_path']


    image_Url = os.path.join(IMAGE_DIR, f'{image_path}')

    folder = os.path.join(CROP_IMAGE_DIR, f'{file_name}')
    os.makedirs(folder, exist_ok=True)
    print(image_Url)
    img = Image.open(image_Url)
    results = []

    for i, r in enumerate(regions):
        x, y, w, h = int(r["x"]), int(r["y"]), int(r["width"]), int(r["height"])

        # Normalize coordinates (VERY IMPORTANT FIX)
        x1 = x if w >= 0 else x + w
        y1 = y if h >= 0 else y + h
        x2 = x + w if w >= 0 else x
        y2 = y + h if h >= 0 else y

        crop = img.crop((x1, y1, x2, y2))


        # Insert crop image record in DB
        new_crop_image = CropImages(uploadfile_id = file_id, bandname = r['band'])
        db.add(new_crop_image)
        db.commit()
        db.refresh(new_crop_image)
        path = os.path.join(folder, f'{new_crop_image.id}{new_crop_image.bandname}.png')
        crop.save(path)
        print(f"Saved cropped image: {path}")
        new_crop_image.filepath = f'{file_name}/{new_crop_image.id}{new_crop_image.bandname}.png'
        db.commit()

        
  
        # results.append({"band": r["band"], "file": filename})

    # with open(os.path.join(folder, "metadata.json"), "w") as f:
    #     json.dump(results, f)

    return {
        'status': 'success',
        'redirect': f'/process/{file_id}/cropped/'
    }

@router.get('/{report_id}/cropped')
def cropped(request: Request,report_id: int, db: Session = Depends(get_db)):
    crops = db.query(CropImages).filter(CropImages.uploadfile_id == report_id, CropImages.deleted_at==None).all()
    report = db.query(Uploadfile).filter(Uploadfile.id == report_id, Uploadfile.deleted_at==None).first()

    response = templates.TemplateResponse(
        request,
        'cropped.html',
        
        {
            'crops': crops,
            'report': report
        }
    )

    return response



@router.delete('/{report_id}/delete/{crop_id}')
def delete_crop_image(report_id: int, crop_id: int, db: Session = Depends(get_db)):

    record = db.query(CropImages).filter(CropImages.id == crop_id, CropImages.uploadfile_id == report_id, CropImages.deleted_at == None).first()
    
    record.deleted_at = datetime.now(timezone.utc)
    db.commit()

    return {'status':'success'}