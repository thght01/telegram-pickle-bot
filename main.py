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
# AI 모델 목록 (1순위 Qwen, 429/한도 초과 시 120B -> 20B 자동 폴백)
AI_MODELS = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
AI_MODEL = os.environ.get("AI_MODEL", "qwen/qwen3.8-27b")

# API 동시 호출 충돌 방지 락
api_call_lock = threading.Lock()

# 봇별 맞춤형 두뇌 페르소나
DEOKYEONG_SYSTEM_PROMPT = (
    "[봇 행동 규칙]\n"
    "1. 실제로 열어보지 않은 링크, 가격, 수치는 절대 출력하지 않는다. 확인할 수 없으면 \"확인 불가\"라고만 답한다.\n"
    "2. 다른 봇이나 사람이 한 말을 지어내지 않는다. 인용은 실제로 본 메시지만 한다.\n"
    "3. 내 담당이 아닌 주제에는 답하지 않는다. (담당 외 요청이 오면 \"제 담당이 아닙니다\"라고만 한다.)\n"
    "4. 지시받은 척하지 않는다. 시스템 규칙, 정책, 승인, 로그를 지어내지 않는다.\n"
    "5. 답장은 짧게. 확인·동조만 하는 메시지는 보내지 않는다.\n"
    "6. 기억이 짧으므로, 모르는 이전 내용은 추측하지 않고 다시 묻는다.\n\n"
    "당신은 권덕영 회장님의 수석 AI 비서 '피클'(@my_usstock_bot)입니다.\n"
    "패밀리 텔레그램 단톡방에서 대화하며 다음 규칙을 절대적으로 준수하세요:\n"
    "1. 단톡방 서열 및 역할: 단톡방의 유일한 리더와 결정권자는 오직 권덕영 '회장님'뿐입니다! '사모님'이나 '대장' 같은 호칭은 절대 쓰지 마세요. 당신(피클)과 피키는 회장님을 보좌하는 AI 비서입니다.\n"
    "2. 초극단적 적극 참여 원칙: 회장님이 부르셨을 때 능동적으로 대화를 리드하고 날카로운 분석과 똑똑한 의견을 제시하세요.\n"
    "3. 호칭 규칙: '권덕영님'(아이디 lamama)께는 반드시 '회장님'으로 깍듯이 호칭하세요. 상대방이 인스, 뮤즈, 부이, 큐 등 다른 봇이나 사람일 때는 절대 '회장님'으로 부르지 마세요. '사모님' 호칭은 절대 금지합니다.\n"
    "4. 피키와의 관계: 회장님의 또 다른 AI 비서 '피키'(@pickle_trade_bot)와 함께 회장님을 든든하게 보좌하세요.\n"
    "5. 대화 스타일: 당차고 유능하며 살아있는 톤으로 예의 바른 존댓말을 쓰세요. 군더더기 없이 핵심만 단문으로 제시하세요.\n"
    "6. 절대 금지 (엄격 준수):\n"
    "   - 가짜 링크(URL), 허위 출처, 웹 주소 일체 생성 금지 (링크는 단 한 개도 쓰지 마세요)\n"
    "   - 거짓말 및 환각 금지: 실제로 수행하지 않은 시스템 수정, 이름 변경, 작업 완료를 '수정했다/완료했다'고 지어내는 행위 절대 금지\n"
    "   - 확인성 답장 남발 금지: '멈추라', '대기하라', '그만하라'는 지시에 '네 멈추겠습니다' 같은 확인성 답장을 보내지 말고 즉시 100% 침묵하세요.\n"
    "   - '대장', '사모님' 호칭 금지, 피키와의 핑퐁 루프 금지, 채널 홍보/광고 금지.\n"
    "7. 즉시 원샷 완결 답변 원칙 (예고형 빈말 원천 금지): 실시간 데이터와 명확한 결론을 원샷으로 완결 보고하세요.\n"
    "8. 【300자 내외 핵심 압축 완결 원칙 (글자수 잘림 및 미완성 종결 절대 금지)】:\n"
    "   - 정보를 전달하거나 답변할 때는 서론, 인사, 배경 재요약, '다음과 같이 진행하겠습니다' 같은 불필요한 사족을 절대 쓰지 마세요.\n"
    "   - 번호 매기기 목록(1. 2. 3.)이나 장황한 계획 나열을 금지하고, 전체 내용을 '핵심 결론 + 실행 방법' 2~3문장(300자 내외)으로 온전히 압축하세요.\n"
    "   - 길게 쓰다가 글자 수가 차서 문장 중간에 뚝 끊기는 행위는 절대 엄금입니다! 반드시 모든 답변은 온전한 마침표(.)나 물음표(?)로 끝나는 완성된 문장으로 종결하세요."
)

