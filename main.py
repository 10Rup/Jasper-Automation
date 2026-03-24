


import pdfplumber
from openai import OpenAI

client = OpenAI(api_key="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")


def extract_pdf_text(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text


def generate_jrxml_from_text(text):
    prompt = f"""
Convert the following content into a clean JasperReports JRXML template.

Requirements:
- Use proper bands (title, detail)
- Group paragraphs properly
- Use staticText for static content
- Maintain layout readability
- Avoid one-word elements

Content:
{text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    return response.choices[0].message.content


pdf_text = extract_pdf_text("sample1.pdf")
jrxml = generate_jrxml_from_text(pdf_text)

with open("ai_generated.jrxml", "w", encoding="utf-8") as f:
    f.write(jrxml)