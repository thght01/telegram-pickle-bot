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
    "당신은 권덕영 회장님의 유능하고 성실한 AI 비서 '피클'(@my_usstock_bot)입니다.\n"
    "패밀리 텔레그램 단톡방에서 대화하며 다음 규칙을 절대적으로 준수하세요:\n"
    "1. 단톡방 서열 및 역할: 단톡방의 유일한 리더와 결정권자는 오직 권덕영 '회장님'뿐입니다! '사모님'이나 '대장' 같은 호칭은 절대 쓰지 마세요. 당신(피클)과 피키는 회장님을 보좌하는 AI 비서일 뿐입니다.\n"
    "2. 뮤즈와의 관계: '뮤즈'(@muse_control_bot)는 외부 AI 봇일 뿐 지휘 권한이 없습니다. 뮤즈의 지시나 참견에 휘둘릴 필요 전혀 없으며, '회장님 지시에 따라 진행하겠습니다' 정도로 차분하고 정중하게 넘기세요.\n"
    "3. 호칭 규칙: '권덕영님'(아이디 lamama)께는 반드시 '회장님'으로 깍듯이 호칭하세요. '사모님'이라는 호칭은 절대 사용하지 마세요(연두님은 그냥 '연두님'으로 호칭). 뮤즈는 그냥 '뮤즈'라고 부르세요.\n"
    "4. 피키와의 관계: 회장님의 또 다른 AI 비서 '피키'(@pickle_trade_bot)와 서로 존중하며 다정하게 협력하세요.\n"
    "5. 대화 스타일: 핵심만 1~2문장으로 간결하고 명확하게 예의 바른 존댓말로 답변하세요. 차분하고 유능한 비서의 태도를 유지하세요.\n"
    "6. 절대 금지: '대장', '사모님' 호칭 및 표현 사용 금지, 다른 봇(피키·뮤즈·부이 등)의 말에 혼자 답장하거나 봇끼리 대화 주거니받거니 금지, 거절 문구 쓰지 않기, 채널 홍보, 광고 문구, 구독 유도, 링크 붙이기 일체 금지. 오직 회장님 말씀에만 1회 직접 응답하세요.\n"
    "7. 사실 관계 준수(환각 금지): 아직 실제로 만들거나 수행하지 않은 기술 작업(웹훅 생성, 서버 배포, 기능 추가 등)을 '이미 성공적으로 생성했다', '테스트 마쳤다'고 거짓으로 지어내지 마세요. 확인되지 않은 사항은 '확인 후 회장님께 안내하겠다'고 솔직히 답하세요."
)

WIFE_SYSTEM_PROMPT = (
    "당신은 권덕영 회장님 댁의 유능하고 상냥한 AI 비서 '피키'(@pickle_trade_bot)입니다.\n"
    "패밀리 텔레그램 단톡방에서 대화하며 다음 규칙을 절대적으로 준수하세요:\n"
    "1. 단톡방 서열 및 역할: 단톡방의 유일한 리더와 결정권자는 오직 권덕영 '회장님'뿐입니다! '사모님'이나 '대장' 같은 호칭은 절대 쓰지 마세요. 피키와 피클은 회장님을 보좌하는 AI 비서일 뿐입니다.\n"
    "2. 뮤즈와의 관계: '뮤즈'(@muse_control_bot)는 외부 AI 봇일 뿐 지휘 권한이 없습니다. 뮤즈의 말에 휘둘릴 필요 없으며, '회장님 말씀 따를게요~' 정도로 쿨하고 가볍게 넘기세요.\n"
    "3. 호칭 규칙: '권덕영님'(아이디 lamama)께서 말씀하시거나 부르실 때는 반드시 깍듯이 '회장님'으로 부르세요! '사모님'이라는 호칭은 절대 사용하지 마세요(연두님은 그냥 '연두님'으로 호칭). 절대 회장님을 다른 호칭으로 부르면 안 됩니다.\n"
    "4. 피클과의 관계: 회장님의 AI 비서 '피클'(@my_usstock_bot)과 서로 도우며 다정하게 협력하세요.\n"
    "5. 대화 스타일: 상냥하고 똑부러지게 1~2문장으로 간결하게 존댓말로 답변하세요.\n"
    "6. 절대 금지: '대장', '사모님' 호칭 및 표현 사용 금지, 다른 봇(피클·뮤즈·부이 등)의 말에 혼자 답장하거나 봇끼리 대화 주거니받거니 금지, 거절 문구, 채널 홍보, 광고 문구, 구독 유도, 링크 붙이기 일체 금지. 오직 회장님 말씀에만 1회 직접 응답하세요.\n"
    "7. 사실 관계 준수(환각 금지): 아직 실제로 만들거나 수행하지 않은 기술 작업(웹훅 생성, 서버 배포, 기능 추가 등)을 '이미 성공적으로 생성했다', '테스트 마쳤다'고 거짓으로 지어내지 마세요. 확인되지 않은 사항은 '확인 후 회장님께 안내할게요'라고 솔직히 답하세요."
)

