import os
import platform
from pdf2image import convert_from_bytes
from datetime import datetime, timezone

from PIL import Image
from dotenv import load_dotenv


storage = os.getenv("UPLOAD_DIR")
appname = os.getenv("APP_NAME")
processed = os.getenv("PROCESS_DIR")


def saveRegion(id, name, path, regions):

    image_Url = os.path.join(appname,storage, f'{path}')

    folder = os.path.join(appname, processed)
    os.makedirs(folder, exist_ok=True)
    print(image_Url)
    img = Image.open(image_Url)
    results = []

    for i, r in enumerate(regions):
        x, y, w, h = int(r["x"]), int(r["y"]), int(r["width"]), int(r["height"])

        # Normalize coordinates (VERY IMPORTANT FIX)
        x1 = x if w >= 0 else x + w
        y1 = y if h >= 0 else y + h
        x2 = x + w if w >= 0 else x
        y2 = y + h if h >= 0 else y

        crop = img.crop((x1, y1, x2, y2))

        crop_name = f'{r["band"]}-{id}.png'
        crop_path = os.path.join(f'{name}', crop_name)
        image_path = os.path.join(folder, crop_path)
        crop.save(image_path)

        print(f"Image Saved: {crop_path}")
        results.append({"upload_id": id, "bandname": r["band"], "path": crop_path.replace("\\", "/")})

    # with open(os.path.join(folder, "metadata.json"), "w") as f:
    #     json.dump(results, f)

    # return {
    #     'status': 'success',
    #     'redirect': f'/process/{file_id}/cropped/'
    # }


    # result = f"Saving regions for file_id: {id}, file_name: {name}, image_path: {path}, regions: {regions}"

    return results