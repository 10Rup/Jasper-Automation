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




router = APIRouter(prefix='/report', tags=['Report'])
templates = Jinja2Templates("appv2/templates/report")


@router.get('/upload')
def upload(request: Request):

    return templates.TemplateResponse(
        request,
        'upload.html'
    )


@router.post('/upload')
async def upload(request: Request, reportname: str = Form(...), report_type: str = Form(...),  samplefile: UploadFile = File(...), pagesize: str = Form(...), orientation: str = Form(...), db: Session = Depends(conn)):

    filename = samplefile.filename
    name, ext = os.path.splitext(samplefile.filename)
    pdf_bytes = await samplefile.read()


    image_path = pdfToImg(ext, pdf_bytes, reportname, db)

    new_report = Upload(displayname=reportname, name=filename, type=report_type, size=pagesize, pagedimention=orientation, path=image_path, created_at=datetime.now(timezone.utc))
    db.add(new_report)
    db.commit()


    return {'msg':'report is uploaded]', 'path' : image_path}