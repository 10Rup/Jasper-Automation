# import cv2

# img = cv2.imread("detail-9.png")
# gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# thresh = cv2.threshold(
#     gray,
#     200,
#     255,
#     cv2.THRESH_BINARY_INV
# )[1]

# contours, _ = cv2.findContours(
#     thresh,
#     cv2.RETR_EXTERNAL,
#     cv2.CHAIN_APPROX_SIMPLE
# )

# html = [
#     "<html>",
#     "<body style='position:relative;'>"
# ]

# for cnt in contours:
#     x, y, w, h = cv2.boundingRect(cnt)

#     if w < 30 or h < 10:
#         continue

#     html.append(
#         f"""
#         <div style="
#             position:absolute;
#             left:{x}px;
#             top:{y}px;
#             width:{w}px;
#             height:{h}px;
#             border:1px solid red;
#         ">
#         </div>
#         """
#     )

# html.append("</body></html>")

# with open("layout.html", "w") as f:
#     f.write("\n".join(html))




from PIL import Image
import pytesseract

img = Image.open("detail-9.png")

hocr = pytesseract.image_to_pdf_or_hocr(
    img,
    extension='hocr'
)

with open("output.html", "wb") as f:
    f.write(hocr)

print("HTML saved")