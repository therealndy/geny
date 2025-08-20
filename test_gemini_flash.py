




import os
import google.genai as genai

# Read API key from environment to avoid committing secrets.
API_KEY = os.getenv("GENAI_API_KEY") or os.getenv("GOOGLE_API_KEY")
prompt = "Vad ser du runt dig just nu och hur mår du?"

if not API_KEY:
    print("[Gemini Flash test] Missing API key. Set GENAI_API_KEY or GOOGLE_API_KEY in your environment.")
    raise SystemExit(1)

try:
    client = genai.Client(api_key=API_KEY)
    print("Available models:")
    for model in client.models.list():
        print(model)
    # Example usage: create a chat and send a message
    chat = client.chats.create(model="models/gemini-2.5-flash")
    response = chat.send_message(prompt)
    print("Gemini Flash response:", getattr(response, "text", str(response)))
except Exception as e:
    print("[Gemini Flash error]", str(e))
