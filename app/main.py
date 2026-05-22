from fastapi import FastAPI, Request

 # type: ignore
from .database import engine
from .models import Base
from .dashboard_models import Base as DashboardBase




from .routes import home, api, upload, report, process, prepare, jrxml, test

from app.routes.dashboard import home as homeDash
from app.routes.tables import tables 
from app.routes.tests import ai_test, correction_ai
from app.routes.generate import prepare_report



from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="SUPER_SECRET_KEY")
app.mount("/images", StaticFiles(directory="app/images"), name="images")
app.mount("/cropimages", StaticFiles(directory="app/cropped_images"), name="cropped_images")
app.mount('/statics', StaticFiles(directory='app/assets/static'), name='statics')

Base.metadata.create_all(bind=engine)
DashboardBase.metadata.create_all(bind=engine)
templates = Jinja2Templates("app/templates")

app.include_router(home.router)
app.include_router(api.router)
app.include_router(upload.router)
app.include_router(report.router)
app.include_router(process.router)
app.include_router(prepare.router)
app.include_router(jrxml.router)
app.include_router(test.router)




# Table
app.include_router(tables.router)



app.include_router(ai_test.router)
app.include_router(correction_ai.router)
app.include_router(prepare_report.router)



# Dashborad View/Routes
app.include_router(homeDash.router)