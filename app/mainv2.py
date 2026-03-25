from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import FileResponse, HTMLResponse
from pdf2image import convert_from_bytes
import os
import uuid
from PIL import Image
import shutil
import json
from . import test_ocr

app = FastAPI()

UPLOAD_DIR = "uploads"
IMAGE_DIR = "images"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)


from openai import OpenAI

client = OpenAI(api_key="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")


def generate_jrxml_prompt(text, band):
    return f"""
    You are a JasperReports expert.

    Convert the given text into a VALID JRXML component.

    STRICT RULES:
    - Output ONLY XML (no explanation)
    - Do NOT use markdown (no ```xml)
    - Use <staticText> unless dynamic field is obvious
    - Use:
        x=0
        y=0
        width=595
        height=842
    - Wrap text inside <![CDATA[]]>

    Band: {band}

    TEXT:
    {text}
    """

def generate_jrxml_from_text(text, band):
    prompt = generate_jrxml_prompt(text, band)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Return only valid JRXML XML. No markdown."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content.strip()

def clean_ai_output(text):
    return text.replace("```xml", "").replace("```", "").strip()

@app.get("/generate-jrxml-components/{file_id}")
def generate_jrxml_components(file_id: str):
    import json, os

    folder = os.path.join(IMAGE_DIR, file_id)
    ocr_path = os.path.join(folder, "ocr.json")

    with open(ocr_path) as f:
        ocr_data = json.load(f)

    results = []

    for item in ocr_data:
        text = item["text"]
        band = item["band"]

        if not text.strip():
            continue

        jrxml = generate_jrxml_from_text(text, band)
        jrxml = clean_ai_output(jrxml)

        results.append({
            "band": band,
            "jrxml": jrxml
        })

    # Save result
    output_path = os.path.join(folder, "jrxml_components.json")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=4)

    return {"status": "done", "file": output_path}



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
            body: JSON.stringify({
                file_id: imageUrl.split("/").pop(),
                regions: rectangles
            })
        })
        .then(res => res.json())
        .then(data => alert("Saved!"));
    }
    </script>
    """

def get_edit_canvas_script():
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

        // Load existing regions
        fetch(`/regions/${fileId}`)
            .then(res => res.json())
            .then(data => {
                if (data.regions) {
                    rectangles = data.regions;
                    draw();
                }
            });
    };

    let startX, startY, isDrawing = false;

    canvas.addEventListener("mousedown", (e) => {
        startX = e.offsetX;
        startY = e.offsetY;
        isDrawing = true;
    });

    canvas.addEventListener("mouseup", (e) => {
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
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                file_id: fileId,
                regions: rectangles
            })
        })
        .then(res => res.json())
        .then(() => alert("Updated!"));
    }
    </script>
    """

def clean_text(text):
    return " ".join(text.split())

def process_ocr_for_project(file_id):
    folder = os.path.join(IMAGE_DIR, file_id)
    metadata_path = os.path.join(folder, "metadata.json")

    with open(metadata_path) as f:
        metadata = json.load(f)

    results = []

    for region in metadata["regions"]:
        image_path = os.path.join(folder, region["file"])

        text = test_ocr.extract_text_from_image(image_path)

        results.append({
            "band": region["band"],
            "file": region["file"],
            "text": clean_text(text)
        })

    # Save OCR output
    output_path = os.path.join(folder, "ocr.json")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=4)

    return output_path



@app.get("/run-ocr/{file_id}")
def run_ocr(file_id: str):
    output_path = process_ocr_for_project(file_id)
    return {"status": "done", "file": output_path}


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

    file_id = data["file_id"]
    regions = data["regions"]

    image_path = os.path.join(IMAGE_DIR, f"{file_id}.png")
    base_output_dir = os.path.join(IMAGE_DIR, file_id)

    os.makedirs(base_output_dir, exist_ok=True)

    # if os.path.exists(base_output_dir):
    #     for f in os.listdir(base_output_dir):
    #         if f.endswith(".png"):
    #             os.remove(os.path.join(base_output_dir, f))

    img = Image.open(image_path)

    band_count = {}
    metadata = {
        "file_id": file_id,
        "regions": []
    }

    for region in regions:
        x = int(region["x"])
        y = int(region["y"])
        w = int(region["width"])
        h = int(region["height"])
        band = region["band"]

        # Fix negative width/height
        if w < 0:
            x = x + w
            w = abs(w)
        if h < 0:
            y = y + h
            h = abs(h)

        # Count per band
        band_count[band] = band_count.get(band, 0) + 1
        count = band_count[band]

        filename = f"{band}_{count}.png"
        save_path = os.path.join(base_output_dir, filename)

        cropped = img.crop((x, y, x + w, y + h))
        cropped.save(save_path)

        # 👇 Save metadata
        metadata["regions"].append({
            "band": band,
            "file": filename,
            "x": x,
            "y": y,
            "width": w,
            "height": h
        })

    # 👇 Save metadata.json
    import json
    metadata_path = os.path.join(base_output_dir, "metadata.json")

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)

    return {
        "status": "saved",
        "folder": base_output_dir,
        "metadata_file": metadata_path
    }

