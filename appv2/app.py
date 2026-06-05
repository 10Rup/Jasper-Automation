from fastapi import FastAPI, Request



from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles




from .databases.db import engine
from .models.model import Base


from .routes import home
from .routes.report import upload, view, process
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


# app routes
app.include_router(home.router)


# report routes
app.include_router(upload.router)
app.include_router(view.router)
app.include_router(process.router)