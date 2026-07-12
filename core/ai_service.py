import os
import time
from PIL import Image
import PyPDF2
from google import genai
from django.conf import settings

def extract_text_from_pdf(filepath):
    text = ""
    with open(filepath, "rb") as pdf:
        reader = PyPDF2.PdfReader(pdf)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text

def gemini_request(input_data):
    API_KEYS = [
        key for key in [
            os.environ.get("API_KEY_1"),
            os.environ.get("API_KEY_2")
        ] if key
    ]
    
    last_error = ""
    for key in API_KEYS:
        try:
            client = genai.Client(api_key=key)
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=[
                            input_data,
                            """
You are an AI Medical Prescription Checker.

Read this prescription.

Return:

CLEAN PRESCRIPTION:

PATIENT DETAILS
Name:
Age:
Gender:
Date:

DOCTOR DETAILS
Doctor Name:
Hospital / Clinic:

MEDICINES PRESCRIBED

DOSAGE / INSTRUCTIONS

AI ANALYSIS:

Include:
- Purpose of medicines
- Important warnings
- Possible side effects
- Patient advice

Rules:
- Correct spelling mistakes.
- Remove unwanted symbols.
- Do not use * symbols.
"""
                        ]
                    )
                    return response.text
                except Exception as e:
                    last_error = str(e)
                    if "503" in last_error:
                        time.sleep(10)
                        continue
                    else:
                        break
        except Exception as e:
            last_error = str(e)
            continue
            
    return "Gemini Error: " + last_error
