from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pdf2image import convert_from_bytes
from PIL import Image
import google.generativeai as genai
import os
import uuid
import json
import base64

app = FastAPI()

UPLOAD_DIR = "uploads"
IMAGE_DIR = "images"
CROP_IMAGE_DIR = "crop_images"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)





@app.get("/projects", response_class=HTMLResponse)
def list_projects():
    folders = os.listdir(CROP_IMAGE_DIR)

    html = "<h2>Projects</h2><ul>"

    for f in folders:
        path = os.path.join(CROP_IMAGE_DIR, f)
        if os.path.isdir(path):
            html += f'<li><a href="/project/{f}">{f}</a></li>'

    html += "</ul>"
    return html


# @app.get("/project/{file_id}", response_class=HTMLResponse)
# def view_project(file_id: str):
#     folder = os.path.join(IMAGE_DIR, file_id)

#     files = os.listdir(folder)

#     html = f"<h2>Project: {file_id}</h2>"

#     for f in files:
#         if f.endswith(".png"):
#             html += f"""
#             <div style="margin-bottom:20px;">
#                 <b>{f}</b><br>
#                 <img src="/project-image/{file_id}/{f}" width="200"><br>
#                 <button onclick="deleteImage('{f}')">Delete</button>
#             </div>
#             """

#     html += f'<br><a href="/edit/{file_id}">Edit Regions</a>'

#     html += f"""
#     <script>
#     const fileId = "{file_id}";

#     function deleteImage(filename) {{
#         if (!confirm("Are you sure?")) return;

#         fetch(`/delete-region/${{fileId}}/${{filename}}`, {{
#             method: "DELETE"
#         }})
#         .then(res => res.json())
#         .then(() => {{
#             alert("Deleted!");
#             location.reload();
#         }});
#     }}
#     </script>
#     """
#     return html


@app.get("/project/{file_id}", response_class=HTMLResponse)
def view_project(file_id: str):
    folder = os.path.join(CROP_IMAGE_DIR, file_id)
    metadata_path = os.path.join(folder, "metadata.json")

    html = f"""
    <style>
        .crop-container {{ margin-bottom: 30px; border-bottom: 2px solid #eee; padding-bottom: 15px; }}
        .controls {{ margin: 10px 0; }}
        .btn {{ padding: 5px 10px; cursor: pointer; border: 1px solid #ccc; border-radius: 3px; background-color: #f0f0f0; }}
        .btn-delete {{ background-color: #ffcccc; color: #a00; border-color: #faa; }}
        .btn-process {{ background-color: #ccffcc; color: #00a; border-color: #afa; }}
        .result-box {{ width: 100%; height: 200px; font-family:monospace; margin-top: 10px; display: none; background: #2d2d2d; color: #f8f8f2; padding: 10px; border-radius: 4px;}}
    </style>
    <h2>Project: {file_id}</h2>
    """

    if not os.path.exists(metadata_path):
        html += "<p>No regions defined. <a href='/'>Start Over</a></p>"
        return html

    with open(metadata_path, "r") as f:
        regions = json.load(f)

    for item in regions:
        f = item["file"]
        band = item["band"]
        # Creating unique IDs for each crop's output and button
        safe_f_id = f.replace(".", "_") # sanitize for HTML id

        html += f"""
        <div class="crop-container" id="container_{safe_f_id}">
            <b>{f} (Band: {band})</b><br>
            <img src="/project-image/{file_id}/{f}" width="200" style="border: 1px solid #999;"><br>
            <div class="controls">
                <button class="btn btn-delete" onclick="deleteImage('{f}')">Delete</button>
                <button class="btn btn-process" id="process_{safe_f_id}" onclick="processImage('{file_id}', '{f}', '{band}')">Process to XML</button>
            </div>
            <textarea class="result-box" id="result_{safe_f_id}"></textarea>
        </div>
        """

    html += f'<br><a href="/edit/{file_id}">Edit Regions</a>'

    # Updated Javascript to handle both delete and process actions
    html += f"""
    <script>
    const fileId = "{file_id}";

    // Handle Image Deletion
    function deleteImage(filename) {{
        if (!confirm("Are you sure?")) return;

        fetch(`/delete-region/${{fileId}}/${{filename}}`, {{
            method: "DELETE"
        }})
        .then(res => res.json())
        .then(() => {{
            alert("Deleted!");
            location.reload();
        }});
    }}

    // Handle AI Processing via AJAX
    function processImage(fileId, filename, band) {{
        const safe_f_id = filename.replace(".", "_");
        const resultBox = document.getElementById("result_" + safe_f_id);
        const processBtn = document.getElementById("process_" + safe_f_id);

        // Show loading state
        resultBox.style.display = "block";
        resultBox.value = "Processing image with Gemini AI... please wait.";
        resultBox.style.background = "#fff"; // Temp white background
        resultBox.style.color = "#333";
        processBtn.disabled = true;
        processBtn.innerText = "Processing...";

        // Call the new backend endpoint
        fetch(`/process-crop/${{fileId}}/${{filename}}/${{band}}`)
        .then(res => res.json())
        .then(data => {{
            if (data.status === "error") {{
                resultBox.value = "Error from AI: " + data.message;
                resultBox.style.color = "red";
            }} else {{
                resultBox.value = data.xml;
                // Revert to dark theme for code
                resultBox.style.background = "#2d2d2d";
                resultBox.style.color = "#f8f8f2";
            }}
        }})
        .catch(err => {{
            resultBox.value = "Request failed: " + err;
            resultBox.style.color = "red";
        }})
        .finally(() => {{
            // Restore button state
            processBtn.disabled = false;
            processBtn.innerText = "Process to XML";
        }});
    }}
    </script>
    """
    return html


