from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CropImages



from ...databases.db import conn
from ...models.model import Upload, Process

from datetime import datetime, timezone

from ...services.report.upload import pdfToImg 
from ...services.report.process import saveRegion
import os
from dotenv import load_dotenv


appname = os.getenv("APP_NAME")


router = APIRouter(prefix='/report', tags=['Report'])
templates = Jinja2Templates(f"{appname}/templates/report")



@router.get('/process/{report_id}')
def process_report(request: Request, report_id: int, db: Session = Depends(conn)):

    report = db.query(Upload).filter(Upload.id == report_id).first()

    return templates.TemplateResponse(
        request,
        'process.html',
        {
            'report': report,
        }
    )


@router.post("/process/save-region")
async def save_region(request: Request, db: Session = Depends(conn)):
    
    data = await request.json()



    file_id = data['file_id']
    file_name = data['file_name']
    regions = data['regions']
    image_path = data['image_path']

    result  = saveRegion(file_id, file_name, image_path, regions)

    
    # Insert crop image record in DB
    for r in result:
        print(r)
        save_img = Process(upload_id = r.get('upload_id'), bandname = r.get('bandname'), path = r.get('path'))
        db.add(save_img)
        db.commit()

