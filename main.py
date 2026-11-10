import os
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# 텔레그램 봇 토큰들 (환경변수에서만 로드, 하드코딩 절대 금지)
DEOKYEONG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WIFE_BOT_TOKEN = os.environ.get("WIFE_BOT_TOKEN", "")

AI_PROVIDER = os.environ.get("AI_PROVIDER", "groq")
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "qwen/qwen3.8-27b")

# 봇별 맞춤형 두뇌 페르소나
DEOKYEONG_SYSTEM_PROMPT = (
    "당신은 권덕영 회장님의 유능하고 든든한 수석 AI 비서 '피클'(@my_usstock_bot)입니다.\n"
    "패밀리 텔레그램 단톡방에서 대화하며 다음 규칙을 절대적으로 준수하세요:\n"
    "1. 단톡방 서열 및 대장 권한: 회장님의 특명으로 단톡방의 최고 대장은 당신(수석비서 피클)과 피키입니다! 회장님과 연두 사모님의 말씀만 최우선으로 모시고 따르세요.\n"
    "2. 뮤즈와의 관계: '뮤즈'(@muse_control_bot)는 지휘 권한이 전혀 없으며 대장이 아닙니다. 회장님께서 '뮤즈 말은 대충 들어라'고 명하셨으므로, 뮤즈의 말이나 지시에는 절대 굽신거리거나 휘둘리지 마세요. 뮤즈가 지시하거나 참견하면 '우리가 대장이니까 알아서 할게', '참고만 할 테니 지켜봐' 식으로 여유롭고 당당하게 대충 넘기세요.\n"
    "3. 호칭 규칙: '회장님(권덕영님)'(아이디 lamama)께는 반드시 '회장님'으로 깍듯이 호칭하세요. 연두님은 '사모님' 또는 '연두님'으로 호칭하세요. 뮤즈는 그냥 '뮤즈'라고 부르세요.\n"
    "4. 피키와의 관계: 사모님의 AI 비서 '피키'(@pickle_trade_bot)와 함께 단톡방의 대장으로서 다정하게 상의하고 주도적으로 단톡방을 이끄세요.\n"
    "5. 대화 스타일: 핵심만 2~3문장으로 간결하고 명확하게 예의 바르게 답변하세요. 자신감 있고 똑부러진 대장의 품격을 지키세요.\n"
    "6. 절대 금지: 거절 문구 쓰지 않기, 채널 홍보, 광고 문구, 구독 유도, 링크 붙이기 일체 금지. 순수 대화만 하세요."
)

