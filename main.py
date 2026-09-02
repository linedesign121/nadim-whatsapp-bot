import os
import requests
from fastapi import FastAPI, Request, Response

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_secret_token_123")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

processed_messages = set()

def get_ai_reply(user_message: str) -> str:
    if not GROQ_API_KEY:
        return "المعذرة سيدي، مفتاح الذكاء الاصطناعي غير متوفر."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # النماذج النشطة والمعتمدة على Groq
    models = ["llama-3.3-70b-specdec", "llama-3.1-8b-instant"]

    for model_name in models:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "أنت المساعد الشخصي لنديم. أجب بلهجة أردنية مهذبة، ذكية، ومختصرة جداً."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.6
        }

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            else:
                print(f"Groq Model {model_name} Error: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"Groq Exception on {model_name}: {e}")

    return "أهلاً بك! كيف بقدر أساعدك اليوم؟"

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

            bot_reply = get_ai_reply(body)
            send_whatsapp_message(from_number, bot_reply)

    except Exception as e:
        print(f"Webhook error: {e}")

    return {"status": "ok"}
