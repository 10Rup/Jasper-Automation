from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import ApiMaster, Uploadfile, CropImages
from datetime import datetime, timezone


router = APIRouter(prefix='/api', tags=['API'])
templates = Jinja2Templates("app/templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get('/settings')
def api_settings(request: Request, db: Session = Depends(get_db)):

    return templates.TemplateResponse(
        request,
        'manageapi.html'
    )


@router.post('/add-key')
def add_api_key(request: Request, username: str = Form(...), apiname: str = Form(...), apikey: str = Form(...), db: Session = Depends(get_db)):

    api_key = db.query(ApiMaster).filter(ApiMaster.apiname == apiname).first()

    if api_key:
        api_key.username = username
        api_key.apikey = apikey
        api_key.created_at = datetime.now(timezone.utc)
        db.commit()
    
    else:
        new_api_key = ApiMaster(username=username, apiname=apiname, apikey=apikey, created_at=datetime.now(timezone.utc))
        db.add(new_api_key)
        db.commit()


    return RedirectResponse(
        url='/api/api-keys',
        status_code=303
    )


@router.get('/api-keys')
def api_keys(request: Request, db: Session = Depends(get_db)):

    api_keys = db.query(ApiMaster).all()

    return templates.TemplateResponse(
        request,
        'apikeys.html',
        {
            'apikeys': api_keys
        }
    )