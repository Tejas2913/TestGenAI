import os
import google.generativeai as genai

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is missing.")

genai.configure(api_key=API_KEY)

for model in genai.list_models():
    if "generateContent" in model.supported_generation_methods:
        print(model.name)