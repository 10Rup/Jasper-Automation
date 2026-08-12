from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile, HTTPException, Body
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...databases.db import conn
from ...models.model import Upload, Process

from datetime import datetime, timezone
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
from sql_metadata import Parser

from ...services.report.upload import pdfToImg
from ...services.report.geminie_generate import imgToCode
from ...services.report.cleanXml import clean_sql

appname = os.getenv("APP_NAME")
processed = os.getenv("PROCESS_DIR")
apikeygeminie = os.getenv("API_KEY_GEMINIE")
output = os.getenv("OUTPUT_DIR")
reference = os.getenv("REFERENCE_DIR")

REFERENCE_UPLOAD_DIR = Path(os.getenv("REFERENCE_UPLOAD_DIR", "storage/reference_uploads"))
REFERENCE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

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

    redirect_url = '/report/correction' if correction == 'yes' else '/report/list'
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
            "url": f"/uploadimg/{u.path}",
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

@report_router.put('/uploads/{id}/query')
def save_upload_query(id: int, payload: dict = Body(...), db: Session = Depends(conn)):
    upload = db.query(Upload).filter(Upload.id == id, Upload.deleted_at.is_(None)).first()
    if not upload:
        raise HTTPException(404, "upload not found")
    upload.query = payload.get("query", "")
    upload.saved_query_id = payload.get("saved_query_id")  # None if hand-typed/edited
    db.commit()
    return {"ok": True}

@report_router.post('/uploads/{id}/process')
def process_upload(id: int, db: Session = Depends(conn)):
    upload = db.query(Upload).filter(Upload.id == id, Upload.deleted_at.is_(None)).first()
    if not upload:
        raise HTTPException(404, "upload not found")

    # NOTE: still a stub — report-list.html's Process button doesn't actually call this
    # anymore, it navigates to /report/process/{id} (the draw-regions page) instead.
    # Left here in case something else still calls it directly.
    return {"ok": True, "message": "processing started"}


@report_router.post('/uploads/{id}/generate')
def generate_report(id: int, db: Session = Depends(conn)):
    """
    Real implementation, merged in from generate.py's generate-geminie logic —
    matches what report-list.html's Generate button actually calls
    (POST /report/uploads/{id}/generate). Only marks the report ready (status = 1)
    once a real .jrxml has been written to disk.
    """
    file = db.query(Upload).filter(Upload.id == id, Upload.deleted_at.is_(None)).first()
    if not file:
        raise HTTPException(404, "report not found")
    if not file.query or not file.query.strip():
        raise HTTPException(400, "attach a query to this report before generating")

    query = clean_sql(file.query)
    parser = Parser(query)
    columns = [col.split('.')[-1] for col in parser.columns]
    fields = {col: "string" for col in columns}  # defaulting all fields to string for now
    config = {"pagesize": file.size}

    jrxml_bands = {
        'title': "", 'pageHeader': "", 'columnHeader': "", 'detail': "",
        'columnFooter': "", 'pageFooter': "", 'summary': "",
    }

    band_images = {}

    for band in jrxml_bands.keys():
        band_report = db.query(Process).filter(
            Process.upload_id == id,
            Process.bandname == band,
            Process.deleted_at.is_(None),
        ).first()
        if not band_report:
            continue

        band_images[band] = os.path.join(appname, processed, band_report.path)

        if band_report.code:
            continue  # already generated for this band — don't re-call the model

        result = imgToCode(band_report.bandname, fields, config, band_images[band], apikeygeminie)
        band_report.code = result
        db.commit()

    if not band_images:
        raise HTTPException(400, "no processed bands found — draw/save regions for this report first")

    # 1. base jrxml template
    base_code_path = os.path.join(appname, reference, "baseA4Report.jrxml")  # only A4 supported for now
    with open(base_code_path, "r", encoding="utf-8") as f:
        final_xml = f.read()

    # 2. query + fields
    query_string = f'''<queryString>
\t\t<![CDATA[{query}]]>
\t</queryString>'''
    for field_name in fields:
        query_string += f'''\n<field name="{field_name}" class="java.lang.String">
\t\t<property name="com.jaspersoft.studio.field.label" value="{field_name}"/>
\t</field>'''
    final_xml += f'\n{query_string}'

    # 3. band code
    for band in band_images:
        band_report = db.query(Process).filter(
            Process.upload_id == id,
            Process.bandname == band,
            Process.deleted_at.is_(None),
        ).first()
        final_xml += f'\n{band_report.code}'

    if not final_xml.strip().endswith("</jasperReport>"):
        final_xml += "\n</jasperReport>"

    # 4. save to disk
    download_filename = f"report_{id}.jrxml"
    file_path = os.path.join(appname, output, download_filename)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_xml)

    # 5. mark ready — only after a real file exists on disk
    file.output_path = file_path
    file.status = 1
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
    return FileResponse(
        upload.output_path,
        filename=os.path.basename(upload.output_path),
        media_type="application/xml",  # JRXML is XML, not the PDF the old generate.py version claimed
    )