from fastapi import FastAPI, Request



from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles




from .databases.db import engine
from .models.model import Base


from .routes import home
from .routes.report import upload, view, process, correction, generate, report
from .routes.dbconn import dbconn, view as dbview
from .routes.query import build as querybuild
import os
from dotenv import load_dotenv


appname = os.getenv("APP_NAME")



app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="SUPER_SECRET_KEY")


Base.metadata.create_all(bind=engine)
# DashboardBase.metadata.create_all(bind=engine)
templates = Jinja2Templates(f"{appname}/report/templates")
 


# Mount static files
app.mount("/uploadimg", StaticFiles(directory=f"{appname}/uploads/reports"), name="uploadimg")
app.mount('/processed-img', StaticFiles(directory=f'{appname}/storages/upload/processed'), name='processed-img')


# app routes
app.include_router(home.router)

# database connection routes


# report routes
app.include_router(report.report_router)
# app.include_router(upload.router)
# app.include_router(view.router)
app.include_router(process.router)
app.include_router(correction.router)
# app.include_router(generate.router)

# dbconn routes
app.include_router(dbview.router)
app.include_router(dbconn.router)

# query routes
app.include_router(querybuild.router)