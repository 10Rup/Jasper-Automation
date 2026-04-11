from fastapi import FastAPI, UploadFile, File, Request, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pdf2image import convert_from_bytes
from PIL import Image
# import google.generativeai as genai
import google.genai as genai
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

def load_reference():
    try:
        with open("reference.txt", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return ""

# 🔐 Gemini Setup
# genai.configure(api_key="AIzaSyAcWnzx6Ny9SQVE_hcEtAG2qxB-S-0wB2k")
client = genai.Client(api_key="AIzaSyAcWnzx6Ny9SQVE_hcEtAG2qxB-S-0wB2k")
# model = genai.GenerativeModel("gemini-3-flash-preview")
model = "gemini-3-flash-preview"

import pandas as pd
import io


# ================= Excel HOME =================
@app.get("/excel-tool", response_class=HTMLResponse)
def excel_tool():
    return """
    <h2>Excel to Jasper XML Converter</h2>
    <p>Upload an excel file to auto-generate ColumnHeader and Detail bands.</p>
    <input type="file" id="excelFile" accept=".xlsx, .xls"/>
    <button onclick="uploadExcel()">Convert to XML</button>
    <br><br>
    <textarea id="excelResult" style="width:100%; height:400px; background:#2d2d2d; color:white;"></textarea>

    <script>
    function uploadExcel() {
        const fileInput = document.getElementById('excelFile');
        const resultBox = document.getElementById('excelResult');
        if (!fileInput.files[0]) return alert("Select a file");

        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        resultBox.value = "Processing Excel...";
        
        fetch("/process-excel", {
            method: "POST",
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            if(data.status === "success") {
                resultBox.value = data.xml;
            } else {
                alert("Error: " + data.message);
            }
        });
    }
    </script>
    """

# ================= EXCEL TO JRXML =================
@app.post("/process-excel")
async def process_excel(file: UploadFile = File(...)):
    try:
        # Read Excel content
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        columns = df.columns.tolist()
        
        # Configuration for layout
        col_width = 100
        row_height = 20
        current_x = 0
        
        # 1. Generate columnHeader Band
        column_header_xml = "    <columnHeader>\n        <band height=\"30\">\n"
        for col in columns:
            column_header_xml += f"""            <staticText>
                <reportElement x="{current_x}" y="0" width="{col_width}" height="{row_height}"/>
                <box><pen lineWidth="1.0"/></box>
                <textElement textAlignment="Center" verticalAlignment="Middle">
                    <font isBold="true"/>
                </textElement>
                <text><![CDATA[{col}]]></text>
            </staticText>\n"""
            current_x += col_width
        column_header_xml += "        </band>\n    </columnHeader>"

        # 2. Generate detail Band (Mapping fields)
        current_x = 0
        detail_xml = "    <detail>\n        <band height=\"25\">\n"
        for col in columns:
            # Clean column name for field reference (no spaces/special chars)
            field_name = str(col).replace(" ", "_")
            detail_xml += f"""            <textField>
                <reportElement x="{current_x}" y="0" width="{col_width}" height="{row_height}"/>
                <box><pen lineWidth="1.0"/></box>
                <textElement textAlignment="Center" verticalAlignment="Middle"/>
                <textFieldExpression><![CDATA[$F{{{field_name}}}]]></textFieldExpression>
            </textField>\n"""
            current_x += col_width
        detail_xml += "        </band>\n    </detail>"

        # 3. Generate Fields definitions (Required for Jasper)
        fields_xml = ""
        for col in columns:
            field_name = str(col).replace(" ", "_")
            fields_xml += f'    <field name="{field_name}" class="java.lang.String"/>\n'

        full_xml = f"{fields_xml}\n{column_header_xml}\n{detail_xml}"

        return JSONResponse({
            "status": "success",
            "xml": full_xml,
            "message": "Excel structure converted to Jasper Bands successfully."
        })

    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)})


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


