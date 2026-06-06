import os
import platform
from pdf2image import convert_from_bytes
from datetime import datetime, timezone

from dotenv import load_dotenv



storage = os.getenv("UPLOAD_DIR")
appname = os.getenv("APP_NAME")

def pdfToImg(ext, report_bytes, reportname, db):

    osModel = platform.system()
    image_path = ""

    if ext==".pdf":
        if osModel != "Windows":
            images = convert_from_bytes(report_bytes, poppler_path="/usr/bin")

        else:
            images = convert_from_bytes(report_bytes)

        image_path = os.path.join(f"{reportname}.png")
        images[0].save(os.path.join(appname, storage, image_path), "PNG")
        

    # PNG / JPEG → save directly
    elif ext in [".png", ".jpg", ".jpeg"]:
        image_path = os.path.join(f"{reportname}{ext}")

        with open(os.path.join(appname, storage, image_path), "wb") as f:
            f.write(report_bytes)
    
    elif ext =='.jrxml':
        file_path = os.path.join(f"{reportname}{ext}")

        with open(os.path.join(appname, storage, file_path), "wb") as f:
            f.write(report_bytes)

    return image_path.replace("\\", "/")