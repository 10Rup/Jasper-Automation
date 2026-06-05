from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session



from ...databases.db import conn
from ...models.model import Upload

from datetime import datetime, timezone

from ...services.report.upload import pdfToImg
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
async def save_region(request: Request):
    
    data = await request.json()


    print(data)
    return {'msg': data}