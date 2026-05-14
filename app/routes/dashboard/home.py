from fastapi import APIRouter, Query, Request, Depends, Form, File, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from ...database import SessionLocal
from ...dashboard_models import DashboardWidget
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



@router.post('/save-layout')
async def save_layout(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    layouts = data.get('layout')

    for item in layouts:
        widget_id = item["id"]

        x = item["x"]
        y = item["y"]

        w = item["w"]
        h = item["h"]

        new_chart = DashboardWidget(config_json=item.get('content'), pos_x=x, pos_y=y,width=w, height=h)
        db.add(new_chart)

    db.commit()


    return  



@router.get('/view-dashboard')
def view_dashboard(request: Request,db: Session = Depends(get_db)):

    widgets = db.query(DashboardWidget).all()

    dashboard_data = []

    for widget in widgets:

        dashboard_data.append({

            "id": widget.id,

            "x": widget.pos_x,
            "y": widget.pos_y,

            "w": widget.width,
            "h": widget.height,

            "content": widget.config_json

        })

    # return dashboard_data
    return templates.TemplateResponse(
        request,
        "dashboard/view.html",

        {
            "widgets": dashboard_data
        }
    )