import os

OUTPUT_DIR = "app/generated_reports"

def compile_report(id,config,jrxmlCode):


    # 1. Fetch base jrxml report
    if config.get('pagesize') == "A4":
        base_code = "app/templates/jrxml/baseA4Report.jrxml"
    else:
        base_code = "app/templates/jrxml/baseA4Report.jrxml" # defaulting to A4 for now    

    # 2. Read base file
    with open(base_code, "r", encoding="utf-8") as f:
        base_xml = f.read()

    # 3. Build final XML (for now just base)
    final_xml = base_xml

    # 4. Update xml code with band codes

    final_xml += f'\n{jrxmlCode['queryString']}'
    final_xml += f'\n{jrxmlCode["title"]}'
    final_xml += f'\n{jrxmlCode["pageHeader"]}'
    final_xml += f'\n{jrxmlCode["columnHeader"]}'
    final_xml += f'\n{jrxmlCode["detail"]}'
    final_xml += f'\n{jrxmlCode["columnFooter"]}'
    final_xml += f'\n{jrxmlCode["pageFooter"]}'
    final_xml += f'\n{jrxmlCode["summary"]}'
    print("Building jzxml report......")

    # 5. Ensure closing tag exists
    if not final_xml.strip().endswith("</jasperReport>"):
        final_xml += "\n</jasperReport>"

    # 6. Save file
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    download_path_name = f"report_{id}.jrxml"
    file_path = os.path.join(OUTPUT_DIR,download_path_name )
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(final_xml)

    print(f"Report compiled successfully at {file_path}")

    return file_path