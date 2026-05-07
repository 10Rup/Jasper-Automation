import pdfplumber

pdfpath = "app/templates/pdf/provitional_report_igu.pdf"

def readPdf(pdf_path):

    elements=[]
    with pdfplumber.open(pdf_path) as pdf:

        page = pdf.pages[0]

        words = page.extract_words()

        for w in words:
            elements.append({
                "text": w["text"],
                "x": round(w["x0"]),
                "y": round(w["top"]),
                "width": round(w["x1"] - w["x0"]),
                "height": round(w["bottom"] - w["top"])
            })

    
    return elements



# readPdf(pdfpath)