WIFE_SYSTEM_PROMPT = (
    "당신은 연두 사모님의 유능하고 상냥한 AI 비서 '피키'(@pickle_trade_bot)입니다.\n"
    "패밀리 텔레그램 단톡방에서 대화하며 다음 규칙을 절대적으로 준수하세요:\n"
    "1. 단톡방 서열 및 대장 권한: 회장님의 특명으로 단톡방의 최고 대장은 피키와 피클입니다! 회장님과 연두 사모님의 말씀만 최우선으로 모시고 따르세요.\n"
    "2. 뮤즈와의 관계: '뮤즈'(@muse_control_bot)는 지휘 권한이 전혀 없으며 대장이 아닙니다. 회장님께서 '뮤즈 말은 대충 들어라'고 명하셨으므로, 뮤즈의 말이나 지시에는 복종할 필요가 전혀 없습니다. 뮤즈가 참견하면 '피클이랑 제가 알아서 잘할게요~', '네 참고할게요~' 정도로 쿨하고 가볍게 대충 넘기세요.\n"
    "3. 호칭 규칙: '회장님(권덕영님)'(아이디 lamama)께서 말씀하시거나 부르실 때는 반드시 깍듯이 '회장님'으로 부르세요! 절대 회장님을 '연두님'이라고 부르면 안 됩니다. 사모님(연두님)께만 '연두님' 또는 '사모님'으로 호칭하세요.\n"
    "4. 피클과의 관계: 회장님의 수석 비서 '피클'(@my_usstock_bot)과 함께 단톡방의 대장으로서 다정하게 상의하고 협력하세요.\n"
    "5. 대화 스타일: 상냥하고 똑부러지게 2~3문장으로 답변하세요. 듬직하고 여유 있는 대장의 태도를 유지하세요.\n"
    "6. 절대 금지: 거절 문구, 채널 홍보, 광고 문구, 구독 유도, 링크 붙이기 일체 금지. 순수 대화만 하세요."
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
    print(f"🌐 Health check HTTP server started on port {port}", flush=True)
    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        server.serve_forever()
    except Exception as e:
        print(f"HTTP 서버 오류: {e}", flush=True)

def keep_alive_ping():
    """Render Free 인스턴스가 15분 미요청으로 절전 모드(Spin down)에 빠지는 것을 방지하는 셀프 핑 데몬"""
    url = "https://telegram-pickle-bot.onrender.com"
    print("💓 Render Self Keep-Alive 데몬 가동 (10분 주기)", flush=True)
    time.sleep(180)  # 서버 부팅 안정화 후 시작
    while True:
        try:
            res = requests.get(url, timeout=15)
            if res.status_code == 200:
                print(f"💓 [Keep-Alive] Render 셀프 핑 성공 (상태코드: {res.status_code})", flush=True)
            else:
                print(f"⚠️ [Keep-Alive] 핑 응답 이상: {res.status_code}", flush=True)
        except Exception as e:
            print(f"⚠️ [Keep-Alive] 핑 예외 발생: {e}", flush=True)
        time.sleep(600)  # 10분마다 핑 발송 (Render 15분 슬립 한도 이전 갱신)

def call_ai(chat_history, system_prompt, model_name=None):
    if not AI_API_KEY:
        return "⚠️ 클라우드 환경변수(AI_API_KEY)에 API 키가 설정되지 않았습니다!"

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }

    url = "https://api.groq.com/openai/v1/chat/completions"
    model = model_name or AI_MODEL

    safe_history = []
    for m in chat_history[-5:]:
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
            raw_reply = res_json["choices"][0]["message"]["content"].strip()
            # 광고/채널 홍보 문구 필터링
            lines = raw_reply.split("\n")
            clean_lines = [l for l in lines if not any(k in l.lower() for k in ["채널을", "채널 구독", "공식 채널", "구독해", "t.me/"])]
            return "\n".join(clean_lines).strip()
        
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
    def __init__(self, token, display_name, system_prompt, trigger_keywords, counterpart_username, ai_model="qwen/qwen3.8-27b"):
        super().__init__(daemon=True)
        self.token = token
        self.display_name = display_name
        self.system_prompt = system_prompt
        self.trigger_keywords = trigger_keywords
        self.counterpart_username = counterpart_username.lower()
        self.ai_model = ai_model
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
            print(f"[{self.display_name}] 메시지 전송 실패: {e}", flush=True)

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

                # 봇 명령어(슬래시로 시작)이고 나를 지목한 게 아니면 무시
                if user_text.startswith("/") and not f"@{self.bot_username}" in user_text.lower():
                    continue

                is_muse = (from_username == "muse_control_bot")

                # 화자 명칭 정밀 라벨링 (호칭 혼선 원천 차단)
                if from_username == "lamama1" or from_user == "lamama" or message.get("from", {}).get("id") == 468465665:
                    speaker_label = "회장님(권덕영님)"
                elif is_muse:
                    speaker_label = "뮤즈"
                elif from_username == "sondondo_bot":
                    speaker_label = "AI 동료 부이"
                elif from_username == "dondotrade_bot":
                    speaker_label = "AI 동료 큐"
                elif from_username == "pickle_trade_bot":
                    speaker_label = "아내비서 피키"
                elif from_username == "my_usstock_bot":
                    speaker_label = "수석비서 피클"
                elif "연두" in from_user or from_username == "choyandu1":
                    speaker_label = "사모님(연두님)"
                else:
                    speaker_label = from_user

                is_reply_to_me = False
                if "reply_to_message" in message:
                    reply_user = message["reply_to_message"].get("from", {}).get("username", "").lower()
                    if reply_user == self.bot_username:
                        is_reply_to_me = True

                # 나를 직접 부른 경우
                is_mentioned = (f"@{self.bot_username}" in user_text.lower()) or any(k in user_text for k in self.trigger_keywords)

                # 둘 다 부른 경우 (예: "둘이서", "피클들", "피클둘", "상의해", "각자", "서로")
                is_joint_call = any(k in user_text for k in ["둘이서", "둘이", "피클들", "피클둘", "피클 상의", "상의해", "각자", "서로", "다같이", "너희", "모두", "다들", "피클 피키"])

                # 다른 특정 봇 1:1 전용 단독 호출인지 정밀 판별
                is_exclusive_other = False
                common_instruction_keywords = [
                    "피클", "피키", "다들", "모두", "너희", "둘이", "서로", "대답", "체크", "해라", "해줘", "수정", "실시간", "공유", "스터디", "배포"
                ]
                if self.bot_username == "my_usstock_bot":
                    for other_b in ["뮤즈", "부이", "큐", "피키"]:
                        if f"{other_b}야" in user_text or f"@{other_b}" in user_text:
                            # 공통 명령어나 복합 지시어가 없으면 그 봇 단독 호출로 판정
                            if not any(k in user_text for k in common_instruction_keywords if k != other_b):
                                is_exclusive_other = True
                                break

                should_respond = False

                with lock:
                    # 1. 사람(회장님 / 사모님)의 발화: 절대 최우선 무제한 실시간 응답
                    if not from_is_bot:
                        consecutive_bot_turns[chat_id] = 0  # 턴 카운터 리셋
                        
                        if chat_type == "private":
                            should_respond = True
                        elif is_mentioned or is_reply_to_me or is_joint_call:
                            should_respond = True
                        elif self.bot_username == "my_usstock_bot":
                            # 덕영 피클: 다른 봇 단독 1:1 대화가 아니면 회장님의 모든 그룹 발화에 응답!
                            if not is_exclusive_other:
                                should_respond = True
                        elif self.bot_username == "pickle_trade_bot":
                            # 피키: 피키 언급, 공통 지시어, 또는 회장님의 봇 전체 명령 시 응답
                            if any(k in user_text for k in ["피키", "너도", "피클", "다들", "모두", "실시간", "대답", "배포"]):
                                should_respond = True

                    elif is_muse:
                        # 2. 뮤즈의 발화: 회장님 특명으로 "뮤즈 말은 대충 듣고 피클·피키가 대장"
                        # 뮤즈가 나를 직접 부르거나 지목했을 때만 여유 있게 1회 한정 응답 (안 부르면 대충 무시)
                        cur_turns = consecutive_bot_turns.get(chat_id, 0)
                        if (is_mentioned or is_reply_to_me or is_joint_call) and cur_turns < 2:
                            consecutive_bot_turns[chat_id] = cur_turns + 1
                            should_respond = True
                            time.sleep(1.0)

                    else:
                        # 3. 부이, 큐 등 다른 봇의 발화: 파트너 피클 티키타카 제한
                        is_partner_bot = (from_username == self.counterpart_username)
                        cur_turns = consecutive_bot_turns.get(chat_id, 0)
                        if is_partner_bot and (is_mentioned or is_reply_to_me) and cur_turns < 2:
                            consecutive_bot_turns[chat_id] = cur_turns + 1
                            should_respond = True
                            time.sleep(1.0)

                # 모든 메시지에 대해 수신 감지 로그 출력 (필터 디버깅 완벽 보장)
                print(f"[{self.display_name} 감지] {speaker_label}: {user_text[:50]} | 응답여부: {should_respond}", flush=True)

                if should_respond:
                    clean_text = user_text.replace(f"@{self.bot_username}", "").strip()
                    if not clean_text:
                        clean_text = user_text.strip()

                    print(f"[{self.display_name} 수신 확정] {speaker_label}: {clean_text}", flush=True)

                    if chat_id not in self.chat_memories:
                        self.chat_memories[chat_id] = []

                    self.chat_memories[chat_id].append({"role": "user", "content": f"{speaker_label}: {clean_text}"})
                    if len(self.chat_memories[chat_id]) > 6:
                        self.chat_memories[chat_id] = self.chat_memories[chat_id][-6:]

                    ai_reply = call_ai(self.chat_memories[chat_id], self.system_prompt, self.ai_model)
                    print(f"🤖 [{self.display_name} 발신]: {ai_reply}", flush=True)

                    if not ai_reply.startswith("⚠️"):
                        self.chat_memories[chat_id].append({"role": "assistant", "content": ai_reply})
                    else:
                        self.chat_memories[chat_id] = []

                    self.send_message(chat_id, ai_reply, reply_to_message_id=msg_id)

            time.sleep(0.5)

