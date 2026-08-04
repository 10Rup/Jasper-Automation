import os
import platform
from pdf2image import convert_from_bytes
from datetime import datetime, timezone

from PIL import Image
from dotenv import load_dotenv

import json
import base64
import anthropic


storage = os.getenv("UPLOAD_DIR")
appname = os.getenv("APP_NAME")
processed = os.getenv("PROCESS_DIR")


# def saveRegion(id, name, path, regions):

#     image_Url = os.path.join(appname,storage, f'{path}')

#     folder = os.path.join(appname, processed)
#     os.makedirs(folder, exist_ok=True)
#     print(image_Url)
#     img = Image.open(image_Url)
#     results = []

#     for i, r in enumerate(regions):
#         x, y, w, h = int(r["x"]), int(r["y"]), int(r["width"]), int(r["height"])

#         # Normalize coordinates (VERY IMPORTANT FIX)
#         x1 = x if w >= 0 else x + w
#         y1 = y if h >= 0 else y + h
#         x2 = x + w if w >= 0 else x
#         y2 = y + h if h >= 0 else y

#         crop = img.crop((x1, y1, x2, y2))

#         # crop_name = f'{r["band"]}-{id}.png'
#         # crop_path = os.path.join(f'{name}', crop_name)
#         # image_path = os.path.join(folder, crop_path)
#         # crop.save(image_path)

#         crop_name = f'{r["band"]}-{id}.png'
#         crop_path = os.path.join(
#             name,
#             crop_name
#         )
        
#         image_path = os.path.join(
#             appname,
#             processed,
#             name,
#             crop_name
#         )

#         os.makedirs(os.path.dirname(image_path), exist_ok=True)

#         crop.save(image_path)
#         print(f"Image Saved: {image_path}")
#         results.append({"upload_id": id, "bandname": r["band"], "path": crop_path.replace("\\", "/")})


#     return results


def saveRegion(id, name, path, regions):
    image_Url = os.path.join(appname, storage, f'{path}')
    folder = os.path.join(appname, processed)
    os.makedirs(folder, exist_ok=True)
    img = Image.open(image_Url)
    results = []

    for i, r in enumerate(regions):
        x, y, w, h = int(r["x"]), int(r["y"]), int(r["width"]), int(r["height"])

        x1 = x if w >= 0 else x + w
        y1 = y if h >= 0 else y + h
        x2 = x + w if w >= 0 else x
        y2 = y + h if h >= 0 else y

        crop = img.crop((x1, y1, x2, y2))

        crop_name = f'{r["band"]}-{id}.png'
        crop_path = os.path.join(name, crop_name)
        image_path = os.path.join(appname, processed, name, crop_name)

        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        crop.save(image_path)

        results.append({
            "upload_id": id,
            "bandname": r["band"],
            "path": crop_path.replace("\\", "/"),
            "x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1,  # persisted now, not discarded
        })

    return results





client = anthropic.Anthropic()  # picks up ANTHROPIC_API_KEY from env, same pattern as services/query/build.py

BAND_NAMES = ["title", "pageHeader", "columnHeader", "detail", "columnFooter", "pageFooter", "summary"]

AI_DETECT_SYSTEM_PROMPT = (
    "You are analyzing a screenshot of a printed/PDF report layout to identify its "
    "JasperReports band structure. The valid band types, top to bottom in a typical "
    "report, are: title, pageHeader, columnHeader, detail, columnFooter, pageFooter, summary.\n"
    "Rules:\n"
    "1. Only include a band if it is genuinely visually present and distinguishable in the image — "
    "do not invent a band that isn't there (e.g. many reports have no separate title band).\n"
    "2. detail is the repeating row/record region — usually the largest band, appearing once "
    "as a bounding region even though it represents many repeated rows.\n"
    "3. Bands must not overlap and must be ordered top-to-bottom by their y coordinate.\n"
    "4. Coordinates are pixel coordinates within an image that is exactly "
    "{width}x{height} pixels. x and y are the top-left corner of the band's bounding box.\n"
    "Output ONLY a JSON array, nothing else — no markdown fences, no prose. Example shape:\n"
    '[{{"band": "columnHeader", "x": 40, "y": 120, "width": 720, "height": 32}}, ...]'
)


def ai_detect_regions(image_path: str) -> list[dict]:
    """
    Sends the uploaded report image to Claude and asks it to draw one bounding box
    per JasperReports band it can identify. Returns the same {band, x, y, width, height}
    shape the frontend's `rectangles` array already uses, so results can be dropped
    straight into the canvas for the user to review and adjust.
    """
    with Image.open(image_path) as img:
        width, height = img.size

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    media_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            system=AI_DETECT_SYSTEM_PROMPT.format(width=width, height=height),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                                   "data": base64.b64encode(image_bytes).decode()}},
                    {"type": "text", "text": "Identify the report bands in this image."},
                ],
            }],
        )
    except anthropic.APIError as e:
        raise RuntimeError(f"AI detection failed: {e}")

    text = "".join(b.text for b in response.content if b.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        regions = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"AI returned unparseable output: {e}")

    # sanity-filter: only keep known band names, clamp to image bounds
    cleaned = []
    for r in regions:
        if r.get("band") not in BAND_NAMES:
            continue
        x = max(0, min(int(r.get("x", 0)), width))
        y = max(0, min(int(r.get("y", 0)), height))
        w = max(1, min(int(r.get("width", 0)), width - x))
        h = max(1, min(int(r.get("height", 0)), height - y))
        cleaned.append({"band": r["band"], "x": x, "y": y, "width": w, "height": h})

    return cleaned