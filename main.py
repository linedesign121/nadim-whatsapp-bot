import os
import requests
from fastapi import FastAPI, Request, Response

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_secret_token_123")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

processed_messages = set()

def get_gemini_reply(user_message: str) -> str:
    if not GEMINI_API_KEY:
        return "المعذرة سيدي، مفتاح Gemini غير معرف."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": user_message}]
        }],
        "systemInstruction": {
            "parts": [{"text": "أنت المساعد الشخصي لنديم. أجب بلهجة أردنية مهذبة، ذكية ومختصرة جداً."}]
        }
    }

    try:
        # رفع مهلة الانتظار لـ 25 ثانية لتفادي الـ Timeout
        res = requests.post(url, headers=headers, json=payload, timeout=25)
        data = res.json()
        if res.status_code == 200:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            print(f"Gemini API Error: {res.status_code} - {data}")
            return "أهلاً بك سيدي! كيف بقدر أساعدك اليوم؟"
    except Exception as e:
        print(f"Gemini Request Exception: {e}")
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
