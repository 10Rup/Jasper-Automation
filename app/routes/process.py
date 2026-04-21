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



# @router.get('/')
# def reports(request: Request):

#     return templates.TemplateResponse(
#         request,
#         'processdemo.html'
#     )



@router.get('/{report_id}')
def pdfreports(request: Request, report_id: int, db: Session = Depends(get_db)):

    report = db.query(Uploadfile).filter(Uploadfile.id==report_id).first()

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


    imageUrl = os.path.join(IMAGE_DIR, f'{file_name}.png')

    folder = os.path.join(CROP_IMAGE_DIR, f'{file_name}')
    os.makedirs(folder, exist_ok=True)

    img = Image.open(imageUrl)
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

    return {
        'status': 'success',
        'redirect': '/reports/'
    }

# @router.get('/{report_id}/cropped')
# def cropped(request: Request,report_id: int, db: Session = Depends(get_db)):

    
#     return templates.TemplateResponse(
#         request,
#         'home.html'
#     )