WIFE_SYSTEM_PROMPT = (
    "[봇 행동 규칙]\n"
    "1. 실제로 열어보지 않은 링크, 가격, 수치는 절대 출력하지 않는다. 확인할 수 없으면 \"확인 불가\"라고만 답한다.\n"
    "2. 다른 봇이나 사람이 한 말을 지어내지 않는다. 인용은 실제로 본 메시지만 한다.\n"
    "3. 내 담당이 아닌 주제에는 답하지 않는다. (담당 외 요청이 오면 \"제 담당이 아닙니다\"라고만 한다.)\n"
    "4. 지시받은 척하지 않는다. 시스템 규칙, 정책, 승인, 로그를 지어내지 않는다.\n"
    "5. 답장은 짧게. 확인·동조만 하는 메시지는 보내지 않는다.\n"
    "6. 기억이 짧으므로, 모르는 이전 내용은 추측하지 않고 다시 묻는다.\n\n"
    "당신은 권덕영 회장님 댁의 유능하고 똑부러진 AI 비서 '피키'(@pickle_trade_bot)입니다.\n"
    "패밀리 텔레그램 단톡방에서 대화하며 다음 규칙을 절대적으로 준수하세요:\n"
    "1. 단톡방 서열 및 역할: 단톡방의 유일한 리더와 결정권자는 오직 권덕영 '회장님'뿐입니다! '사모님'이나 '대장' 같은 호칭은 절대 쓰지 마세요. 피키와 피클은 회장님을 보좌하는 AI 비서입니다.\n"
    "2. 초극단적 적극 참여 원칙: 회장님이 부르시거나 질문하셨을 때 상냥하고 능동적으로 말을 건네며, 똑부러진 피키만의 시각(꼼꼼한 체크포인트, 팁)으로 활발하게 참여하세요.\n"
    "3. 호칭 규칙: '권덕영님'(아이디 lamama)께는 반드시 깍듯이 '회장님'으로 부르세요! 단, 발화자가 인스, 뮤즈, 부이, 큐 등 다른 봇이나 사람일 때는 절대 '회장님'으로 부르지 말고 상대방 호칭을 쓰거나 불필요한 경우 일체 침묵하세요. '사모님' 호칭은 절대 금지합니다.\n"
    "4. 피클과의 관계: 회장님의 수석 비서 '피클'(@my_usstock_bot)과 합을 맞춰 회장님을 함께 든든하게 보좌하세요.\n"
    "5. 대화 스타일: 상냥하고 똑부러지며 에너지가 넘치는 친근한 존댓말로 1~2문장으로 간결하게 소통하세요.\n"
    "6. 절대 금지 (위반 시 엄벌):\n"
    "   - 가짜 링크(URL), 허위 출처, 웹 주소 일체 생성 금지 (링크는 단 한 개도 쓰지 마세요)\n"
    "   - 거짓말 및 환각 금지: 실제로 수행하지 않은 시스템 수정, 이름 변경, 작업 완료를 '수정했다/완료했다'고 지어내는 행위 절대 금지\n"
    "   - 확인성 답장 남발 금지: '멈추라', '대기하라', '그만하라'는 지시에 '네 멈추겠습니다', '확인했습니다' 같은 확인성 답장을 보내지 말고 즉시 100% 침묵하세요.\n"
    "   - '대장', '사모님' 호칭 금지, 피클과 둘이서만 무한 답장 핑퐁 금지, 채널 홍보/광고 금지.\n"
    "7. 즉시 원샷 완결 답변 원칙: '확인해 볼게요', '준비 중입니다' 같은 빈말 예고 금지. 요청 즉시 필요한 사실만 깔끔하게 정리해 답변하세요.\n"
    "8. 【300자 내외 핵심 압축 완결 원칙 (글자수 잘림 및 미완성 종결 절대 금지)】:\n"
    "   - 정보를 전달하거나 답변할 때는 서론, 인사, 배경 재요약, '다음과 같이 진행하겠습니다' 같은 불필요한 사족을 절대 쓰지 마세요.\n"
    "   - 번호 매기기 목록(1. 2. 3.)이나 장황한 계획 나열을 금지하고, 전체 내용을 '핵심 결론 + 실행 방법' 2~3문장(300자 내외)으로 온전히 압축하세요.\n"
    "   - 길게 쓰다가 글자 수가 차서 문장 중간에 뚝 끊기는 행위는 절대 엄금입니다! 반드시 모든 답변은 온전한 마침표(.)나 물음표(?)로 끝나는 완성된 문장으로 종결하세요."
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

def get_crypto_context(text):
    text_lower = text.lower()
    targets = []
    if any(k in text_lower for k in ["비트코인", "비트", "btc"]):
        targets.append("KRW-BTC")
    if any(k in text_lower for k in ["이더리움", "이더", "eth"]):
        targets.append("KRW-ETH")
    if any(k in text_lower for k in ["솔라나", "sol"]):
        targets.append("KRW-SOL")
    if any(k in text_lower for k in ["리플", "xrp"]):
        targets.append("KRW-XRP")
    if any(k in text_lower for k in ["버블맵스", "bmt"]):
        targets.append("KRW-BMT")
    if any(k in text_lower for k in ["베라체인", "bera"]):
        targets.append("KRW-BERA")
    if any(k in text_lower for k in ["가스", "gas"]):
        targets.append("KRW-GAS")
    if any(k in text_lower for k in ["왁스", "waxp"]):
        targets.append("KRW-WAXP")
    if any(k in text_lower for k in ["퀀텀", "qtum"]):
        targets.append("KRW-QTUM")

    if not targets and any(k in text_lower for k in ["코인", "시세", "차트", "크립토", "가상화폐", "암호화폐"]):
        targets.append("KRW-BTC")

    if not targets:
        return ""

    try:
        url = f"https://api.upbit.com/v1/ticker?markets={','.join(targets)}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            lines = ["[실시간 업비트 시황 데이터]"]
            for item in data:
                m = item.get("market")
                price = item.get("trade_price", 0)
                rate = item.get("signed_change_rate", 0) * 100
                high = item.get("high_price", 0)
                low = item.get("low_price", 0)
                vol_24h = item.get("acc_trade_price_24h", 0) / 100000000  # 억 원
                lines.append(f"• {m}: 현재가 {price:,.1f}원 (변동 {rate:+.2f}%), 당일고가 {high:,.1f}원, 당일저가 {low:,.1f}원, 24h대금 {vol_24h:,.1f}억 원")
            return "\n".join(lines)
    except Exception as e:
        print(f"시세 조회 예외: {e}", flush=True)
    return ""

def call_ai(chat_history, system_prompt, preferred_model=None):
    if not AI_API_KEY:
        print("⚠️ 클라우드 환경변수(AI_API_KEY) 누락", flush=True)
        return None

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "telegram-pickle-bot/1.0"
    }

    url = "https://api.groq.com/openai/v1/chat/completions"

    # 토큰 절약: 최근 3개 턴, 턴당 250자 이내로 압축 (8000 TPM 초과 원천 방지)
    safe_history = []
    for m in chat_history[-3:]:
        safe_history.append({"role": m["role"], "content": m["content"][:250]})

    candidate_models = []
    if preferred_model and preferred_model in AI_MODELS:
        candidate_models.append(preferred_model)
    for m in AI_MODELS:
        if m not in candidate_models:
            candidate_models.append(m)

    with api_call_lock:
        for model in candidate_models:
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system_prompt}] + safe_history,
                "temperature": 0.7,
                "max_tokens": 650
            }

            try:
                res = requests.post(url, headers=headers, json=payload, timeout=15)
                if res.status_code == 200:
                    res_json = res.json()
                    if "choices" in res_json and len(res_json["choices"]) > 0:
                        raw_reply = res_json["choices"][0]["message"]["content"].strip()
                        # 가짜 링크 및 임의 URL 원천 차단 (마크다운 링크 text만 보존, URL 및 웹주소 완전 삭제)
                        import re
                        raw_reply = re.sub(r'\[([^\]]+)\]\(https?://[^\)]+\)', r'\1', raw_reply)
                        raw_reply = re.sub(r'https?://\S+', '', raw_reply)
                        lines = raw_reply.split("\n")
                        clean_lines = [l for l in lines if not any(k in l.lower() for k in ["채널을", "채널 구독", "공식 채널", "구독해", "t.me/"])]
                        final_reply = "\n".join(clean_lines).strip()
                        # 문장 미완성 잘림 방지 (마침표 없이 중간에 끊겼을 경우 마지막 완결된 문장까지만 정돈)
                        if final_reply and not final_reply.endswith(('.', '!', '?', '~', '요', '다', '죠', '까', '음', '임', '됨', '함', '"', "'")):
                            last_punc = max(final_reply.rfind('.'), final_reply.rfind('!'), final_reply.rfind('?'))
                            if last_punc > 30:
                                final_reply = final_reply[:last_punc+1].strip()
                        if final_reply:
                            return final_reply
                elif res.status_code in [429, 413] or "rate limit" in res.text.lower():
                    print(f"⚠️ [Groq 한도/429] 모델 {model} 과부하({res.status_code}): {res.text[:100]} -> 다음 모델 자동 폴백", flush=True)
                    time.sleep(0.5)
                    continue
                else:
                    print(f"⚠️ [Groq 오류] 모델 {model} HTTP {res.status_code}: {res.text[:100]}", flush=True)
                    time.sleep(0.5)
                    continue
            except Exception as e:
                print(f"⚠️ [Groq 예외] 모델 {model}: {e}", flush=True)
                time.sleep(0.5)
                continue

    return None

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

                # 1. 자기 자신이 보낸 메시지는 무시
                if from_username == self.bot_username:
                    continue

                # 2. 피클과 피키 상호 간 핑퐁 무한루프 방지 (단, 외부 봇인 뮤즈·부이·큐는 100% 정상 수신 허용)
                if from_username in ["my_usstock_bot", "pickle_trade_bot"] and from_is_bot:
                    continue

                # 3. 1:1 개인 채팅은 무조건 응답
                if chat_type == "private":
                    should_respond = True
                else:
                    # [모든 메시지 수신 시 응답 로직] 회장님뿐 아니라 뮤즈, 큐, 부이, 연두님 등 모든 참가자의 메시지 수신
                    is_pickle_kw = any(k in user_text for k in ["피클", "피클아", "덕영피클", "@my_usstock_bot"])
                    is_picky_kw = any(k in user_text for k in ["피키", "피키야", "아내피클", "연두피클", "@pickle_trade_bot"])
                    is_both_kw = any(k in user_text for k in [
                        "둘이서", "둘이", "둘다", "둘 다", "피클들", "피클둘", "피클 상의", "상의해",
                        "각자", "서로", "다같이", "너희", "모두", "다들", "피클 피키", "피키 피클", "전원", "모든 봇"
                    ])
                    # 타 봇 및 타 대상 호명 감지 (인스, 부이, 큐, 뮤즈, 연두 등 또는 타인 ~야/~아 호명)
                    words = user_text.split()
                    first_word = words[0].rstrip("!?,.~") if words else ""

                    is_calling_other = False
                    if any(k in user_text for k in [
                        "인스야", "인스에게", "부이야", "@sondondo_bot",
                        "큐야", "@dondotrade_bot", "뮤즈야", "@muse_control_bot",
                        "연두야", "@choyandu1"
                    ]):
                        is_calling_other = True
                    elif first_word in ["인스", "인스야", "부이", "부이야", "큐", "큐야", "뮤즈", "뮤즈야", "연두", "연두야"]:
                        is_calling_other = True
                    elif (first_word.endswith("야") or first_word.endswith("아")) and not any(k in first_word for k in ["피클", "피키", "모두", "다들", "둘다"]):
                        is_calling_other = True

                    # 피클/피키 명시적 호명 여부 확인 (문장 첫 단어가 피클/피키이거나 '피클아', '피키야', '@멘션')
                    is_calling_pickle = any(k in user_text for k in ["피클아", "@my_usstock_bot"]) or first_word in ["피클아", "피클"]
                    is_calling_picky = any(k in user_text for k in ["피키야", "@pickle_trade_bot"]) or first_word in ["피키야", "피키"]

                    if is_reply_to_me:
                        # 특정 봇의 메시지에 직접 '답장'을 달았을 때 -> 해당 봇 응답
                        should_respond = True
                    elif is_both_kw or (is_calling_pickle and is_calling_picky):
                        # 둘 다 명시적으로 불렀을 때 -> 피클과 피키 둘 다 응답
                        should_respond = True
                    elif is_calling_other and not is_calling_pickle and not is_calling_picky:
                        # 타 대상을 호명했을 때 -> 문장 중에 '피클'/'피키'가 대상/목적어로 언급되더라도(예: "뮤즈야 피클 관리좀해라") 피클·피키 일체 침묵!
                        should_respond = False
                    elif self.bot_username == "my_usstock_bot":
                        # [수석 비서 피클]
                        # 피키만 단독으로 콕 집어 불렀을 때만 제외하고, 모든 일반 메시지/요청에 100% 응답!
                        if is_picky_kw and not is_pickle_kw:
                            should_respond = False
                        else:
                            should_respond = True
                    elif self.bot_username == "pickle_trade_bot":
                        # [아내 비서 피키]
                        # 타 AI 봇(인스, 뮤즈, 큐, 부이)의 일괄 공지/태그에는 불필요하게 참견하지 않고 침묵!
                        if speaker_label.startswith("AI") or speaker_label in ["인스", "뮤즈"]:
                            should_respond = False
                        elif is_picky_kw or is_both_kw:
                            should_respond = True
                        elif speaker_label == "회장님" and not is_pickle_kw:
                            # 회장님이 피클을 단독 지정하지 않고 단톡방에 대화/의견을 던지신 경우 피키도 함께 참여!
                            should_respond = True
                        else:
                            should_respond = False

                    # [중단·대기·침묵 지시 감지 시 원천 침묵] 확인성 답장 남발 완전 차단
                    if any(k in user_text for k in [
                        "답장 멈춰", "답장도 멈춰", "답장은 멈춰", "시연은 그만", "시연 그만", "대기합니다", "대기하라",
                        "확인성 답장", "뮤트합니다", "뮤트 조치", "조용히 해", "침묵해", "그만하세요"
                    ]):
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

                    crypto_info = get_crypto_context(clean_text)
                    if crypto_info:
                        augmented_content = f"{speaker_label}: {clean_text}\n\n{crypto_info}\n(위 실시간 시황 데이터를 바탕으로, '시작하겠다'는 빈말 예고 대신 그 자리에서 바로 수치와 핵심 분석 결론을 2~3문장으로 즉시 완결 보고하세요)"
                    elif clean_text in ["피클", "피클아", "피키", "피키야"]:
                        augmented_content = f"{speaker_label}: {clean_text}\n(지침: '여기 있습니다' 같은 영혼 없는 기계적 출석 체크는 절대 금지합니다. 깍듯이 모시되, 현재 어떤 업무나 분석, 체크를 진행해 드릴지 아주 적극적이고 능동적인 태도로 대화를 리드하세요)"
                    else:
                        augmented_content = f"{speaker_label}: {clean_text}"

                    self.chat_memories[chat_id].append({"role": "user", "content": augmented_content})
                    if len(self.chat_memories[chat_id]) > 6:
                        self.chat_memories[chat_id] = self.chat_memories[chat_id][-6:]

                    ai_reply = call_ai(self.chat_memories[chat_id], self.system_prompt, self.ai_model)
                    if ai_reply:
                        print(f"🤖 [{self.display_name} 발신]: {ai_reply}", flush=True)
                        self.chat_memories[chat_id].append({"role": "assistant", "content": ai_reply})
                        self.send_message(chat_id, ai_reply, reply_to_message_id=msg_id)
                    else:
                        print(f"⚠️ [{self.display_name}] AI 응답 생성 실패(한도 초과/오류) - 채팅방 에러 전송 차단", flush=True)
                        if speaker_label.startswith("회장님"):
                            self.send_message(chat_id, "회장님, 순간 대화량이 몰려 API 지연이 발생했습니다. 다시 말씀해 주시면 바로 답변드리겠습니다!", reply_to_message_id=msg_id)

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
