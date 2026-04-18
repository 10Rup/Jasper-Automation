from fastapi import FastAPI, Request  # type: ignore
from .database import engine
from .models import Base
from .routes import home, api, upload, report
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="SUPER_SECRET_KEY")
app.mount("/images", StaticFiles(directory="app/images"), name="images")
app.mount("/cropped_images", StaticFiles(directory="app/cropped_images"), name="cropped_images")


Base.metadata.create_all(bind=engine)
templates = Jinja2Templates("app/templates")

app.include_router(home.router)
app.include_router(api.router)
app.include_router(upload.router)
app.include_router(report.router)