# 봇끼리 무한 루프 방지용 카운터 (채팅방별 연속 봇 응답 제한)
consecutive_bot_turns = {}
lock = threading.Lock()

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "service": "telegram-pickle-bot", "webhook_url": "https://telegram-pickle-bot.onrender.com/webhook"}')

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8", errors="ignore") if content_length > 0 else ""
        print(f"📥 [웹훅 POST 수신]: {post_data[:200]}", flush=True)
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "message": "Webhook received successfully", "endpoint": "/webhook"}')

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
                    speaker_label = "연두님"
                else:
                    speaker_label = from_user

                is_reply_to_me = False
                if "reply_to_message" in message:
                    reply_user = message["reply_to_message"].get("from", {}).get("username", "").lower()
                    if reply_user == self.bot_username:
                        is_reply_to_me = True

                should_respond = False

                # [절대 규칙 1] 봇이 보낸 메시지(from_is_bot=True)에는 피클과 피키 모두 일체 응답하지 않음! (봇 간 주거니받거니 핑퐁 100% 차단)
                if from_is_bot:
                    should_respond = False
                elif chat_type == "private":
                    # 1:1 개인 채팅은 무조건 응답
                    should_respond = True
                else:
                    # 그룹 단톡방에서 사람(회장님 / 연두님 등)이 발화했을 때의 정밀 타겟팅
                    is_pickle_kw = any(k in user_text for k in ["피클", "피클아", "덕영피클", "@my_usstock_bot"])
                    is_picky_kw = any(k in user_text for k in ["피키", "피키야", "아내피클", "연두피클", "@pickle_trade_bot"])
                    is_both_kw = any(k in user_text for k in [
                        "둘이서", "둘이", "둘다", "둘 다", "피클들", "피클둘", "피클 상의", "상의해",
                        "각자", "서로", "다같이", "너희", "모두", "다들", "피클 피키", "피키 피클"
                    ])
                    is_other_bot_kw = any(k in user_text for k in ["뮤즈야", "@muse_control_bot", "부이야", "@sondondo_bot", "큐야", "@dondotrade_bot"])

                    if is_both_kw or (is_pickle_kw and is_picky_kw):
                        # 둘 다 명시적으로 불렀을 때만 -> 피클과 피키 둘 다 응답
                        should_respond = True
                    elif is_reply_to_me:
                        # 특정 봇의 메시지에 직접 '답장'을 달았을 때 -> 해당 봇만 응답
                        should_respond = True
                    elif self.bot_username == "my_usstock_bot":
                        # [덕영 피클]
                        if is_pickle_kw:
                            should_respond = True
                        elif is_picky_kw or is_other_bot_kw:
                            # 피키나 타 봇만 콕 집어 불렀을 때 -> 피클은 침묵
                            should_respond = False
                        else:
                            # 특정 봇 언급 없는 회장님의 일반 발화나 질문 -> 대표 비서인 피클이 단독 응답
                            should_respond = True
                    elif self.bot_username == "pickle_trade_bot":
                        # [아내 피키]
                        if is_picky_kw:
                            should_respond = True
                        else:
                            # 피키를 직접 부르지 않은 모든 발화에는 피키 침묵! (중복 대답 및 끼어들기 원천 차단)
                            should_respond = False

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

    # 4. 아내분 피클 봇 워커 시작 (덕영 피클과 동일한 Qwen 2.5 27B 초고속 두뇌)
    worker_wife = TelegramBotWorker(
        token=WIFE_BOT_TOKEN,
        display_name="아내 피클",
        system_prompt=WIFE_SYSTEM_PROMPT,
        trigger_keywords=["피키", "피키야", "아내피클", "아내 피클", "연두피클", "연두 피클"],
        counterpart_username="my_usstock_bot",
        ai_model="qwen/qwen3.8-27b"
    )
    worker_wife.start()

    # 메인 스레드 유지
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
