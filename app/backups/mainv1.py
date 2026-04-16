from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import FileResponse, HTMLResponse
from pdf2image import convert_from_bytes
import os
import uuid

app = FastAPI()

UPLOAD_DIR = "uploads"
IMAGE_DIR = "images"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

def get_canvas_script():
    return """
    <script>
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");

    let img = new Image();
    img.src = imageUrl;

    let rectangles = [];
    let startX, startY, isDrawing = false;

    img.onload = function () {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
    };

    canvas.addEventListener("mousedown", (e) => {
        startX = e.offsetX;
        startY = e.offsetY;
        isDrawing = true;
    });

    canvas.addEventListener("mouseup", (e) => {
        if (!isDrawing) return;

        let endX = e.offsetX;
        let endY = e.offsetY;

        let rect = {
            x: startX,
            y: startY,
            width: endX - startX,
            height: endY - startY,
            band: document.getElementById("band").value
        };

        rectangles.push(rect);
        draw();
        isDrawing = false;
    });

    function draw() {
        ctx.drawImage(img, 0, 0);

        ctx.strokeStyle = "red";
        ctx.lineWidth = 2;

        rectangles.forEach(r => {
            ctx.strokeRect(r.x, r.y, r.width, r.height);
        });
    }

    function saveRegions() {
        fetch("/save-regions", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(rectangles)
        })
        .then(res => res.json())
        .then(data => alert("Saved!"));
    }
    </script>
    """

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <body>
            <h2>Upload PDF</h2>
            <form action="/upload" method="post" enctype="multipart/form-data">
                <input type="file" name="file" accept="application/pdf"/>
                <button type="submit">Upload</button>
            </form>
        </body>
    </html>
    """


# @app.post("/upload", response_class=HTMLResponse)
# async def upload_pdf(file: UploadFile = File(...)):
#     file_id = str(uuid.uuid4())
#     pdf_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")

#     with open(pdf_path, "wb") as f:
#         f.write(await file.read())

#     images = convert_from_bytes(open(pdf_path, "rb").read())
#     image_path = os.path.join(IMAGE_DIR, f"{file_id}.png")
#     images[0].save(image_path, "PNG")

#     return f"""
#     <html>
#         <body>
#             <h2>Uploaded Image</h2>
#             <img src="/image/{file_id}" width="500"/>
#         </body>
#     </html>
#     """


@app.post("/upload", response_class=HTMLResponse)
async def upload_pdf(file: UploadFile = File(...)):
    import uuid, os
    from pdf2image import convert_from_bytes

    file_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")

    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    images = convert_from_bytes(open(pdf_path, "rb").read())
    image_path = os.path.join(IMAGE_DIR, f"{file_id}.png")
    images[0].save(image_path, "PNG")

    return f"""
    <html>
    <body>
        <h2>Draw Regions</h2>

        <label>Select Band:</label>
        <select id="band">
            <option value="title">Title</option>
            <option value="detail">Detail</option>
            <option value="pageHeader">Page Header</option>
            <option value="pageFooter">Page Footer</option>
        </select>

        <br><br>

        <canvas id="canvas"></canvas>

        <br><br>
        <button onclick="saveRegions()">Save Regions</button>

        <script>
            const imageUrl = "/image/{file_id}";
        </script>

        {get_canvas_script()}
    </body>
    </html>
    """

    
@app.post("/save-regions")
async def save_regions(request: Request):
    data = await request.json()

    print("Regions:", data)  # For now

    return {"status": "saved"}


@app.get("/image/{file_id}")
def get_image(file_id: str):
    image_path = os.path.join(IMAGE_DIR, f"{file_id}.png")
    return FileResponse(image_path)