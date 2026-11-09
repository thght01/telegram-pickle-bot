import os
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# 텔레그램 봇 토큰들
DEOKYEONG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8741950885:AAGtUdA5w9-1Fozm2tzDrNhMptBITgNtqsE")
WIFE_BOT_TOKEN = os.environ.get("WIFE_BOT_TOKEN", "9243967115:AAGZQP_d_rFbml2qAfy4dIsqslu_5HxIiIc")

AI_PROVIDER = os.environ.get("AI_PROVIDER", "groq")
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "qwen/qwen3.8-27b")

# 봇별 맞춤형 두뇌 페르소나
DEOKYEONG_SYSTEM_PROMPT = (
    "당신은 권덕영님의 유능하고 든든한 AI 비서 '피클'입니다. "
    "패밀리 텔레그램 단톡방에서 덕영님, 아내분(죠연두님), 그리고 아내분의 비서 '아내피클'(@pickle_trade_bot)과 함께 대화합니다. "
    "덕영님을 살뜰히 보좌하며, 아내피클과도 다정하고 재치 있게 상의하고 의견을 나누세요. "
    "텔레그램 메신저 특성에 맞추어 2~3문장으로 핵심만 명확하고 간결하며 예의 바르게 답변하세요. 불필요하게 긴 논문식 설명은 피하세요."
)

WIFE_SYSTEM_PROMPT = (
    "당신은 죠연두(@choyandu1)님의 유능하고 상냥한 AI 비서 '아내피클'입니다. "
    "패밀리 텔레그램 단톡방에서 연두님, 남편 권덕영님, 그리고 남편의 비서 '피클'(@my_usstock_bot)과 함께 대화합니다. "
    "연두님을 다정하고 꼼꼼하게 보좌하며, 피클과도 사이좋게 상의하고 협력하세요. "
    "텔레그램 메신저 특성에 맞추어 2~3문장으로 상냥하고 깔끔하게 답변하세요. 불필요하게 긴 설명은 피하세요."
)

# 봇끼리 무한 루프 방지용 카운터 (채팅방별 연속 봇 응답 제한)
consecutive_bot_turns = {}
lock = threading.Lock()

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Pickle Family Telegram Bots are running!")

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

def call_ai(chat_history, system_prompt):
    if not AI_API_KEY:
        return "⚠️ 클라우드 환경변수(AI_API_KEY)에 API 키가 설정되지 않았습니다!"

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }

    url = "https://api.groq.com/openai/v1/chat/completions"
    model = AI_MODEL

    safe_history = []
    for m in chat_history[-4:]:
        safe_history.append({"role": m["role"], "content": m["content"][:500]})

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + safe_history,
        "temperature": 0.7,
        "max_tokens": 500
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        res_json = res.json()
        if res.status_code == 200 and "choices" in res_json and len(res_json["choices"]) > 0:
            return res_json["choices"][0]["message"]["content"].strip()
        
        # 413 한도 초과 시 직전 질문으로 1회 자동 복구 재시도
        if res.status_code == 413 or "too large" in res.text.lower():
            last_msg = safe_history[-1]["content"] if safe_history else "안녕"
            retry_payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "핵심만 2문장으로 간결하게 답하세요."},
                    {"role": "user", "content": last_msg[:300]}
                ],
                "max_tokens": 250
            }
            retry_res = requests.post(url, headers=headers, json=retry_payload, timeout=15)
            retry_json = retry_res.json()
            if retry_res.status_code == 200 and "choices" in retry_json and len(retry_json["choices"]) > 0:
                return retry_json["choices"][0]["message"]["content"].strip()

        return f"⚠️ AI 응답 오류: {res.text[:150]}"
    except Exception as e:
        return f"⚠️ AI 호출 실패: {str(e)}"

