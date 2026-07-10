# services/report/generate.py

from google import genai
from google.genai import types
from PIL import Image
import pathlib


# ─── Build session context (called ONCE per report) ───────────────────────────

def build_session_context(fields: dict, config: dict) -> list[types.Content]:
    """
    Returns the initial conversation history with all rules baked in.
    Pass this to every img_code() call — never rebuild it.
    """
    system_text = f"""You are a JasperReports JRXML expert. Apply these rules to every band I send.

AVAILABLE FIELDS:
{fields}

PAGE CONFIG: {config.get('pagesize')}

=== RULES (apply to all bands) ===
ELEMENTS:
- <staticText>  → labels / headings
- <textField>   → dynamic values using $F{{FIELD_NAME}}
- Match intelligently: "TOTAL THEO MARKS" → TOTAL_THEO_MARKS; no match → <staticText>

STRUCTURE (mandatory):
<BAND_TAG>
  <band height="AUTO">
    ...content...
  </band>
</BAND_TAG>
- Never omit <band>. Always include height (50–200, auto-fit content).

FORMATTING:
- x/y/width/height must stay within page bounds
- font size 10 default; adjust per visual weight
- textAlignment="Center" verticalAlignment="Middle"
- <box> only when borders needed:
  <box>
    <topPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
    <leftPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
    <bottomPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
    <rightPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
  </box>
- Font hierarchy: <textElement><font/></textElement>
- Forecolor on reportElement: <reportElement ... forecolor="#350EE6"/>
- Images: <image hAlign="Center" vAlign="Middle" onErrorType="Blank">
    <reportElement .../>
    <imageExpression><![CDATA["path"]]></imageExpression>
  </image>

STRICT DON'Ts:
- No UUID, no comments, no markdown
- No <text value="..."/>, textAdjust, textExpression
- No forecolor inside <font/>
- No textFieldExpression inside staticText
"""

    return [
        types.Content(
            role="user",
            parts=[types.Part(text=system_text)]
        ),
        types.Content(
            role="model",
            parts=[types.Part(text="Understood. Send each band with its name and image.")]
        ),
    ]


# ─── Single band call ─────────────────────────────────────────────────────────

def img_code(
    band: str,
    img_path: str,
    history: list[types.Content],
    client: genai.Client,
    model: str = "gemini-3-flash-preview" #"gemini-2.0-flash"
) -> tuple[str, list[types.Content]]:
    """
    Generates JRXML for one band.
    Returns (xml_string, updated_history).
    Thread the same history list through all calls.
    """
    # Load image as bytes — new SDK uses inline_data
    img_bytes = pathlib.Path(img_path).read_bytes()
    mime = "image/png" if img_path.lower().endswith(".png") else "image/jpeg"

    user_content = types.Content(
        role="user",
        parts=[
            types.Part(text=f"Generate JRXML for <{band}>. Image attached."),
            types.Part(
                inline_data=types.Blob(mime_type=mime, data=img_bytes)
            ),
        ]
    )

    # Full conversation: history + new turn
    contents = history + [user_content]

    response = client.models.generate_content(
        model=model,
        contents=contents,
    )

    xml = response.text.strip()

    # Append both turns to history for continuity
    updated_history = contents + [
        types.Content(
            role="model",
            parts=[types.Part(text=xml)]
        )
    ]

    return xml, updated_history


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def generateReport(
    band_image_map: dict,
    fields: dict,
    config: dict,
    api_key: str,
    model: str = "gemini-2.0-flash"
) -> dict:
    """
    band_image_map: {"title": "/abs/path/title.png", "detail": "/abs/path/detail.png", ...}
    Returns:        {"title": "<title>...</title>", "detail": "...", ...}
    """
    client = genai.Client(api_key=api_key)
    history = build_session_context(fields, config)
    results = {}

    for band, img_path in band_image_map.items():
        print(f"Processing band: {band} with image {img_path}")
        xml, history = img_code(band, img_path, history, client, model)
        results[band] = xml
        print(f"✓ {band} generated ({len(xml)} chars)")

    return results