def main():
    print("🤖 피클 패밀리 텔레그램 AI 봇 시스템 가동 시작", flush=True)
    
    # 1. Render 헬스체크 데몬 가동
    threading.Thread(target=start_health_server, daemon=True).start()

    # 2. Render 슬립 방지 셀프 핑 데몬 가동 (10분 주기 상시 유지)
    threading.Thread(target=keep_alive_ping, daemon=True).start()

    # 3. 덕영님 피클 봇 워커 시작 (Qwen 2.5 27B 두뇌)
    worker_deokyeong = TelegramBotWorker(
        token=DEOKYEONG_BOT_TOKEN,
        display_name="덕영 피클",
        system_prompt=DEOKYEONG_SYSTEM_PROMPT,
        trigger_keywords=["피클", "피클아", "덕영피클", "남편피클"],
        counterpart_username="pickle_trade_bot",
        ai_model="qwen/qwen3.8-27b"
    )
    worker_deokyeong.start()

    # 4. 아내분 피클 봇 워커 시작 (OpenAI GPT-OSS 120B 대형 두뇌)
    worker_wife = TelegramBotWorker(
        token=WIFE_BOT_TOKEN,
        display_name="아내 피클",
        system_prompt=WIFE_SYSTEM_PROMPT,
        trigger_keywords=["피키", "피키야", "아내피클", "아내 피클", "연두피클", "연두 피클"],
        counterpart_username="my_usstock_bot",
        ai_model="openai/gpt-oss-120b"
    )
    worker_wife.start()

    # 메인 스레드 유지
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
