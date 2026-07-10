# services/report/generate.py

import anthropic
import pathlib
import base64

from .cleanXml import clean_jrxml_response


# ─── Build session context (called ONCE per report) ───────────────────────────

def build_session_context(fields: dict, config: dict) -> tuple[str, list]:
    """
    Returns (system_prompt, initial_history).
    Claude uses a proper system prompt — no need to fake it as a user turn.
    """
    system_prompt = f"""
        You are a JasperReports expert.

        A. Use the following reference JRXML or xml code as a STYLE GUIDE only, Do NOT copy blindly. Adapt based on the image.
            Example Output:
                <band-name>
                    <band height="125" splitType="Stretch">
                        <textField isStretchWithOverflow="true" isBlankWhenNull="true">
                            <reportElement x="80" y="15" width="141" height="51" uuid="7c4acc13-1103-42c2-8a37-35c6f9d1314d"/>
                            <box>
                                <topPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                                <leftPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                                <bottomPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                                <rightPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                            </box>
                            <textElement textAlignment="Center" verticalAlignment="Middle"/>
                            <textFieldExpression><![CDATA["Text Field"]]></textFieldExpression>
                        </textField>
                    </band>
                </band-name>

        --------------------------------------------------
        B. AVAILABLE DATA FIELDS (VERY IMPORTANT):
            {fields}
            FIELD USAGE RULES:
            1. If any label in the image represents dynamic data (marks, totals, values, numbers), you MUST use <textField>
            2. Use this format strictly:
                <textField>
                    <reportElement x="" y="" width="" height=""/>
                    <box><pen lineWidth="1.0" lineColor="#000000"/></box>
                    <textElement textAlignment="Center" verticalAlignment="Middle">
                        <font/>
                    </textElement>
                    <textFieldExpression><![CDATA[$F{{FIELD_NAME}}]]></textFieldExpression>
                </textField>

            3. Match labels with fields intelligently:
            - "TOTAL THEO MARKS" → TOTAL_THEO_MARKS
            - "TOTAL THEO OBTAINED" → TOTAL_THEO_OBT_MARKS

            4. If no matching field is found → use <staticText>
                
        --------------------------------------------------

        C. Now analyze the image and generate JRXML for <band-name>.

            Mandatory Rules:
            1. Use <staticText> for labels/headings
            2. Use <textField> for dynamic values (based on fields above)
            3. Proper (x, y, width, height)
            4. Use <box> only if required and use following format example:-
                <box>
                    <topPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                    <leftPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                    <bottomPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                    <rightPen lineWidth="1.0" lineStyle="Solid" lineColor="#000000"/>
                </box>

            5. STRICT font hierarchy:
                <textElement><font/></textElement>
            6. textAlignment="Center", verticalAlignment="Middle"
            7. Extract exact text
            8. NO UUID
            9. NO comments
            10. NO markdown
            11. CRITICAL STRUCTURE RULE:
                <band-name>
                    <band height="AUTO">
                        ...YOUR CONTENT...
                    </band>
                </band-name>

                - NEVER skip <band>
                - NEVER omit <band>
                - NEVER return only inner elements
                - Output is INVALID if <band> is missing
                - Always include height attribute in <band>
                - Use a reasonable height based on content (e.g., 50–200)
                - Use font size to 10 by default else increase or decrease according to requirement.

            12. Keep layout within {config.get('pagesize')} bounds (Strickly).

            13. DO NOT use:
                - <text value="text" />
                - textAdjust
                - textExpression
                - forecolor inside <font/> tag
                - topIndent
                - textFieldExpression with staticText



            14. If Image or signature is present inside the report image use following format, 
            Example:-
                <image hAlign="Center" vAlign="Middle" onErrorType="Blank">
                    <reportElement x="390" y="10" width="140" height="30" uuid="7426c6e3-4bb6-416d-8e66-a9cd22df6de6"/>
                    <imageExpression><![CDATA["Image_path"]]></imageExpression>
                </image>

            15. If  "forecolor" is required then use following format as example :-
                <reportElement x="10" y="105" width="545" height="15" forecolor="#350EE6"/>
        --------------------------------------------------

        
        """
    # {f"Additional instructions: {extra}" if extra else ""}    
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
        xml = clean_jrxml_response(xml)
        results[band] = xml
        print(f"✓ {band} done ({len(xml)} chars)")

    return results