# ================= NEW: PROCESS CROP ENDPOINT =================
@app.get("/process-crop/{file_id}/{filename}/{band}")
async def process_crop(file_id: str, filename: str, band: str):
    image_path = os.path.join(IMAGE_DIR, file_id, filename)

    if not os.path.exists(image_path):
        return JSONResponse({"status": "error", "message": f"File {filename} not found."})

    try:
        # Load the image
        img = Image.open(image_path)
        
        # Craft the dynamic prompt based on the band type
        # I am using the precision rules established in earlier chats
        prompt = f"""
        Analyze this cropped image and generate high-precision JRXML code for the JasperReports <{band}> band.
        
        Rules:
        1. Use <staticText> for all elements.
        2. Set proper (x, y, width, height) relative to the image size.
        3. Use <box><pen lineWidth="1.0" lineColor="#000000"/></box> for borders is border is required.
        4. textAlignment="Center", verticalAlignment="Middle".
        5. Extract actual text accurately.
        6. DO NOT include UUIDs.
        7. NO markdown formatting. Output ONLY the XML block starting with <{band}> and ending with </{band}>.
        Use <staticText> for every cell in the table.
        """

        # Call Gemini API
        response = model.generate_content([prompt, img])
        xml_content = response.text.strip()

        # Final cleanup just in case AI adds markdown wraps
        xml_content = xml_content.replace("```xml", "").replace("```", "").strip()

        return JSONResponse({"status": "success", "xml": xml_content})

    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Gemini API Exception: {str(e)}"})

@app.get("/project-image/{file_id}/{filename}")
def serve_project_image(file_id: str, filename: str):
    path = os.path.join(CROP_IMAGE_DIR, file_id, filename)
    return FileResponse(path)

@app.delete("/delete-region/{file_id}/{filename}")
def delete_region(file_id: str, filename: str):
    folder = os.path.join(CROP_IMAGE_DIR, file_id)
    file_path = os.path.join(folder, filename)
    metadata_path = os.path.join(folder, "metadata.json")

    # Delete image file
    if os.path.exists(file_path):
        os.remove(file_path)

    # Update metadata.json
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            data = json.load(f)

        data["regions"] = [
            r for r in data["regions"] if r["file"] != filename
        ]

        with open(metadata_path, "w") as f:
            json.dump(data, f, indent=4)

    return {"status": "deleted"}



