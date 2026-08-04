from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile, HTTPException, Body
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...databases.db import conn
from ...models.model import Upload

from datetime import datetime, timezone
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv

from ...services.report.upload import pdfToImg

appname = os.getenv("APP_NAME")

REFERENCE_UPLOAD_DIR = Path(os.getenv("REFERENCE_UPLOAD_DIR", "storage/reference_uploads"))
REFERENCE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Renamed from the generic `router` used in both source files, so importing this
# module alongside others in the same package can't collide on the name.
report_router = APIRouter(prefix='/report', tags=['Report'])
templates = Jinja2Templates(f"{appname}/templates/report")


# ================= PAGES =================

@report_router.get('/')
def home(request: Request):
    return templates.TemplateResponse(request, 'home.html')


@report_router.get('/upload')
def upload_page(request: Request):
    return templates.TemplateResponse(request, 'upload.html')


# ================= UPLOAD (report / sample) =================

@report_router.post('/upload')
async def upload_report(
    request: Request,
    correction: str = Form(...),
    reportname: str = Form(...),
    report_type: str = Form(...),
    samplefile: UploadFile = File(...),
    pagesize: str = Form(...),
    orientation: str = Form(...),
    db: Session = Depends(conn),
):
    filename = samplefile.filename
    ext = os.path.splitext(filename)[1]
    report_bytes = await samplefile.read()
    file_size = len(report_bytes)

    # TODO: confirm pdfToImg actually handles every extension this form accepts
    # (.csv, .json, .xlsx, .png, .jpeg, .jrxml) — not just .pdf, given its name.
    image_path = pdfToImg(ext, report_bytes, reportname, db)

    new_report = Upload(
        displayname=reportname,
        name=filename,
        type='report',
        format=report_type,
        size=str(file_size),
        pagedimention=f"{pagesize}-{orientation}",
        path=image_path,
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_report)
    db.commit()

    redirect_url = '/report/correction' if correction == 'yes' else '/report/view'
    return RedirectResponse(url=redirect_url, status_code=303)


# ================= UPLOAD (reference) =================

@report_router.post('/reference/upload')
async def upload_reference(
    request: Request,
    displayname: str = Form(...),
    notes: str = Form(''),
    file: UploadFile = File(...),
    db: Session = Depends(conn),
):
    filename = file.filename
    file_bytes = await file.read()
    file_size = len(file_bytes)

    safe_name = os.path.basename(filename or "reference")
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    stored_path = REFERENCE_UPLOAD_DIR / stored_name
    with open(stored_path, "wb") as f:
        f.write(file_bytes)

    # Upload has no dedicated "notes" column yet — accepted from the form but not stored.
    new_reference = Upload(
        displayname=displayname,
        name=filename,
        type='reference',
        format=os.path.splitext(filename)[1].lstrip('.'),
        size=str(file_size),
        path=str(stored_path),
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_reference)
    db.commit()

    return JSONResponse(status_code=201, content={
        "ok": True, "id": new_reference.id, "displayname": new_reference.displayname,
    })


# ================= LIST / FILE / DELETE =================
@report_router.get('/list')
def list_page(request: Request):
    return templates.TemplateResponse(request, 'list.html')

@report_router.get('/uploads')
def list_uploads(type: str = Query(...), db: Session = Depends(conn)):
    uploads = (
        db.query(Upload)
        .filter(Upload.type == type, Upload.deleted_at.is_(None))
        .order_by(Upload.id.desc())
        .all()
    )
    return [
        {
            "id": u.id,
            "displayname": u.displayname,
            "name": u.name,
            # "url": f"/report/uploads/file/{u.id}",
            'url': f"/uploadimg/{u.path}",
            "size": u.size,
            "status": u.status or 0,
            "query": u.query,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in uploads
    ]


@report_router.get('/uploads/file/{id}')
def get_upload_file(id: int, db: Session = Depends(conn)):
    upload = db.query(Upload).filter(Upload.id == id, Upload.deleted_at.is_(None)).first()
    if not upload:
        raise HTTPException(404, "upload not found")
    if not upload.path or not os.path.exists(upload.path):
        raise HTTPException(404, "file is missing on disk")
    return FileResponse(upload.path)


@report_router.delete('/uploads/{id}')
def delete_upload(id: int, db: Session = Depends(conn)):
    upload = db.query(Upload).filter(Upload.id == id, Upload.deleted_at.is_(None)).first()
    if not upload:
        raise HTTPException(404, "upload not found")
    upload.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


# ================= QUERY / PROCESS / GENERATE / DOWNLOAD =================
# These four were only ever documented as comments in report-list.html — none
# actually existed yet. Wiring them up here so the frontend's four action
# buttons per card (Process / Add Query / Generate / Download) have something
# real to call. The actual processing/generation logic is stubbed — see TODOs.

@report_router.put('/uploads/{id}/query')
def save_upload_query(id: int, payload: dict = Body(...), db: Session = Depends(conn)):
    upload = db.query(Upload).filter(Upload.id == id, Upload.deleted_at.is_(None)).first()
    if not upload:
        raise HTTPException(404, "upload not found")
    upload.query = payload.get("query", "")
    db.commit()
    return {"ok": True}


@report_router.post('/uploads/{id}/process')
def process_upload(id: int, db: Session = Depends(conn)):
    upload = db.query(Upload).filter(Upload.id == id, Upload.deleted_at.is_(None)).first()
    if not upload:
        raise HTTPException(404, "upload not found")

    # TODO: this is where whatever "process this upload" means actually happens —
    # e.g. running the image → JRXML band-extraction pipeline referenced elsewhere
    # in this codebase (services/report/geminie_generate.py's imgToCode, per earlier
    # conversation). Left unimplemented since that logic wasn't provided in this file.

    return {"ok": True, "message": "processing started"}


@report_router.post('/uploads/{id}/generate')
def generate_report(id: int, db: Session = Depends(conn)):
    upload = db.query(Upload).filter(Upload.id == id, Upload.deleted_at.is_(None)).first()
    if not upload:
        raise HTTPException(404, "upload not found")
    if not upload.query or not upload.query.strip():
        raise HTTPException(400, "attach a query to this upload before generating")

    # TODO: this is where the actual JasperReports generation call happens —
    # running upload.path (the JRXML/template) against upload.query's result set.
    # On success, persist the generated file path and flip status to 1 so the
    # frontend's Download button unlocks. Placeholder below just marks it ready
    # without producing a real file — replace once the generation pipeline exists.
    upload.status = 1
    db.commit()

    return {"ok": True, "message": "report generated"}


@report_router.get('/uploads/{id}/download')
def download_generated_report(id: int, db: Session = Depends(conn)):
    upload = db.query(Upload).filter(Upload.id == id, Upload.deleted_at.is_(None)).first()
    if not upload:
        raise HTTPException(404, "upload not found")
    if upload.status != 1:
        raise HTTPException(400, "this report hasn't been generated yet")
    if not upload.output_path or not os.path.exists(upload.output_path):
        raise HTTPException(404, "generated file is missing on disk")
    return FileResponse(upload.output_path, filename=os.path.basename(upload.output_path))