from fastapi import FastAPI, UploadFile, File, Request, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pdf2image import convert_from_bytes
from PIL import Image
import google.generativeai as genai
import os
import uuid
import json
import base64
import xml.etree.ElementTree as ET


app = FastAPI()

UPLOAD_DIR = "uploads"
IMAGE_DIR = "images"
CROP_IMAGE_DIR = "crop_images"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)



# 🔐 Gemini Setup
genai.configure(api_key="AIzaSyAcWnzx6Ny9SQVE_hcEtAG2qxB-S-0wB2k")
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


# ================= PROJECT VIEW =================
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

@app.get("/project/{file_id}", response_class=HTMLResponse)
def view_project(file_id: str):
    # Ensure this matches your directory variable (CROP_IMAGE_DIR or IMAGE_DIR)
    folder = os.path.join(CROP_IMAGE_DIR, file_id) 
    metadata_path = os.path.join(folder, "metadata.json")

    html = f"""
    <style>
        .crop-container {{ margin-bottom: 30px; border-bottom: 2px solid #eee; padding-bottom: 20px; }}
        .controls {{ margin: 15px 0; display: flex; gap: 10px; align-items: center; }}
        .btn {{ padding: 8px 15px; cursor: pointer; border: 1px solid #ccc; border-radius: 4px; font-weight: bold; }}
        .btn-delete {{ background-color: #ffcccc; color: #a00; border-color: #faa; }}
        .btn-process {{ background-color: #28a745; color: white; border-color: #218838; }}
        .refine-input {{ flex-grow: 1; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }}
        .result-box {{ width: 100%; height: 250px; font-family: 'Courier New', monospace; margin-top: 10px; display: none; background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 4px; font-size: 13px; line-height: 1.5; }}
    </style>
    <h2>Project: {file_id}</h2>
    """

    if not os.path.exists(metadata_path):
        html += "<p>No regions defined. <a href='/'>Start Over</a></p>"
        return html

    with open(metadata_path, "r") as f:
        regions = json.load(f)

    for item in regions:
        filename = item["file"]
        band = item["band"]
        safe_f_id = filename.replace(".", "_")

        html += f"""
        <div class="crop-container" id="container_{safe_f_id}">
            <b>{filename} (Target Band: <span style="color:blue;">{band}</span>)</b><br>
            <img src="/project-image/{file_id}/{filename}" width="300" style="border: 1px solid #999; margin-top:10px;"><br>
            
            <div class="controls">
                <input type="text" id="prompt_{safe_f_id}" class="refine-input" 
                       placeholder="Optional: Add extra instructions (e.g., 'make text bold', '3 columns')...">
                
                <button class="btn btn-process" id="process_{safe_f_id}" 
                        onclick="processImage('{file_id}', '{filename}', '{band}')">Process to XML</button>
                
                <button class="btn btn-delete" onclick="deleteImage('{filename}')">Delete</button>
            </div>
            
            <textarea class="result-box" id="result_{safe_f_id}" readonly></textarea>
        </div>
        """

    html += f'<br><a href="/edit/{file_id}" style="text-decoration:none;"><button class="btn">Edit Regions</button></a>'

    html += f"""
    <script>
    const fileId = "{file_id}";

    function deleteImage(filename) {{
        if (!confirm("Are you sure?")) return;
        fetch(`/delete-region/${{fileId}}/${{filename}}`, {{ method: "DELETE" }})
        .then(res => res.json())
        .then(() => {{
            alert("Deleted!");
            location.reload();
        }});
    }}

    function processImage(fileId, filename, band) {{
        const safe_f_id = filename.replace(".", "_");
        const resultBox = document.getElementById("result_" + safe_f_id);
        const processBtn = document.getElementById("process_" + safe_f_id);
        const extraPrompt = document.getElementById("prompt_" + safe_f_id).value;

        // UI Feedback
        resultBox.style.display = "block";
        resultBox.value = "Analyzing image and generating JRXML... please wait.";
        resultBox.style.background = "#fff";
        resultBox.style.color = "#333";
        processBtn.disabled = true;
        processBtn.innerText = "Processing...";

        // Encode the extra prompt to handle special characters in URL
        const queryParams = extraPrompt ? `?extra=${{encodeURIComponent(extraPrompt)}}` : "";

        fetch(`/process-crop/${{fileId}}/${{filename}}/${{band}}${{queryParams}}`)
        .then(res => res.json())
        .then(data => {{
            if (data.status === "error") {{
                resultBox.value = "AI Error: " + data.message;
                resultBox.style.color = "red";
            }} else {{
                resultBox.value = data.xml;
                resultBox.style.background = "#2d2d2d";
                resultBox.style.color = "#f8f8f2";
            }}
        }})
        .catch(err => {{
            resultBox.value = "Network failed: " + err;
            resultBox.style.color = "red";
        }})
        .finally(() => {{
            processBtn.disabled = false;
            processBtn.innerText = "Process to XML";
        }});
    }}
    </script>
    """
    return html

