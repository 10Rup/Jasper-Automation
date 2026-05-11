from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import ApiMaster, Uploadfile, CropImages, CompileReport
from datetime import datetime, timezone

import plotly.express as px
import pandas as pd

router = APIRouter(prefix='/dashboard', tags=['Dashboard'])
templates = Jinja2Templates("app/templates")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get('/')
def home(request: Request):
     # Dummy data
    data = {
        "Month": ["Jan", "Feb", "Mar", "Apr"],
        "Students": [100, 150, 170, 220]
    }

    df = pd.DataFrame(data)

    # Create chart
    fig = px.bar(
        df,
        x="Month",
        y="Students",
        title="Student Growth"
    )

    # Convert graph to HTML
    chart_html = fig.to_html(full_html=False)

    return templates.TemplateResponse(
        request,
        'dashboard/home.html',
        {
            'chart': chart_html
        }
    )



@router.get('/add')
def addGraph(request: Request):

    return templates.TemplateResponse(
        request,
        'dashboard/add_dashboard.html'
        
    )