@app.get("/image/{file_id}")
def get_image(file_id: str):
    image_path = os.path.join(IMAGE_DIR, f"{file_id}.png")
    return FileResponse(image_path)


@app.get("/projects", response_class=HTMLResponse)
def list_projects():
    folders = os.listdir(IMAGE_DIR)

    html = "<h2>Projects</h2><ul>"

    for f in folders:
        path = os.path.join(IMAGE_DIR, f)
        if os.path.isdir(path):
            html += f'<li><a href="/project/{f}">{f}</a></li>'

    html += "</ul>"
    return html

@app.get("/project/{file_id}", response_class=HTMLResponse)
def view_project(file_id: str):
    folder = os.path.join(IMAGE_DIR, file_id)

    files = os.listdir(folder)

    html = f"<h2>Project: {file_id}</h2>"

    for f in files:
        if f.endswith(".png"):
            # html += f'<div><h2>{f}</h2><img src="/project-image/{file_id}/{f}" width="200"></div>'
            html += f"""
            <div style="margin-bottom:20px;">
                <b>{f}</b><br>
                <img src="/project-image/{file_id}/{f}" width="200"><br>
                <button onclick="deleteImage('{f}')">Delete</button>
            </div>
            """

    html += f'<br><a href="/edit/{file_id}">Edit Regions</a>'

    html += f"""
    <script>
    const fileId = "{file_id}";

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
    </script>
    """
    return html

@app.get("/project-image/{file_id}/{filename}")
def serve_project_image(file_id: str, filename: str):
    path = os.path.join(IMAGE_DIR, file_id, filename)
    return FileResponse(path)

@app.get("/edit/{file_id}", response_class=HTMLResponse)
def edit_project(file_id: str):
    return f"""
    <html>
    <body>
        <h2>Edit Regions</h2>

        <canvas id="canvas"></canvas>
        <br><br>

        <select id="band">
            <option value="title">Title</option>
            <option value="detail">Detail</option>
            <option value="pageHeader">Page Header</option>
            <option value="pageFooter">Page Footer</option>
        </select>

        <button onclick="saveRegions()">Save Changes</button>

        <script>
            const imageUrl = "/image/{file_id}";
            const fileId = "{file_id}";
        </script>

        {get_edit_canvas_script()}
    </body>
    </html>
    """

@app.get("/regions/{file_id}")
def get_regions(file_id: str):
    import json

    path = os.path.join(IMAGE_DIR, file_id, "metadata.json")

    if not os.path.exists(path):
        return []

    with open(path) as f:
        return json.load(f)


@app.delete("/delete-region/{file_id}/{filename}")
def delete_region(file_id: str, filename: str):
    folder = os.path.join(IMAGE_DIR, file_id)
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




def group_by_band(components):
    bands = {}

    for item in components:
        band = item["band"]
        bands.setdefault(band, []).append(item["jrxml"])

    return bands

# def insert_into_band(jrxml, band_name, content_list):
#     import re

#     content = "\n".join(content_list)

#     replacement = f"""
#     <{band_name}>
#         <band height="200">
#             {content}
#         </band>
#     </{band_name}>
#     """

#     pattern = f"<{band_name}>.*?</{band_name}>"
#     return re.sub(pattern, replacement, jrxml, flags=re.DOTALL)

import re

def insert_into_band(jrxml, band_name, content_list):
    content = "\n".join(content_list)

    # Pattern to find band inside the section
    pattern = f"(<{band_name}>\\s*<band[^>]*>)(.*?)(</band>\\s*</{band_name}>)"

    replacement = f"\\1\n{content}\n\\3"

    return re.sub(pattern, replacement, jrxml, flags=re.DOTALL)


def apply_y_positions(content_list):
    updated = []
    y = 0

    for item in content_list:
        new_item = re.sub(r'y="0"', f'y="{y}"', item)
        updated.append(new_item)
        y += 50  # spacing

    return updated

@app.get("/generate-final-jrxml/{file_id}")
def generate_final_jrxml(file_id: str):
    import json, os

    # Paths
    folder = os.path.join(IMAGE_DIR, file_id)
    components_path = os.path.join(folder, "jrxml_components.json")
    template_path = "templates/Blank_A4_Report.jrxml"

    # Load files
    with open(components_path) as f:
        components = json.load(f)

    with open(template_path) as f:
        base_jrxml = f.read()

    # Group by band
    bands = group_by_band(components)

    # Insert into template
    # for band, content_list in bands.items():
    #     base_jrxml = insert_into_band(base_jrxml, band, content_list)

    for band, content_list in bands.items():
        content_list = apply_y_positions(content_list)
        base_jrxml = insert_into_band(base_jrxml, band, content_list)

    # Save final file
    output_path = os.path.join(folder, "final_report.jrxml")

    with open(output_path, "w") as f:
        f.write(base_jrxml)

    return {"status": "generated", "file": output_path}