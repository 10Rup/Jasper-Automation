from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session




from ...databases.db import conn
from ...models.model import Upload, Process

from datetime import datetime, timezone

#from ...services.report.generate import generateReport 
#from ...services.report.ocr_generate import imgToOcr, buildJson
from ...services.report.geminie_generate import imgToCode
from ...services.report.cleanXml import clean_sql
import os
import json
from dotenv import load_dotenv
from sql_metadata import Parser

processed = os.getenv("PROCESS_DIR")
appname = os.getenv("APP_NAME")
apikey = os.getenv("API_KEY")
apikeygeminie = os.getenv("API_KEY_GEMINIE")
output = os.getenv("OUTPUT_DIR")
reference = os.getenv("REFERENCE_DIR")

router = APIRouter(prefix='/query', tags=['Query'])
templates = Jinja2Templates(f"{appname}/templates/query")



@router.get('/')
def create_query(request: Request, db: Session = Depends(conn)):

    
    return templates.TemplateResponse(
        request, 
        'build.html'
    ) 

