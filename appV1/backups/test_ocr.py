import pytesseract
from PIL import Image

# Optional (only if PATH issue)
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# image_path = "images/97a95882-3a9a-47bc-9e78-03863feb9ca7/detail_1.png"  # change this

# img = Image.open(image_path)

# text = pytesseract.image_to_string(img)

# print("----- OCR OUTPUT -----")
# print(text)


def extract_text_from_image(image_path):
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)

        # Clean text (important)
        text = " ".join(text.split())

        return text

    except Exception as e:
        print(f"OCR Error for {image_path}:", e)
        return ""