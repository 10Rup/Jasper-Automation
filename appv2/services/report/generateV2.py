# services/report/generate.py

import anthropic
import pathlib
import base64


# ─── Build session context (called ONCE per report) ───────────────────────────

def build_session_context(fields: dict, config: dict) -> tuple[str, list]:
    """
    Returns (system_prompt, initial_history).
    Claude uses a proper system prompt — no need to fake it as a user turn.
    """
    system_prompt = f"""You are a JasperReports JRXML expert. Apply these rules to every band I send.

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
- Output raw XML only — no explanation, no code fences
"""

    # Seed history with one assistant turn so Claude knows the tone expected
    initial_history = [
        {
            "role": "assistant",
            "content": "Understood. Send each band name with its image and I will return only the raw JRXML for that band."
        }
    ]

    return system_prompt, initial_history


# ─── Single band call ─────────────────────────────────────────────────────────

def img_code(
    band: str,
    img_path: str,
    history: list,
    client: anthropic.Anthropic,
    system_prompt: str,
    model: str = "claude-opus-4-5",
    max_tokens: int = 4096,
) -> tuple[str, list]:
    """
    Generates JRXML for one band using Claude.
    Returns (xml_string, updated_history).
    Thread the same history list through all calls.
    """
    img_bytes = pathlib.Path(img_path).read_bytes()
    b64_img   = base64.standard_b64encode(img_bytes).decode("utf-8")
    mime      = "image/png" if img_path.lower().endswith(".png") else "image/jpeg"

    user_message = {
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": b64_img,
                },
            },
            {
                "type": "text",
                "text": f"Generate JRXML for <{band}>."
            },
        ],
    }

    messages = history + [user_message]

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=messages,
    )

    xml = response.content[0].text.strip()
    xml = xml.replace("```xml ", "").replace("```", "").strip()

    # Append both turns so next band call has full context
    updated_history = messages + [
        {
            "role": "assistant",
            "content": xml
        }
    ]

    return xml, updated_history


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def generateReport(
    band_image_map: dict,
    fields: dict,
    config: dict,
    api_key: str,
    model: str = "claude-opus-4-5",
) -> dict:
    """
    band_image_map: {"title": "/abs/path/title.png", "detail": "...", ...}
    Returns:        {"title": "<title>...</title>", "detail": "...", ...}
    """
    client = anthropic.Anthropic(api_key=api_key)
    system_prompt, history = build_session_context(fields, config)
    results = {}

    for band, img_path in band_image_map.items():
        print(f"Processing band: {band} with image {img_path}")
        xml, history = img_code(
            band, img_path, history, client, system_prompt, model
        )
        results[band] = xml
        print(f"✓ {band} done ({len(xml)} chars)")

    return results