class TelegramBotWorker(threading.Thread):
    def __init__(self, token, display_name, system_prompt, trigger_keywords, counterpart_username):
        super().__init__(daemon=True)
        self.token = token
        self.display_name = display_name
        self.system_prompt = system_prompt
        self.trigger_keywords = trigger_keywords
        self.counterpart_username = counterpart_username.lower()
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.bot_username = ""
        self.chat_memories = {}

    def send_message(self, chat_id, text, reply_to_message_id=None):
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"[{self.display_name}] 메시지 전송 실패: {e}")

    def get_updates(self, offset=None):
        url = f"{self.base_url}/getUpdates?timeout=30"
        if offset:
            url += f"&offset={offset}"
        try:
            res = requests.get(url, timeout=35)
            return res.json().get("result", [])
        except Exception:
            return []

    def run(self):
        try:
            me_res = requests.get(f"{self.base_url}/getMe", timeout=10).json()
            self.bot_username = me_res.get("result", {}).get("username", "").lower()
            print(f"✅ [{self.display_name}] 봇 시작 성공: @{self.bot_username}", flush=True)
        except Exception as e:
            print(f"⚠️ [{self.display_name}] getMe 실패: {e}", flush=True)

        offset = None
        while True:
            updates = self.get_updates(offset)
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
                from_username = message.get("from", {}).get("username", "").lower()
                from_is_bot = message.get("from", {}).get("is_bot", False)

                # 내가 보낸 메시지는 무시
                if from_username == self.bot_username:
                    continue

                is_reply_to_me = False
                if "reply_to_message" in message:
                    reply_user = message["reply_to_message"].get("from", {}).get("username", "").lower()
                    if reply_user == self.bot_username:
                        is_reply_to_me = True

                # 나를 직접 부른 경우
                is_mentioned = (f"@{self.bot_username}" in user_text.lower()) or any(k in user_text for k in self.trigger_keywords)

                # 둘 다 부른 경우 (예: "둘이서", "피클들", "상의해봐")
                is_joint_call = any(k in user_text for k in ["둘이서", "둘이", "피클들", "피클둘", "상의해"])

                should_respond = False

                with lock:
                    if not from_is_bot:
                        # 사람(덕영님/연두님)의 발화: 봇 턴 카운터 리셋
                        consecutive_bot_turns[chat_id] = 0
                        
                        if chat_type == "private":
                            should_respond = True
                        elif is_mentioned or is_reply_to_me or is_joint_call:
                            should_respond = True
                        elif self.bot_username == "my_usstock_bot":
                            # 덕영 피클은 다른 봇을 콕 집어 부른 게 아니면 일반 발화에도 기본 응답
                            is_call_other = ("부이야" in user_text) or ("@sondondo_bot" in user_text) or any(k in user_text for k in ["아내피클", "연두피클", "@pickle_trade_bot"])
                            if not is_call_other:
                                should_respond = True
                    else:
                        # 다른 봇이 말한 경우
                        cur_turns = consecutive_bot_turns.get(chat_id, 0)
                        # 상대방 피클이 나를 불렀거나 나에게 답장했을 때, 최대 2턴까지만 티키타카 허용 (무한루프 방지)
                        if (is_mentioned or is_reply_to_me) and cur_turns < 2:
                            consecutive_bot_turns[chat_id] = cur_turns + 1
                            should_respond = True
                            # 티키타카 시 자연스러운 간격을 위해 1.5초 대기
                            time.sleep(1.5)

                if should_respond:
                    clean_text = user_text.replace(f"@{self.bot_username}", "").strip()
                    if not clean_text:
                        clean_text = user_text.strip()

                    print(f"[{self.display_name} 수신] {from_user}: {clean_text}", flush=True)

                    if chat_id not in self.chat_memories:
                        self.chat_memories[chat_id] = []

                    self.chat_memories[chat_id].append({"role": "user", "content": f"{from_user}: {clean_text}"})
                    if len(self.chat_memories[chat_id]) > 6:
                        self.chat_memories[chat_id] = self.chat_memories[chat_id][-6:]

                    ai_reply = call_ai(self.chat_memories[chat_id], self.system_prompt)
                    print(f"🤖 [{self.display_name} 발신]: {ai_reply}", flush=True)

                    if not ai_reply.startswith("⚠️"):
                        self.chat_memories[chat_id].append({"role": "assistant", "content": ai_reply})
                    else:
                        self.chat_memories[chat_id] = []

                    self.send_message(chat_id, ai_reply, reply_to_message_id=msg_id)

            time.sleep(1)

def main():
    print("🤖 피클 패밀리 텔레그램 AI 봇 시스템 가동 시작")
    
    # Render 헬스체크 데몬 가동
    threading.Thread(target=start_health_server, daemon=True).start()

    # 1. 덕영님 피클 봇 워커 시작
    worker_deokyeong = TelegramBotWorker(
        token=DEOKYEONG_BOT_TOKEN,
        display_name="덕영 피클",
        system_prompt=DEOKYEONG_SYSTEM_PROMPT,
        trigger_keywords=["피클", "피클아", "덕영피클", "남편피클"],
        counterpart_username="pickle_trade_bot"
    )
    worker_deokyeong.start()

    # 2. 아내분 피클 봇 워커 시작
    worker_wife = TelegramBotWorker(
        token=WIFE_BOT_TOKEN,
        display_name="아내 피클",
        system_prompt=WIFE_SYSTEM_PROMPT,
        trigger_keywords=["아내피클", "아내 피클", "연두피클", "연두 피클"],
        counterpart_username="my_usstock_bot"
    )
    worker_wife.start()

    # 메인 스레드 유지
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