# 🔐 Gemini Setup
genai.configure(api_key="AIzaSyCu6iDYu4QDtaPNnFIAceRWCFYYKKzJboE")
model = genai.GenerativeModel("gemini-3-flash-preview")


# ================= HOME =================
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h2>Upload PDF</h2>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file"/>
        <button type="submit">Upload</button>
    </form>
    """


# ================= UPLOAD =================
@app.post("/upload", response_class=HTMLResponse)
async def upload_pdf(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())

    pdf_bytes = await file.read()

    images = convert_from_bytes(pdf_bytes)
    image_path = os.path.join(IMAGE_DIR, f"{file_id}.png")
    images[0].save(image_path, "PNG")

    return f"""
    <h2>Draw Regions</h2>

    <select id="band">
            <option value="title">Title</option>
            <option value="detail">Detail</option>
            <option value="pageHeader">Page Header</option>
            <option value="pageFooter">Page Footer</option>
            <option value="columnHeader">Column Header</option>
    </select>
    <br><br>
    <canvas id="canvas"></canvas>
    <br><br>
    <button onclick="saveRegions()">Save</button>

    <script>
        const imageUrl = "/image/{file_id}";
        const fileId = "{file_id}";
    </script>

    {get_canvas_script()}
    """


# ================= SERVE IMAGE =================
@app.get("/image/{file_id}")
def get_image(file_id: str):
    return FileResponse(os.path.join(IMAGE_DIR, f"{file_id}.png"))


# ================= CANVAS SCRIPT =================
def get_canvas_script():
    return """
    <script>
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");

    let rectangles = [];
    let img = new Image();
    img.src = imageUrl;

    img.onload = function () {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
    };

    let startX, startY, isDrawing = false;

    canvas.addEventListener("mousedown", e => {
        startX = e.offsetX;
        startY = e.offsetY;
        isDrawing = true;
    });

    canvas.addEventListener("mouseup", e => {
        if (!isDrawing) return;

        let rect = {
            x: startX,
            y: startY,
            width: e.offsetX - startX,
            height: e.offsetY - startY,
            band: document.getElementById("band").value
        };

        rectangles.push(rect);
        draw();
        isDrawing = false;
    });

    function draw() {
        ctx.drawImage(img, 0, 0);
        ctx.strokeStyle = "red";

        rectangles.forEach(r => {
            ctx.strokeRect(r.x, r.y, r.width, r.height);
        });
    }

    function saveRegions() {
        fetch("/save-regions", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                file_id: fileId,
                regions: rectangles
            })
        })
        .then(res => res.json())
        .then(() => alert("Saved"));
    }
    </script>
    """


# ================= SAVE CROPS =================
@app.post("/save-regions")
async def save_regions(request: Request):
    data = await request.json()

    file_id = data["file_id"]
    regions = data["regions"]

    image_path = os.path.join(IMAGE_DIR, f"{file_id}.png")
    folder = os.path.join(CROP_IMAGE_DIR, file_id)
    os.makedirs(folder, exist_ok=True)

    img = Image.open(image_path)

    results = []

    for i, r in enumerate(regions):
        x, y, w, h = int(r["x"]), int(r["y"]), int(r["width"]), int(r["height"])

        if w < 0:
            x += w
            w = abs(w)
        if h < 0:
            y += h
            h = abs(h)

        crop = img.crop((x, y, x + w, y + h))

        filename = f"crop_{i}.png"
        path = os.path.join(folder, filename)
        crop.save(path)

        results.append({"band": r["band"], "file": filename})

    with open(os.path.join(folder, "metadata.json"), "w") as f:
        json.dump(results, f)

    return {"status": "saved"}


# ================= GEMINI =================
# def generate_jrxml(image_path):
#     img = Image.open(image_path)

#     prompt = """
# Generate clean JRXML using staticText.

# Rules:
# - No explanation
# - No comments
# - Proper reportElement (x,y,width,height)
# - Use box borders
# - Table-like alignment
# """

#     response = model.generate_content([prompt, img])
#     return response.text.replace("```xml", "").replace("```", "").strip()