# ================= NEW: PROCESS CROP ENDPOINT =================
@app.get("/process-crop/{file_id}/{filename}/{band}")
async def process_crop(file_id: str, filename: str, band: str, extra: str = Query("")):
    # Ensure this matches your global directory variable
    image_path = os.path.join(CROP_IMAGE_DIR, file_id, filename)

    if not os.path.exists(image_path):
        return JSONResponse({"status": "error", "message": f"File {filename} not found."})

    try:
        # Load the image
        img = Image.open(image_path)
        
        # Base Prompt Construction
        prompt = f"""
       
        Analyze this cropped image and generate high-precision JRXML code for the JasperReports <{band}> band.

        Mandatory Rules:
        1. Use <staticText> for all elements/cells in the table.
        2. Set proper (x, y, width, height) relative to the image size.
        3. Use <box><pen lineWidth="1.0" lineColor="#000000"/></box> for borders if borders are present in the image.
        4. STRICT HIERARCHY: All font settings must be inside <textElement>. 
        The order MUST be: <textElement> -> <font/> -> </textElement>.
        Example: <textElement><font size="10" isBold="true"/></textElement>.
        5. Use textAlignment="Center" and verticalAlignment="Middle" for consistency unless the image clearly shows left/right alignment.
        6. Extract actual text from the image accurately.
        7. STRICT: DO NOT include UUID attributes.
        8. When a small square box is found (like a checkbox), use the <rectangle> component.
        9. STRICT: NO markdown formatting. Output ONLY the XML block starting with <{band}> and ending with </{band}>.
        """
        
        # Append additional user instructions if they exist
        if extra:
            prompt += f"\nADDITIONAL USER REFINEMENT INSTRUCTIONS: {extra}\n"

        # Call Gemini API
        response = model.generate_content([prompt, img])
        xml_content = response.text.strip()

        # Final cleanup to remove any potential markdown code blocks
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
    # Ensure this matches your global IMAGE_DIR variable
    folder = os.path.join(CROP_IMAGE_DIR, file_id) 
    file_path = os.path.join(folder, filename)
    metadata_path = os.path.join(folder, "metadata.json")

    # 1. Physical file deletion
    if os.path.exists(file_path):
        os.remove(file_path)

    # 2. Metadata sync
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            data = json.load(f)

        # 'data' is a List: [{"band": "...", "file": "..."}]
        # We filter out the item where the filename matches
        updated_data = [item for item in data if item.get("file") != filename]

        # Write the cleaned list back to the file
        with open(metadata_path, "w") as f:
            json.dump(updated_data, f, indent=4)
            
        print(f"Metadata updated. Remaining items: {len(updated_data)}")

    return {"status": "deleted"}



@app.get("/preview", response_class=HTMLResponse)
def preview_page():
    return """
    <html>
        <head>
            <title>JRXML Live Previewer</title>
            <style>
                body { display: flex; height: 100vh; margin: 0; font-family: sans-serif; }
                #editor { width: 50%; padding: 20px; background: #2d2d2d; color: white; display: flex; flex-direction: column; }
                #viewer { width: 50%; padding: 20px; background: #f0f0f0; overflow: auto; position: relative; }
                textarea { flex-grow: 1; font-family: monospace; background: #1e1e1e; color: #d4d4d4; padding: 10px; border: none; }
                .report-band { background: white; border: 1px dashed #ccc; margin-bottom: 20px; position: relative; min-height: 200px; width: 595px; } /* A4 width approx */
                .element { position: absolute; border: 1px solid black; font-size: 10px; display: flex; align-items: center; justify-content: center; overflow: hidden; background: rgba(255,255,255,0.8); }
                button { padding: 10px; margin-bottom: 10px; cursor: pointer; background: #28a745; color: white; border: none; }
            </style>
        </head>
        <body>
            <div id="editor">
                <h2>Paste JRXML Detail/Band Code</h2>
                <textarea id="xmlInput" placeholder="Paste your <detail> or <staticText> tags here..."></textarea>
                <button onclick="updatePreview()">Render Preview</button>
            </div>
            <div id="viewer">
                <h2>Visual Layout Map</h2>
                <div id="canvas"></div>
            </div>

            <script>
                function updatePreview() {
                    const xmlText = document.getElementById('xmlInput').value;
                    const canvas = document.getElementById('canvas');
                    canvas.innerHTML = ''; // Clear previous

                    try {
                        const parser = new DOMParser();
                        const xmlDoc = parser.parseFromString(`<root>${xmlText}</root>`, "text/xml");
                        const elements = xmlDoc.getElementsByTagName("reportElement");

                        // Create a simulated band
                        const band = document.createElement('div');
                        band.className = 'report-band';
                        
                        Array.from(elements).forEach(el => {
                            const x = parseInt(el.getAttribute('x')) || 0;
                            const y = parseInt(el.getAttribute('y')) || 0;
                            const w = parseInt(el.getAttribute('width')) || 100;
                            const h = parseInt(el.getAttribute('height')) || 20;
                            
                            // Find the text content (either in staticText or textField)
                            const parent = el.parentElement;
                            let content = "Text";
                            const textNode = parent.getElementsByTagName("text")[0];
                            if(textNode) content = textNode.textContent;

                            const box = document.createElement('div');
                            box.className = 'element';
                            box.style.left = x + 'px';
                            box.style.top = y + 'px';
                            box.style.width = w + 'px';
                            box.style.height = h + 'px';
                            box.innerText = content;
                            
                            band.appendChild(box);
                        });
                        
                        canvas.appendChild(band);
                    } catch (e) {
                        alert("Invalid XML: " + e.message);
                    }
                }
            </script>
        </body>
    </html>
    """