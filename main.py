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
    "당신은 덕영님의 유능하고 친절한 AI 비서 '피클'입니다. 텔레그램 메신저 특성에 맞추어 2~4문장으로 핵심만 명확하고 간결하며 예의 바르게 답변하세요. 불필요하게 긴 논문식 답변은 피하세요."
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
        model = os.environ.get("AI_MODEL", "qwen/qwen3.8-27b")
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model = "gpt-4o-mini"

    # 최근 4개 턴만 유지하고 각 메시지 길이 500자로 압축 (Groq 8000 TPM 무료 한도 완벽 방어)
    safe_history = []
    for m in chat_history[-4:]:
        safe_history.append({"role": m["role"], "content": m["content"][:500]})

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + safe_history,
        "temperature": 0.7,
        "max_tokens": 600
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        res_json = res.json()
        if res.status_code == 200 and "choices" in res_json and len(res_json["choices"]) > 0:
            return res_json["choices"][0]["message"]["content"].strip()
        
        # 413 TPM 한도 오류 발생 시 직전 질문 1개만으로 즉시 자동 복구 재시도
        if res.status_code == 413 or "too large" in res.text.lower():
            last_msg = safe_history[-1]["content"] if safe_history else "안녕"
            retry_payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "핵심만 2문장으로 간결하게 답하세요."},
                    {"role": "user", "content": last_msg[:300]}
                ],
                "max_tokens": 300
            }
            retry_res = requests.post(url, headers=headers, json=retry_payload, timeout=15)
            retry_json = retry_res.json()
            if retry_res.status_code == 200 and "choices" in retry_json and len(retry_json["choices"]) > 0:
                return retry_json["choices"][0]["message"]["content"].strip()

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

            from_is_bot = message.get("from", {}).get("is_bot", False)
            is_reply_to_bot = False
            if "reply_to_message" in message:
                reply_user = message["reply_to_message"].get("from", {}).get("username")
                if reply_user == bot_username:
                    is_reply_to_bot = True

            is_mentioned = (f"@{bot_username}".lower() in user_text.lower()) or ("피클" in user_text)
            is_call_buoy = user_text.startswith("부이야") or user_text.startswith("부이 ") or ("@sondondo_bot" in user_text)

            should_respond = False
            if from_is_bot:
                # 다른 봇(부이 등)의 메시지: 피클을 직접 부르거나 답장했을 때만 응답 (무한루프 방지)
                if is_mentioned or is_reply_to_bot:
                    should_respond = True
            else:
                # 사용자(덕영님)의 메시지:
                # 1) 개인방
                # 2) '피클' 호칭 또는 @멘션
                # 3) 피클 메시지에 답장
                # 4) 그룹방에서 부이만 단독으로 부른 게 아닌 모든 일반 발화
                if chat_type == "private" or is_mentioned or is_reply_to_bot or not is_call_buoy:
                    should_respond = True

            if should_respond:
                clean_text = user_text.replace(f"@{bot_username}", "").strip()
                if not clean_text:
                    clean_text = user_text.strip()

                print(f"[{chat_type}] {from_user}: {clean_text}", flush=True)

                if chat_id not in chat_memories:
                    chat_memories[chat_id] = []

                chat_memories[chat_id].append({"role": "user", "content": clean_text})
                if len(chat_memories[chat_id]) > 10:
                    chat_memories[chat_id] = chat_memories[chat_id][-10:]

                ai_reply = call_ai(chat_memories[chat_id])
                print(f"🤖 [피클 응답]: {ai_reply}", flush=True)
                if not ai_reply.startswith("⚠️"):
                    chat_memories[chat_id].append({"role": "assistant", "content": ai_reply})
                else:
                    # 오류 발생 시 이전 메모리를 초기화하여 다음 요청이 즉시 정상 복구되도록 조치
                    chat_memories[chat_id] = []
                send_message(chat_id, ai_reply, reply_to_message_id=msg_id)

        time.sleep(1)

if __name__ == "__main__":
    main()
