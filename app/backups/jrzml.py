import pdfplumber
import requests


def extract_pdf_text(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text


def clean_text(text):
    lines = text.split("\n")
    paragraphs = []
    buffer = ""

    for line in lines:
        if line.strip() == "":
            if buffer:
                paragraphs.append(buffer.strip())
                buffer = ""
        else:
            buffer += " " + line.strip()

    if buffer:
        paragraphs.append(buffer.strip())

    return paragraphs


def generate_prompt(paragraphs):
    content = "\n\n".join(paragraphs)

    return f"""
You are a JasperReports expert.

Your task is to convert structured text content into a clean, professional JRXML report template.

STRICT REQUIREMENTS:
1. Output ONLY valid JRXML XML.
2. Do NOT include explanations.
3. Use <jasperReport>, <title>, <detail>.
4. Each paragraph = ONE <staticText>.
5. Proper vertical spacing (no overlap).
6. Width ~450, height ~20–40.
7. Title should be larger font.

INPUT CONTENT:
{content}
"""


def generate_jrxml_ollama(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json()["response"]


# Run pipeline
pdf_text = extract_pdf_text("sample1.pdf")
paragraphs = clean_text(pdf_text)
prompt = generate_prompt(paragraphs)

jrxml = generate_jrxml_ollama(prompt)

with open("final_output.jrxml", "w", encoding="utf-8") as f:
    f.write(jrxml)

print("JRXML generated successfully!")