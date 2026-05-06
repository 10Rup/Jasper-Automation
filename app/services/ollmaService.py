import os
from dotenv import load_dotenv
import base64
from ollama import Client


def ollamaClient(prompt, image_path):

    client = Client(
        host="https://ollama.com",
        headers={
            'Authorization': 'Bearer ' + os.getenv('OLLAMA_API_KEY')
        }
    )
    MODEL="gpt-oss:120b"
    with open(image_path, "rb") as img_file:
        image_base64 = base64.b64encode(img_file.read()).decode("utf-8")

    response = client.chat(
        model=MODEL,
        messages=[
            {
                'role': 'system',
                'content': 'You are a JasperReports JRXML expert.'
            },
            {
                'role': 'user',
                'content': prompt,
                # 'images': [image_base64]
            }
        ]
    )

    xml_content = response['message']['content']

    xml_content = (
        xml_content
        .replace("```xml", "")
        .replace("```", "")
        .strip()
    )

    print(xml_content)

    return