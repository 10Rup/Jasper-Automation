from PIL import Image
from google import genai


def img_code(band,fields,config,imgPath, apiKey):

    prompt = f"""
        You are a JasperReports expert.

        A. Use the following reference JRXML or xml code as a STYLE GUIDE only, Do NOT copy blindly. Adapt based on the image.
            Example Output:
                <{band}>
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
                </{band}>

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

        C. Now analyze the image and generate JRXML for <{band}>.

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
                <{band}>
                    <band height="AUTO">
                        ...YOUR CONTENT...
                    </band>
                </{band}>

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
                - forecolor inside <font/> tag
                - topIndent



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
    
    # Load the image
    img = Image.open(imgPath)
    
    
    # 🔐 Gemini Setup
    client = genai.Client(api_key=apiKey)
    model = "gemini-3-flash-preview"
    response = client.models.generate_content(
        model=model, # or "gemini-1.5-flash"
        contents=[prompt, img]
    )

    code = response.text.strip()
    return code
