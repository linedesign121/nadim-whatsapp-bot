import os
import time
import requests
from fastapi import FastAPI, Request, Response
from google import genai

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_secret_token_123")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Error initializing Gemini Client: {e}")

processed_messages = set()

def get_gemini_reply(user_message: str) -> str:
    if not client:
        return "المعذرة سيدي، مفتاح الذكاء الاصطناعي غير معرف."

    # محاولة الإرسال حتى 3 مرات لتجاوز أي ضغط لحظي (503)
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=user_message,
                config={
                    "system_instruction": "أنت المساعد الشخصي لنديم. أجب بلهجة أردنية مهذبة، ذكية، ومختصرة جداً."
                }
            )
            if response.text:
                return response.text
        except Exception as e:
            print(f"Gemini API Error (Attempt {attempt + 1}): {e}")
            time.sleep(1.5)

    return "أهلاً بك سيدي! كيف بقدر أساعدك اليوم؟"

def send_whatsapp_message(to_number: str, message_text: str):
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("Error: WHATSAPP_TOKEN or PHONE_NUMBER_ID missing.")
        return

    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message_text}
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"WhatsApp API Status: {res.status_code}")
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")

@app.get("/")
def home():
    return {"status": "running"}

@app.get("/webhook")
def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)

@app.post("/webhook")
async def handle_incoming_messages(request: Request):
    data = await request.json()

    try:
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return {"status": "no_message"}

        msg = messages[0]
        msg_id = msg.get("id")

        if msg_id in processed_messages:
            return {"status": "ignored_duplicate"}

        processed_messages.add(msg_id)
        if len(processed_messages) > 1000:
            processed_messages.clear()

        if msg.get("type") == "text":
            from_number = msg.get("from")
            body = msg.get("text", {}).get("body", "")

            bot_reply = get_gemini_reply(body)
            send_whatsapp_message(from_number, bot_reply)

    except Exception as e:
        print(f"Webhook processing error: {e}")

    return {"status": "ok"}
