import os
import requests
from fastapi import FastAPI, Request, Response

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_secret_token_123")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

processed_messages = set()
chat_history = []
ACTIVE_MODEL = None

def get_best_available_model() -> str:
    """سحب الموديل الفعال والنشط تلقائياً من سيرفر Groq عند بدء التشغيل"""
    global ACTIVE_MODEL
    if ACTIVE_MODEL:
        return ACTIVE_MODEL

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        res = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json().get("data", [])
            # اختيار أول نموذج محادثة نصي نشط وتخطي نماذج الصوت والحماية
            for item in data:
                m_id = item.get("id", "")
                if not any(x in m_id for x in ["whisper", "guard", "vision"]):
                    ACTIVE_MODEL = m_id
                    print(f"--> Successfully loaded active Groq model: {ACTIVE_MODEL}")
                    return ACTIVE_MODEL
    except Exception as e:
        print(f"Error fetching models list: {e}")

    # بديل احتياطي عام
    ACTIVE_MODEL = "llama-3.1-8b-instant"
    return ACTIVE_MODEL

def get_ai_reply(user_message: str) -> str:
    global chat_history
    if not GROQ_API_KEY:
        return "المعذرة سيدي، مفتاح Groq غير معرف في Render."

    model_to_use = get_best_available_model()
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = {
        "role": "system",
        "content": (
            "أنت المساعد الشخصي لنديم (Nadeem). "
            "أجب دائماً بلهجة أردنية عفوية، ذكية، مهذبة ومختصرة. "
            "تذكر سياق الحديث ولا تكرر عبارات الترحيب العامة إلا إذا بدأ هو بالسلام."
        )
    }

    # بناء سياق الرسائل متضمناً الرسالة الحالية
    messages_payload = [system_prompt] + chat_history + [{"role": "user", "content": user_message}]

    payload = {
        "model": model_to_use,
        "messages": messages_payload,
        "temperature": 0.6
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        if res.status_code == 200:
            reply = res.json()["choices"][0]["message"]["content"]
            # حفظ المحادثة في الذاكرة فقط بعد نجاح الرد
            chat_history.append({"role": "user", "content": user_message})
            chat_history.append({"role": "assistant", "content": reply})
            if len(chat_history) > 10:
                chat_history = chat_history[-10:]
            return reply
        else:
            print(f"Groq API Error: {res.status_code} - {res.text}")
            return "معك يا نديم، بس صار ضغط خفيف عالشبكة. شو كنت بتحكي؟"
    except Exception as e:
        print(f"Request Exception: {e}")
        return "معك يا نديم، سامعك.. احكيلي."

def send_whatsapp_message(to_number: str, message_text: str):
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("Error: WhatsApp credentials missing.")
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
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
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
