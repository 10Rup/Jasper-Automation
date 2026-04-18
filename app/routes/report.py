import os
import platform

from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pdf2image import convert_from_bytes
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import ApiMaster, Uploadfile, CropImages
from datetime import datetime, timezone


router = APIRouter(prefix='/reports', tags=['API'])
templates = Jinja2Templates("app/templates")
IMAGE_DIR = 'app/images'
CROP_IMAGE_DIR = 'app/cropped_images'


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



@router.get('/')
def reports(request: Request):

    return templates.TemplateResponse(
        request,
        'reports.html'
    )



@router.get('/{report_type}')
def pdfreports(request: Request, report_type: str, db: Session = Depends(get_db)):

    files = db.query(UploadFile).filter(Uploadfile.filetype == report_type).all()

    return templates.TemplateResponse(
        request,
        'reportlist.html',
        {
            'files': files
        }
    )




# @router.get('/')
# def get_images(request: Request, db: Session = Depends(get_db)):
#     # images = db.query(Uploadfile.filename, Uploadfile.filename, func.max(Uploadfile.created_at).label("created_at")).group_by(Uploadfile.filename).order_by(func.max(Uploadfile.created_at).desc()).all()
#     images = db.query(Uploadfile).order_by(Uploadfile.created_at.desc()).all()
#     return templates.TemplateResponse(
#         request,
#         'report_samples.html',
#         {
#             'images': images,
#         }
#     )


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
