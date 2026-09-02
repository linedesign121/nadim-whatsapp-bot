import os
import datetime
import requests
from fastapi import FastAPI, Request, Response
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "nadim_secure_token_123")
MY_PHONE_NUMBER = os.getenv("MY_PHONE_NUMBER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def get_gemini_reply(user_message: str) -> str:
    if not GEMINI_API_KEY:
        print("CRITICAL: GEMINI_API_KEY is not set!")
        return "أهلاً بك! تم استلام رسالتك."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY.strip()}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"أنت المساعد الشخصي لنديم. أجب بلهجة أردنية مهذبة، ذكية، ومختصرة جداً:\n{user_message}"
                    }
                ]
            }
        ]
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=40)
        data = res.json()
        print(f"حالة Gemini - الحالة: {res.status_code}")

        if res.status_code == 200 and "candidates" in data:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            err_msg = data.get("error", {}).get("message", "خطأ غير معروف")
            print(f"Gemini Error: {err_msg}")
            return f"عذراً سيدي، خطأ من الخادم: {err_msg}"
    except requests.exceptions.Timeout:
        return "المعذرة سيدي، استغرقت الاستجابة وقتاً طويلاً، يرجى إعادة الإرسال."
    except Exception as e:
        print(f"Gemini Exception: {e}")
        return f"عذراً، خطأ في الاتصال: {e}"


def send_whatsapp_message(to: str, text: str):
    if not PHONE_NUMBER_ID or not WHATSAPP_TOKEN:
        print("خطأ: رمز WHATSAPP_TOKEN أو معرف رقم الهاتف مفقود!")
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
        res = requests.post(url, json=payload, headers=headers, timeout=20)
        print(f"حالة واجهة برمجة تطبيقات واتساب: {res.status_code}")
    except Exception as e:
        print(f"خطأ في إرسال رسالة واتساب: {e}")


def morning_routine():
    msg = (
        "صباح الخير سيدي نديم ☀️\n\n"
        "☕ عمان اليوم: الطقس معتدل ومناسب.\n"
        "ابدأ الصباح بكوب، والمشروب المفضل، وتذكير التجارة الأولى 🥛\n\n"
        "🎯 رقم اليوم وهدف الشهر قيد المتابعة.\n"
        "جاهز ننطلق بمهام اليوم؟"
    )
    if MY_PHONE_NUMBER:
        send_whatsapp_message(MY_PHONE_NUMBER, msg)


scheduler = BackgroundScheduler(timezone="Asia/Amman")
scheduler.add_job(morning_routine, "cron", hour=7, minute=0)
scheduler.start()


@app.get("/")
def home():
    return {"حالة": "البوت قيد التشغيل"}


@app.get("/webhook")
def verify_webhook(request: Request):
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="محرّم", status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request):
    try:
        data = await request.json()
        entry = data.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if messages:
            msg_obj = messages[0]
            sender = msg_obj.get("from")
            text = msg_obj.get("text", {}).get("body", "")

            if text:
                bot_reply = get_gemini_reply(text)
                send_whatsapp_message(sender, bot_reply)
    except Exception as e:
        print(f"خطأ في معالجة الويب هوك: {e}")

    return {"حالة": "نعم"}
