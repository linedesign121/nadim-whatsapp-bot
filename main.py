import os
import requests
from fastapi import FastAPI, Request, Response, BackgroundTasks
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "nadim_secure_token_123")
MY_PHONE_NUMBER = os.getenv("MY_PHONE_NUMBER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

processed_messages = set()

def get_gemini_reply(user_message: str) -> str:
    if not GEMINI_API_KEY:
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
        res = requests.post(url, json=payload, headers=headers, timeout=60)
        data = res.json()
        if res.status_code == 200 and "candidates" in data:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return "المعذرة سيدي، صار ضغط لحظي عالسيرفر، ثواني وراجعلك."
    except Exception:
        return "المعذرة سيدي، استغرقت الاستجابة وقتاً طويلاً، جرب تبعثلي كمان مرة."


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
        requests.post(url, json=payload, headers=headers, timeout=20)
    except Exception as e:
        print(f"خطأ في إرسال رسالة واتساب: {e}")


def handle_ai_response(sender: str, text: str):
    bot_reply = get_gemini_reply(text)
    send_whatsapp_message(sender, bot_reply)


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

            # التحقق من أن الرسالة لم تُعالج من قبل لمنع التكرار
            if msg_id and msg_id in processed_messages:
                return Response(content="OK", status_code=200)

            if msg_id:
                processed_messages.add(msg_id)
                if len(processed_messages) > 1000:
                    processed_messages.clear()

            if text:
                # الرد الفوري على واتساب وتشغيل المعالجة في الخلفية
                background_tasks.add_task(handle_ai_response, sender, text)

    except Exception as e:
        print(f"خطأ في معالجة الويب هوك: {e}")

    # إرجاع 200 فوراً خلال أجزاء من الثانية لمنع واتساب من إعادة الإرسال
    return Response(content="OK", status_code=200)
