import os
import requests
from fastapi import FastAPI, Request, Response, BackgroundTasks
from apscheduler.schedulers.background import BackgroundScheduler
from google import genai

app = FastAPI()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "nadim_secure_token_123")
MY_PHONE_NUMBER = os.getenv("MY_PHONE_NUMBER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = None
if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY.strip())

processed_messages = set()

def get_gemini_reply(user_message: str) -> str:
    if not client:
        return "المعذرة سيدي، مفتاح Gemini غير معرف."

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=user_message,
            config={
                "system_instruction": "أنت المساعد الشخصي لنديم. أجب بلهجة أردنية مهذبة، ذكية، ومختصرة جداً."
            }
        )
        return response.text if response.text else "أهلاً بك سيدي، كيف أساعدك؟"
    except Exception as e:
        print(f"Gemini API Error: {e}")
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash-lite",
                contents=user_message,
                config={
                    "system_instruction": "أنت المساعد الشخصي لنديم. أجب بلهجة أردنية مهذبة، ذكية ومختصرة."
                }
            )
            return response.text
        except Exception as e2:
            print(f"Fallback Error: {e2}")
            return "المعذرة سيدي، واجهت مشكلة اتصال مؤقتة، ثواني وبكون جاهز."


def send_whatsapp_message(to: str, text: str):
    if not PHONE_NUMBER_ID or not WHATSAPP_TOKEN:
        return

    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN.strip()}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    try:
        requests.post(url, json=payload, headers=headers, timeout=15)
    except Exception as e:
        print(f"WhatsApp Error: {e}")


def handle_incoming_message(sender: str, text: str):
    reply = get_gemini_reply(text)
    send_whatsapp_message(sender, reply)


def morning_routine():
    msg = (
        "صباح الخير سيدي نديم ☀️\n\n"
        "☕ عمان اليوم: الطقس معتدل ومناسب.\n"
        "ابدأ الصباح بكوب قهوتك المفضل ☕\n\n"
        "🎯 أهداف اليوم قيد المتابعة.\n"
        "جاهز ننطلق بمهام اليوم؟"
    )
    if MY_PHONE_NUMBER:
        send_whatsapp_message(MY_PHONE_NUMBER, msg)


scheduler = BackgroundScheduler(timezone="Asia/Amman")
scheduler.add_job(morning_routine, "cron", hour=7, minute=0)
scheduler.start()


@app.get("/")
def home():
    return {"status": "running"}


@app.get("/webhook")
def verify_webhook(request: Request):
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Forbidden", status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if messages:
            msg_obj = messages[0]
            msg_id = msg_obj.get("id")
            sender = msg_obj.get("from")
            text = msg_obj.get("text", {}).get("body", "")

            if msg_id and msg_id in processed_messages:
                return Response(content="OK", status_code=200)

            if msg_id:
                processed_messages.add(msg_id)
                if len(processed_messages) > 500:
                    processed_messages.clear()

            if text:
                background_tasks.add_task(handle_incoming_message, sender, text)

    except Exception as e:
        print(f"Webhook Error: {e}")

    return Response(content="OK", status_code=200)
