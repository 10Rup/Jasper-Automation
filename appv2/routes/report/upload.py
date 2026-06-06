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


@router.get('/upload')
def upload(request: Request):

    return templates.TemplateResponse(
        request,
        'upload.html'
    )


@router.post('/upload')
async def upload(request: Request, correction: str =  Form(...), reportname: str = Form(...), report_type: str = Form(...),  samplefile: UploadFile = File(...), pagesize: str = Form(...), orientation: str = Form(...), db: Session = Depends(conn)):

    filename = samplefile.filename
    name, ext = os.path.splitext(samplefile.filename)
    report_bytes = await samplefile.read()

    # if correction == 'yes':
        
    #     return RedirectResponse(
    #         url='/report/correction',
    #         status_code=303
    #     )
        
    image_path = pdfToImg(ext, report_bytes, reportname, db)

    new_report = Upload(displayname=reportname, name=filename, type=report_type, size=pagesize, pagedimention=orientation, path=image_path, created_at=datetime.now(timezone.utc))
    db.add(new_report)
    db.commit()

    

    return RedirectResponse(
        url='/report/view',
        status_code=303
    )