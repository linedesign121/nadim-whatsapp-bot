def get_gemini_reply(user_message: str) -> str:
    if not GEMINI_API_KEY:
        return "المعذرة سيدي، مفتاح Gemini غير معرف."

    models_to_try = [
        "gemini-2.5-flash-lite",
        "gemini-3.6-flash"
    ]

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
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
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            if res.status_code == 200:
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                print(f"Model {model_name} failed: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"Exception on {model_name}: {e}")

    return "أهلاً بك سيدي! كيف بقدر أساعدك اليوم؟"
