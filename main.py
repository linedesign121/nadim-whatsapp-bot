import os
import requests
import datetime
from fastapi import FastAPI, Request, Response
from apscheduler.schedulers.background import BackgroundScheduler
from google import genai

app = FastAPI()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "nadim_secure_token_123")
MY_PHONE_NUMBER = os.getenv("MY_PHONE_NUMBER")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def send_whatsapp_msg(to_number: str, text: str):
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
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
        "text": {"body": text}
    }
    requests.post(url, json=payload, headers=headers)

def morning_routine():
    msg = (
        "☀️ صباح الخير سيدي نديم\n\n"
        "📍 عمان اليوم: الطقس معتدل ومناسب.\n"
        "☕ نبدأ الصباح بكوب ماء، والمشروب المفضل، وتذكير السيجارة الأولى.\n\n"
        "🎯 رقم اليوم وهدف الشهر قيد المتابعة.\n"
        "جاهز ننطلق بمهام اليوم؟"
    )
    send_whatsapp_msg(MY_PHONE_NUMBER, msg)

scheduler = BackgroundScheduler(timezone="Asia/Amman")
scheduler.add_job(morning_routine, 'cron', hour=7, minute=0)
scheduler.start()

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)

@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            message = entry["messages"][0]
            from_number = message["from"]
            user_text = message.get("text", {}).get("body", "")

            if "وضع المدير" in user_text:
                reply = (
                    "🏛️ وضع المدير (CEO Mode) مفعل:\n"
                    "• التركيز الفوري: حسم عروض الصفقات المعلقة.\n"
                    "• ممنوع اليوم: التشتت أو التعديلات غير المدفوعة.\n"
                    "• أكبر خطر: تأخر تحصيل الدفعات."
                )
            else:
                prompt = (
                    "أنت المساعد التنفيذي والشخصي لسيدي نديم (NADIM AI). "
                    "خاطبه بـ 'سيدي نديم'. التزم بالقرارات العملية والدعم المباشر والشخصي وفق التعليمات المعتمدة.\n"
                    f"رسالة نديم: {user_text}"
                )
                res = ai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                reply = res.text

            send_whatsapp_msg(from_number, reply)
    except Exception:
        pass

    return {"status": "success"}

@app.get("/")
def health_check():
    return {"status": "NADIM AI is running on WhatsApp 24/7"}
