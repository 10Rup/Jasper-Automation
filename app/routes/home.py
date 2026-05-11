from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import ApiMaster, Uploadfile, CropImages, CompileReport
from datetime import datetime, timezone


router = APIRouter()
templates = Jinja2Templates("app/templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get('/')
def home(request: Request, db: Session = Depends(get_db)):

    automantion = db.query(func.count(CompileReport.id).label('total')).filter(CompileReport.deleted_at==None, CompileReport.is_compiled==True).first()

    apis = db.query(func.count(ApiMaster.id).label('total')).first()
    # print(automantion.total)
    return templates.TemplateResponse(
        request,
        'home.html',
        {
            'automated': automantion.total,
            'api_count': apis.total
        }
    )