# ================= GENERATE XML =================
# @app.get("/generate/{file_id}")
# def generate(file_id: str):
#     folder = os.path.join(IMAGE_DIR, file_id)

#     with open(os.path.join(folder, "metadata.json")) as f:
#         data = json.load(f)

#     final_xml = ""

#     for item in data:
#         path = os.path.join(folder, item["file"])
#         xml = generate_jrxml(path)

#         final_xml += f"\n{xml}\n"

#     output_path = os.path.join(folder, "final.txt")

#     with open(output_path, "w") as f:
#         f.write(final_xml)

#     return {"file": output_path}



# ================= REFINED GEMINI LOGIC =================
def generate_jrxml_direct(image_path):
    img = Image.open(image_path)
    
    # This prompt is tuned for maximum structural accuracy
    prompt = """
    Analyze this image and generate the complete JRXML <detail> band code.
    
    Layout Rules:
    1. Use <staticText> for every cell in the table.
    2. Use <box><pen lineWidth="1.0" lineColor="#000000"/></box> for all cell if it is similer to table format.
    3. Ensure coordinates (x, y) and dimensions (width, height) create a perfect grid.
    4. Text alignment: textAlignment="Center" and verticalAlignment="Middle".
    5. NO UUIDs. NO Markdown code blocks (no ```xml). 
    6. Extract the actual text from the image for each cell.
    7. If the table is wide, assume a landscape width (~800px).
    
    Output ONLY the <detail>...</detail> XML block.
    """

    response = model.generate_content([prompt, img])
    # Clean up any stray markdown just in case
    clean_xml = response.text.replace("```xml", "").replace("```", "").strip()
    return clean_xml

# ================= SIMPLIFIED GENERATE ENDPOINT =================
@app.get("/generate/{file_id}", response_class=HTMLResponse)
def generate(file_id: str):
    # Path to the full page image saved during upload
    folder_path = os.path.join(CROP_IMAGE_DIR, file_id)

    if not os.path.exists(folder_path):
        return f"<h2>Error: Folder for {file_id} not found.</h2>"

    metadata_path = os.path.join(folder_path, "metadata.json")

    with open(metadata_path) as f:
        data = json.load(f)

    return data
    # Send the full image to Gemini
    # try:
    #     final_xml = generate_jrxml_direct(image_path)
    # except Exception as e:
    #     return f"<h2>AI Error: {str(e)}</h2>"

    # # Return the code in a copy-friendly web interface
    # return f"""
    # <html>
    #     <head>
    #         <title>Jasper Automation - XML Result</title>
    #         <style>
    #             body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background: #f4f7f6; }}
    #             .container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
    #             textarea {{ width: 100%; height: 60vh; font-family: 'Courier New', Courier, monospace; font-size: 14px; padding: 15px; border: 1px solid #ccc; border-radius: 4px; background: #2d2d2d; color: #f8f8f2; }}
    #             button {{ padding: 10px 20px; font-size: 16px; cursor: pointer; background: #28a745; color: white; border: none; border-radius: 4px; margin-top: 10px; }}
    #             button:hover {{ background: #218838; }}
    #             .back-btn {{ background: #6c757d; text-decoration: none; display: inline-block; padding: 10px 20px; color: white; border-radius: 4px; }}
    #         </style>
    #     </head>
    #     <body>
    #         <div class="container">
    #             <h2>Generated JRXML (Detail Band)</h2>
    #             <p>The AI has analyzed your image and mapped the table layout. Copy the code below:</p>
    #             <textarea id="xmlbox">{final_xml}</textarea>
    #             <br>
    #             <button onclick="copyCode()">Copy XML to Clipboard</button>
    #             <a href="/" class="back-btn">Upload Another</a>
    #         </div>

    #         <script>
    #         function copyCode() {{
    #             const copyText = document.getElementById("xmlbox");
    #             copyText.select();
    #             document.execCommand("copy");
    #             alert("JRXML copied successfully!");
    #         }}
    #         </script>
    #     </body>
    # </html>
    # """