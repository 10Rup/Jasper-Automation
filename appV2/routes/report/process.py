from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...databases.db import conn
from ...models.model import Upload, Process

from datetime import datetime, timezone

from ...services.report.process import saveRegion, ai_detect_regions
import os
from dotenv import load_dotenv


appname = os.getenv("APP_NAME")


router = APIRouter(prefix='/report', tags=['Report'])
templates = Jinja2Templates(f"{appname}/templates/report")


@router.get('/process/{report_id}')
def process_report(request: Request, report_id: int, db: Session = Depends(conn)):
    report = db.query(Upload).filter(Upload.id == report_id, Upload.deleted_at.is_(None)).first()
    if not report:
        return JSONResponse(status_code=404, content={"status": "error", "message": "report not found"})

    existing = (
        db.query(Process)
        .filter(Process.upload_id == report_id, Process.deleted_at.is_(None))
        .all()
    )
    existing_regions = [
        {"band": p.bandname, "x": p.x or 0, "y": p.y or 0, "width": p.width or 0, "height": p.height or 0}
        for p in existing if p.x is not None
    ]

    return templates.TemplateResponse(
        request, 'process.html',
        {'report': report, 'existing_regions': existing_regions},
    )


@router.post("/process/save-region")
async def save_region(request: Request, db: Session = Depends(conn)):
    data = await request.json()
    file_id = data['file_id']
    file_name = data['file_name']
    regions = data['regions']
    image_path = data['image_path']

    result = saveRegion(file_id, file_name, image_path, regions)

    try:
        # re-saving replaces the previous mapping entirely, rather than appending to it —
        # soft-delete whatever was there before this upload's next save
        db.query(Process).filter(
            Process.upload_id == file_id, Process.deleted_at.is_(None)
        ).update({"deleted_at": datetime.now(timezone.utc)})

        for r in result:
            save_img = Process(
                upload_id=r.get('upload_id'), bandname=r.get('bandname'), path=r.get('path'),
                x=r.get('x'), y=r.get('y'), width=r.get('width'), height=r.get('height'),
            )
            db.add(save_img)
        db.commit()

        return {'status': 'success', 'message': "Report Successfully Processed", 'redirect': '/report/list'}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error Message - {str(e)}"}


@router.post('/add-query/{report_id}')
async def add_query(request: Request, report_id: int, db: Session = Depends(conn)):
    data = await request.json()
    query = data.get('query')

    report = db.query(Upload).filter(Upload.id == report_id, Upload.deleted_at.is_(None)).first()
    if not report:
        return JSONResponse(status_code=404, content={"status": "error", "message": "report not found"})

    report.query = query
    db.commit()

    return {'status': 'success', 'message': 'Query added successfully'}


@router.post('/process/{report_id}/ai-detect')
def ai_detect(report_id: int, db: Session = Depends(conn)):
    report = db.query(Upload).filter(Upload.id == report_id, Upload.deleted_at.is_(None)).first()
    if not report:
        return JSONResponse(status_code=404, content={"status": "error", "message": "report not found"})

    image_url = os.path.join(appname, os.getenv("UPLOAD_DIR"), report.path)
    try:
        regions = ai_detect_regions(image_url)
    except RuntimeError as e:
        return JSONResponse(status_code=502, content={"status": "error", "message": str(e)})

    return {"status": "success", "regions": regions}