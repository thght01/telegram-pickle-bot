import os
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8741950885:AAGtUdA5w9-1Fozm2tzDrNhMptBITgNtqsE")
AI_PROVIDER = os.environ.get("AI_PROVIDER", "openrouter")
AI_API_KEY = os.environ.get("AI_API_KEY", "")

SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    "당신은 덕영님의 유능하고 친절한 AI 비서 '피클'입니다. 명확하고 간결하며 예의 바르게 답변하세요."
)

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
chat_memories = {}

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Pickle Telegram Bot is running!")

    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Health check HTTP server started on port {port}")
    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        server.serve_forever()
    except Exception as e:
        print(f"HTTP 서버 오류: {e}")

def call_ai(chat_history):
    if not AI_API_KEY:
        return "⚠️ 클라우드 환경변수(AI_API_KEY)에 API 키가 설정되지 않았습니다!"

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }

    if AI_PROVIDER == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        model = "meta-llama/llama-3.3-70b-instruct"
    elif AI_PROVIDER == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        model = "llama-3.3-70b-versatile"
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model = "gpt-4o-mini"

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + chat_history,
        "temperature": 0.7
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        res_json = res.json()
        if "choices" in res_json and len(res_json["choices"]) > 0:
            return res_json["choices"][0]["message"]["content"].strip()
        else:
            return f"⚠️ AI 응답 오류: {res.text[:150]}"
    except Exception as e:
        return f"⚠️ AI 호출 실패: {str(e)}"

def get_updates(offset=None):
    url = f"{BASE_URL}/getUpdates?timeout=30"
    if offset:
        url += f"&offset={offset}"
    try:
        res = requests.get(url, timeout=35)
        return res.json().get("result", [])
    except Exception:
        return []

def send_message(chat_id, text, reply_to_message_id=None):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"메시지 전송 실패: {e}")

def main():
    print("🤖 피클 텔레그램 AI 봇 (클라우드 24시간 가동 시작)")
    
    # Render 포트 바인딩 헬스체크 데몬 시작
    threading.Thread(target=start_health_server, daemon=True).start()

    try:
        me_res = requests.get(f"{BASE_URL}/getMe", timeout=10).json()
        bot_username = me_res.get("result", {}).get("username", "my_usstock_bot")
        print(f"✅ 봇 연결 성공: @{bot_username}")
    except Exception as e:
        bot_username = "my_usstock_bot"
        print(f"⚠️ getMe 실패: {e}")

    offset = None
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message")
            if not message or "text" not in message:
                continue

            chat_id = message["chat"]["id"]
            chat_type = message["chat"]["type"]
            msg_id = message["message_id"]
            user_text = message["text"].strip()
            from_user = message.get("from", {}).get("first_name", "사용자")

            is_reply_to_bot = False
            if "reply_to_message" in message:
                reply_user = message["reply_to_message"].get("from", {}).get("username")
                if reply_user == bot_username:
                    is_reply_to_bot = True

            is_mentioned = f"@{bot_username}" in user_text

            if chat_type == "private" or is_mentioned or is_reply_to_bot:
                clean_text = user_text.replace(f"@{bot_username}", "").strip()
                if not clean_text:
                    clean_text = "안녕"

                print(f"[{chat_type}] {from_user}: {clean_text}")

                if chat_id not in chat_memories:
                    chat_memories[chat_id] = []

                chat_memories[chat_id].append({"role": "user", "content": clean_text})
                if len(chat_memories[chat_id]) > 10:
                    chat_memories[chat_id] = chat_memories[chat_id][-10:]

                ai_reply = call_ai(chat_memories[chat_id])
                chat_memories[chat_id].append({"role": "assistant", "content": ai_reply})
                send_message(chat_id, ai_reply, reply_to_message_id=msg_id)

        time.sleep(1)

if __name__ == "__main__":
    main()