# ================= CANVAS SCRIPT (ADVANCED EDITING) =================
def get_canvas_script():
    return """
    <script>
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    const bandSelect = document.getElementById("band");

    let rectangles = [];
    let img = new Image();
    img.src = imageUrl;

    let selectedRect = null; // Tracks the box being edited
    let isDrawing = false;
    let isDragging = false;
    let isResizing = false;
    let resizeHandle = null; // Which corner ('tl', 'tr', 'bl', 'br')

    let startX, startY, offX, offY;
    const HANDLE_SIZE = 8; // Size of corner resize handles

    img.onload = function () {
        canvas.width = img.width;
        canvas.height = img.height;
        draw();
    };

    // --- Helper: Check if point (x,y) is inside rectangle r ---
    function isInside(x, y, r) {
        const rx = r.x, ry = r.y, rw = r.width, rh = r.height;
        // Handle negative widths/heights
        const realX = rw > 0 ? rx : rx + rw;
        const realY = rh > 0 ? ry : ry + rh;
        const realW = Math.abs(rw);
        const realH = Math.abs(rh);
        return x >= realX && x <= realX + realW && y >= realY && y <= realY + realH;
    }

    // --- Helper: Get resize handle at point (x,y) for selected rect ---
    function getHandle(x, y, r) {
        const rx = r.x, ry = r.y, rw = r.width, rh = r.height;
        const rXR = rx + rw;
        const rYB = ry + rh;
        const h = HANDLE_SIZE / 2;

        if (x >= rx-h && x <= rx+h && y >= ry-h && y <= ry+h) return 'tl'; // Top Left
        if (x >= rXR-h && x <= rXR+h && y >= ry-h && y <= ry+h) return 'tr'; // Top Right
        if (x >= rx-h && x <= rx+h && y >= rYB-h && y <= rYB+h) return 'bl'; // Bottom Left
        if (x >= rXR-h && x <= rXR+h && y >= rYB-h && y <= rYB+h) return 'br'; // Bottom Right
        return null;
    }

    // --- Interaction 1: Band Dropdown Sync ---
    bandSelect.addEventListener("change", e => {
        if (selectedRect) {
            selectedRect.band = e.target.value;
            draw();
        }
    });

    // --- Interaction 2: Mouse Down (New, Edit, Resize) ---
    canvas.addEventListener("mousedown", e => {
        const mx = e.offsetX;
        const my = e.offsetY;

        // A. Check for Resizing existing selected box
        if (selectedRect) {
            resizeHandle = getHandle(mx, my, selectedRect);
            if (resizeHandle) {
                isResizing = true;
                return;
            }
        }

        // B. Check for Dragging/Selecting an existing box
        let found = false;
        rectangles.slice().reverse().forEach(r => { // Check newest first
            if (!found && isInside(mx, my, r)) {
                selectedRect = r;
                offX = mx - r.x; // Save offsets for smooth dragging
                offY = my - r.y;
                isDragging = true;
                found = true;
                bandSelect.value = r.band; // Sync dropdown
            }
        });

        if (found) { draw(); return; }

        // C. Start Drawing a New Box
        selectedRect = null; // Clear selection
        bandSelect.value = bandSelect.options[1].value; // Reset to default
        startX = mx;
        startY = my;
        isDrawing = true;
        draw();
    });

    // --- Interaction 3: Mouse Move (Move, Resize, Draw Preview) ---
    canvas.addEventListener("mousemove", e => {
        const mx = e.offsetX;
        const my = e.offsetY;

        // Update Cursor UI feedback
        if (selectedRect) {
            const h = getHandle(mx, my, selectedRect);
            if (h === 'tl' || h === 'br') canvas.style.cursor = 'nwse-resize';
            else if (h === 'tr' || h === 'bl') canvas.style.cursor = 'nesw-resize';
            else if (isInside(mx, my, selectedRect)) canvas.style.cursor = 'move';
            else canvas.style.cursor = 'default';
        } else {
            canvas.style.cursor = 'default';
        }

        if (isResizing && selectedRect) {
            const r = selectedRect;
            if (resizeHandle === 'tl') { r.width += (r.x - mx); r.height += (r.y - my); r.x = mx; r.y = my; }
            if (resizeHandle === 'tr') { r.width = mx - r.x; r.height += (r.y - my); r.y = my; }
            if (resizeHandle === 'bl') { r.x = mx; r.width += (selectedRect.x - mx); r.height = my - r.y; }
            if (resizeHandle === 'br') { r.width = mx - r.x; r.height = my - r.y; }
            draw();
        } else if (isDragging && selectedRect) {
            selectedRect.x = mx - offX;
            selectedRect.y = my - offY;
            draw();
        } else if (isDrawing) {
            draw();
            // New Box Preview (Dotted Blue)
            ctx.setLineDash([5, 5]);
            ctx.strokeStyle = "blue";
            ctx.lineWidth = 2;
            ctx.strokeRect(startX, startY, mx - startX, my - startY);
            ctx.setLineDash([]);
        }
    });

    // --- Interaction 4: Mouse Up (Save/Finalize) ---
    canvas.addEventListener("mouseup", e => {
        if (isDrawing) {
            let rect = {
                x: startX,
                y: startY,
                width: e.offsetX - startX,
                height: e.offsetY - startY,
                band: bandSelect.value
            };
            if (Math.abs(rect.width) > 5 && Math.abs(rect.height) > 5) {
                rectangles.push(rect);
                selectedRect = rect; // Select new box immediately
            }
        }
        isDrawing = isDragging = isResizing = false;
        resizeHandle = null;
        draw();
    });

    // --- Interaction 5: Keyboard Delete (Delete Selected) ---
    window.addEventListener("keydown", e => {
        if ((e.key === "Delete" || e.key === "Backspace") && selectedRect) {
            e.preventDefault();
            rectangles = rectangles.filter(r => r !== selectedRect);
            selectedRect = null;
            draw();
        }
    });

    function draw() {
        ctx.drawImage(img, 0, 0); // Background Image
        
        ctx.lineWidth = 2;
        rectangles.forEach(r => {
            const isSel = (r === selectedRect);
            
            // Draw Box
            ctx.strokeStyle = isSel ? "lime" : "red"; // Green if selected
            ctx.setLineDash(isSel ? [2, 2] : []);     // Dashed if selected
            ctx.strokeRect(r.x, r.y, r.width, r.height);
            ctx.setLineDash([]); // Reset
            
            // Draw Label
            ctx.fillStyle = isSel ? "lime" : "red";
            ctx.font = "bold 12px Arial";
            ctx.fillText(r.band.toUpperCase(), r.x + 5, r.y + 15);

            // Draw Resize Handles (if selected)
            if (isSel) {
                ctx.fillStyle = "white";
                ctx.strokeStyle = "lime";
                ctx.lineWidth = 1;
                const h = HANDLE_SIZE / 2;
                const cornerHandles = [
                    [r.x-h, r.y-h], [r.x+r.width-h, r.y-h], 
                    [r.x-h, r.y+r.height-h], [r.x+r.width-h, r.y+r.height-h]
                ];
                cornerHandles.forEach(([hx, hy]) => {
                    ctx.fillRect(hx, hy, HANDLE_SIZE, HANDLE_SIZE);
                    ctx.strokeRect(hx, hy, HANDLE_SIZE, HANDLE_SIZE);
                });
                ctx.lineWidth = 2; // Reset
            }
        });
    }

    function saveRegions() {
        if (rectangles.length === 0) { alert("No regions to save."); return; }
        fetch("/save-regions", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                file_id: fileId,
                regions: rectangles
            })
        })
        .then(res => res.json())
        .then(() => alert("All regions saved and synced successfully!"));
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
    img = img.resize((800, 800))

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

        # # Call Gemini API
        # response = model.generate_content([prompt, img])
        # xml_content = response.text.strip()

        # # Final cleanup to remove any potential markdown code blocks
        # xml_content = xml_content.replace("```xml", "").replace("```", "").strip()


        # Use the client to generate content
        response = client.models.generate_content(
            model=model, # or "gemini-1.5-flash"
            contents=[prompt, img]
        )
        
        # In the new SDK, the text is accessed via .text
        xml_content = response.text.strip()

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