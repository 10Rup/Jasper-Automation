import cv2
import pytesseract
import json
from pathlib import Path

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

IMAGE_PATH = "detail-9.png"

# Windows Tesseract Path
pytesseract.pytesseract.tesseract_cmd = (
    # r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    r"C:\Users\lspl\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
)

# --------------------------------------------------
# LOAD IMAGE
# --------------------------------------------------


def imgToOcr(img_path):
    img = cv2.imread(img_path)

    if img is None:
        raise FileNotFoundError(f"Image not found: {img_path}")

    height, width = img.shape[:2]

    # --------------------------------------------------
    # PREPROCESS IMAGE
    # --------------------------------------------------

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Optional threshold for cleaner OCR
    ret, thresh = cv2.threshold(
        gray,
        150,
        255,
        cv2.THRESH_BINARY
    )

    # --------------------------------------------------
    # OCR
    # --------------------------------------------------

    ocr_data = pytesseract.image_to_data(
        thresh,
        output_type=pytesseract.Output.DICT
    )

    # --------------------------------------------------
    # GROUP WORDS INTO LINES
    # --------------------------------------------------

    lines = {}

    for i in range(len(ocr_data["text"])):

        text = ocr_data["text"][i].strip()

        if not text:
            continue

        key = (
            ocr_data["block_num"][i],
            ocr_data["par_num"][i],
            ocr_data["line_num"][i]
        )

        if key not in lines:
            lines[key] = {
                "words": [],
                "x": ocr_data["left"][i],
                "y": ocr_data["top"][i],
                "width": 0,
                "height": 0
            }

        lines[key]["words"].append(text)

        current_x = ocr_data["left"][i]
        current_width = ocr_data["width"][i]

        line_right = current_x + current_width

        lines[key]["width"] = max(
            lines[key]["width"],
            line_right - lines[key]["x"]
        )

        lines[key]["height"] = max(
            lines[key]["height"],
            ocr_data["height"][i]
        )

    return  lines, width, height
# print(imgToOcr(IMAGE_PATH))
# --------------------------------------------------
# BUILD JSON
# --------------------------------------------------
def buildJson(img_path,lines, width, height):
    elements = []

    for line in lines.values():

        elements.append({
            "type": "text",
            "text": " ".join(line["words"]),
            "x": int(line["x"]),
            "y": int(line["y"]),
            "width": int(line["width"]),
            "height": int(line["height"])
        })

    elements.sort(key=lambda x: (x["y"], x["x"]))

    result = {
        "image_width": width,
        "image_height": height,
        "elements": elements
    }

    # --------------------------------------------------
    # SAVE JSON
    # --------------------------------------------------

    output_file = Path(img_path).stem + ".json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    print("=" * 50)
    print(f"JSON saved to: {output_file}")
    print("=" * 50)

    # print(json.dumps(result, indent=4, ensure_ascii=False))
    return result


# buildJson(*imgToOcr(IMAGE_PATH))