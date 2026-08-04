import re
import html


def clean_jrxml_response(xml_content: str) -> str:

    # Remove markdown
    xml_content = xml_content.replace("xml", "")
    xml_content = xml_content.replace("```xml", "")
    xml_content = xml_content.replace("```", "")

    # Remove wrapping quotes
    xml_content = xml_content.strip()

    if xml_content.startswith('"') and xml_content.endswith('"'):
        xml_content = xml_content[1:-1]

    # Decode escaped characters
    xml_content = bytes(xml_content, "utf-8").decode("unicode_escape")

    # HTML decode if needed
    xml_content = html.unescape(xml_content)

    # Remove XML comments
    xml_content = re.sub(r"<!--.*?-->", "", xml_content, flags=re.DOTALL)

    # Remove extra blank lines
    xml_content = re.sub(r"\n\s*\n", "\n", xml_content)

    return xml_content.strip()


def clean_sql(sql):
    # Replace $P{} and $P!{}
    sql = re.sub(r"\$P!\{[^}]+\}", "'VALUE'", sql)
    sql = re.sub(r"\$P\{[^}]+\}", "'VALUE'", sql)
    return sql