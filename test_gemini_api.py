import google.generativeai as genai
import os

# Use environment variable or paste your API key below
API_KEY = os.getenv("GENAI_API_KEY") or "PASTE_YOUR_API_KEY_HERE"

if not API_KEY or API_KEY == "PASTE_YOUR_API_KEY_HERE":
    print("ERROR: Please set GENAI_API_KEY environment variable or paste your Gemini API key in the script.")
    exit(1)

try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    response = model.generate_content("Hello Gemini, are you working?")
    print("Gemini response:", response.text if hasattr(response, "text") else response)
except Exception as e:
    print("Gemini API error:", e)
