import os
import platform

from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pdf2image import convert_from_bytes
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import ApiMaster, Uploadfile, CropImages, CompileReport
from datetime import datetime, timezone


router = APIRouter(prefix='/reports', tags=['Report'])
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
    if report_type =='excel':
        files = db.query(Uploadfile).filter(Uploadfile.filetype=='xls', Uploadfile.deleted_at==None).all()

    elif report_type =='image':
        files = db.query(Uploadfile).filter(Uploadfile.filetype.in_(['png','jpeg']), Uploadfile.deleted_at==None).all()
    
    elif report_type == 'Combine':
        files = db.query(CompileReport).all()
        html_template = 'compile.html'
        return templates.TemplateResponse(
            request,
            html_template,
            {
                'files': files,
                'report_ext': report_type
            }
        )

    else:
        files = db.query(Uploadfile).filter(Uploadfile.filetype==report_type, Uploadfile.deleted_at==None).all()
    
    
    html_template = 'reportslist.html'
    return templates.TemplateResponse(
        request,
        html_template,
        {
            'files': files,
            'report_ext': report_type
        }
    )




@router.post('/save-query')
def save_query(data: dict, request: Request, db: Session =  Depends(get_db)):
    file_id = data.get('id')
    query = data.get('query')


    record = db.query(Uploadfile).filter(Uploadfile.id == file_id, Uploadfile.deleted_at == None).first()

    if not record:
        return {'status': 'error', 'message':'Issue in Saving Query!'}
    
    record.report_query = query
    db.commit()
    return {'status':'success', 'message':'Query saved successfully!'}

@router.delete('/delete/{report_id}')
def delete_report(request: Request, report_id: int, db: Session = Depends(get_db)):


    report = db.query(Uploadfile).filter(Uploadfile.id == report_id).first()
    if not report:
        return {'status':'error', 'message':'Report is not deleted'}
    
    report.deleted_at = True
    db.commit()
    return {'status':'success', 'message':'Report Deleted Successfullt.'}

        
# @router.post('/process-query/{report_id}')
# def process_query(request: Request, report_id: int, db: Session = Depends(get_db)):
    
#     query = db.query(Uploadfile).filter(Uploadfile.id == report_id, Uploadfile.deleted_at == None).first()

#     print(query.report_query)

#     return