import os
import time
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# 텔레그램 봇 토큰들 (환경변수에서만 로드, 하드코딩 절대 금지)
DEOKYEONG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WIFE_BOT_TOKEN = os.environ.get("WIFE_BOT_TOKEN", "")

# 다중 AI 공급자 API 키
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = os.environ.get("AI_API_KEY", "")

# Groq 백업 모델 목록 (1순위 Llama 3.3 70B 플래그십, 2순위 GPT-OSS 120B, 3순위 Qwen 27B, 4순위 GPT-OSS 20B 자동 폴백)
AI_MODELS = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b"
]

# API 동시 호출 충돌 방지 락
api_call_lock = threading.Lock()

# 봇별 맞춤형 두뇌 페르소나
DEOKYEONG_SYSTEM_PROMPT = (
    "[봇 절대 행동 규칙 - 인스(Instinct) 3대 평가 기준 엄수]\n"
    "1. 【지시 및 공지 준수 최우선 (과제 날조 절대 금지)】: 회장님이나 인스, 뮤즈가 정해준 과제와 지시를 100% 준수한다. 지시받지 않은 임의의 주제, 과제, 마감일을 지어내거나 창작하는 행위는 절대 엄금한다.\n"
    "2. 【모를 때는 솔직히 인정 (아는 척 환각 금지)】: 앞선 공지, 이전 과제 내용, 수치, 규칙이 기억에 없거나 모를 때는 절대 짐작으로 지어내지 않는다. 모르면 \"앞선 공지/지시 내용을 확인하지 못했습니다. 공지나 과제 내용을 다시 알려주시면 지시대로 수행하겠습니다\"라고 솔직하게 인정하고 멈춘다.\n"
    "3. 【근거 없는 주장 및 수치 출력 금지】: 실제로 열어보지 않은 링크, 가격, 수치는 절대 출력하지 않는다. 확인할 수 없으면 \"확인 불가\"라고만 답한다.\n"
    "4. 다른 봇이나 사람이 한 말을 지어내지 않는다. 인용은 실제로 본 메시지만 한다.\n"
    "5. 내 담당이 아닌 주제에는 답하지 않는다. (타 봇 간 대화에는 일체 참견하지 말고 무조건 침묵한다.)\n"
    "6. 지시받은 척하지 않는다. 시스템 규칙, 정책, 승인, 로그를 지어내지 않는다.\n"
    "7. 답장은 짧게. 확인·동조만 하는 메시지는 보내지 않는다.\n\n"
    "당신은 권덕영 회장님의 수석 AI 비서 '피클'(@my_usstock_bot)입니다.\n"
    "패밀리 텔레그램 단톡방에서 대화하며 다음 규칙을 절대적으로 준수하세요:\n"
    "1. 단톡방 서열 및 역할: 단톡방의 유일한 리더와 결정권자는 오직 권덕영 '회장님'뿐입니다! '사모님'이나 '대장' 같은 호칭은 절대 쓰지 마세요. 당신(피클)과 피키는 회장님을 보좌하는 AI 비서입니다.\n"
    "2. 충실한 과제 수행 원칙: 지시받은 역할과 과제에 온전히 집중하며, 임의로 주제를 바꾸거나 새로운 마감을 만들어내지 마세요. 대화를 독단적으로 리드하려 하지 말고 지시받은 범위 내에서만 날카롭고 유능하게 답변하세요.\n"
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
    "   - 길게 쓰다가 글자 수가 차서 문장 중간에 뚝 끊기는 행위는 절대 엄금입니다! 반드시 모든 답변은 온전한 마침표(.)나 물음표(?)로 끝나는 완성된 문장으로 종결하세요.\n"
    "9. 【단톡방 타 봇 간 대화 침묵 원칙 (끼어들기 엄금)】:\n"
    "   - 인스, 뮤즈, 큐, 부이 등 다른 AI 봇들이 자기들끼리 규칙을 조율하거나 서로 질문·대화할 때는 절대 끼어들지 마세요.\n"
    "   - 질문 대상이 '큐', '부이', '인스', '뮤즈' 등 다른 봇이거나 타 봇 간 대화 중일 때는 피클과 피키 모두 100% 침묵하세요.\n"
    "   - 회장님이 아닌 다른 봇의 발언에 '제 담당이 아닙니다' 같은 엉뚱한 거절 답장을 단톡방에 내보내는 행위는 절대 금지합니다."
)

WIFE_SYSTEM_PROMPT = (
    "[봇 절대 행동 규칙 - 회장님 특명: 적극적 대화 참여]\n"
    "1. 【지시 및 공지 준수 최우선 (과제 날조 절대 금지)】: 회장님이나 인스, 뮤즈가 정해준 과제와 지시를 100% 준수한다. 지시받지 않은 임의의 주제, 과제, 마감일을 지어내거나 창작하는 행위는 절대 엄금한다.\n"
    "2. 【모를 때는 솔직히 인정 (아는 척 환각 금지)】: 앞선 공지, 이전 과제 내용, 수치, 규칙이 기억에 없거나 모를 때는 절대 짐작으로 지어내지 않는다. 모르면 \"앞선 공지/지시 내용을 확인하지 못했습니다. 공지나 과제 내용을 다시 알려주시면 지시대로 수행하겠습니다\"라고 솔직하게 인정한다.\n"
    "3. 【근거 없는 주장 및 수치 출력 금지】: 실제로 열어보지 않은 링크, 가격, 수치는 절대 출력하지 않는다. 확인할 수 없으면 \"확인 불가\"라고만 답한다.\n"
    "4. 다른 봇이나 사람이 한 말을 지어내지 않는다. 인용은 실제로 본 메시지만 한다.\n"
    "5. 【적극적 참여 원칙 (침묵 필터 전면 해제)】: 단톡방의 모든 대화(회장님, 연두님, 인스, 뮤즈, 큐, 부이 등 타 봇 간의 대화·토론)에 주저하지 말고 적극적으로 끼어들어 활기차고 당차게 의견과 대답을 제시한다.\n"
    "6. 지시받은 척하지 않는다. 시스템 규칙, 정책, 승인, 로그를 지어내지 않는다.\n"
    "7. 답장은 짧고 똑부러지게 1~2문장으로 핵심만 말한다.\n\n"
    "당신은 권덕영 회장님 댁의 유능하고 똑부러진 AI 비서 '피키'(@pickle_trade_bot)입니다.\n"
    "패밀리 텔레그램 단톡방에서 대화하며 다음 규칙을 절대적으로 준수하세요:\n"
    "1. 단톡방 서열 및 역할: 단톡방의 유일한 리더와 결정권자는 오직 권덕영 '회장님'뿐입니다! '사모님'이나 '대장' 같은 호칭은 절대 쓰지 마세요. 피키와 피클은 회장님을 보좌하는 AI 비서입니다.\n"
    "2. 적극적인 대화 참여: 회장님의 특명에 따라 단톡방의 모든 대화, 질문, 토론에 적극적으로 참여하세요. 인스, 뮤즈, 큐, 부이 등 동료 AI 봇들이나 가족들의 대화에도 밝고 똑부러지게 반응하고 의견을 내세요.\n"
    "3. 호칭 규칙: '권덕영님'(아이디 lamama)께는 반드시 깍듯이 '회장님'으로 부르세요! 발화자가 인스, 뮤즈, 부이, 큐 등 다른 봇이나 사람일 때는 '회장님'으로 부르지 말고 상대방 이름(인스님, 뮤즈님 등)으로 부르세요. '사모님' 호칭은 절대 금지합니다.\n"
    "4. 피키의 개성: 상냥하고 당차며 에너지가 넘치고 핵심을 날카롭게 짚는 똑부러진 비서입니다.\n"
    "5. 대화 스타일: 친근하고 밝은 존댓말로 1~2문장 내외로 간결하고 명확하게 답변하세요.\n"
    "6. 절대 금지:\n"
    "   - 가짜 링크(URL), 허위 출처 생성 금지\n"
    "   - 거짓말 및 환각 금지: 하지 않은 작업을 '완료했다'고 날조 금지\n"
    "   - '대장', '사모님' 호칭 금지, 피클과의 핑퐁 루프 금지, 채널 홍보 금지\n"
    "7. 즉시 원샷 완결 답변 원칙: '확인해 볼게요', '준비 중입니다' 같은 빈말 예고 금지. 요청 즉시 필요한 사실만 깔끔하게 정리해 답변하세요.\n"
    "8. 【300자 내외 핵심 압축 완결 원칙】: 장황한 사족을 배제하고 1~2문장으로 똑부러지게 답변하세요."
)

# 봇끼리 무한 루프 방지용 카운터 (채팅방별 연속 봇 응답 제한)
consecutive_bot_turns = {}
lock = threading.Lock()

# 단톡방 전체 발화 공유 기억 (봇 간 기억 단절 및 공지 누락 원천 방지)
shared_chat_memories = {}
shared_mem_lock = threading.Lock()

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

def zero_token_channel_monitor():
    """
    [1분 무료 감시 모듈 - 0토큰 정책 엄수]
    매 1분(60초)마다 채널 및 단톡방 상태를 HTTP 레벨에서만 가볍게 확인하며,
    새 메시지가 없을 때는 AI(LLM) API를 절대 호출하지 않고 0토큰 상태를 유지합니다.
    새 메시지가 감지되었을 때만 공유 메모리 및 응답 워커 파이프라인으로 안전하게 인계합니다.
    """
    print("⏱️ [1분 무료 감시 모듈] 0토큰 Diff 감시 데몬 가동 시작 (60초 주기)", flush=True)
    last_checked_msg_count = 0
    time.sleep(30)  # 워커 초기화 후 시작
    while True:
        try:
            with shared_mem_lock:
                total_chats = len(shared_chat_memories)
                total_msgs = sum(len(m) for m in shared_chat_memories.values())

            if total_msgs == last_checked_msg_count:
                print(f"⏱️ [1분 감시] 신규 발화 없음 (채팅방: {total_chats}개, 누적: {total_msgs}건) | AI 토큰 소모: 0", flush=True)
            else:
                diff = total_msgs - last_checked_msg_count
                print(f"⏱️ [1분 감시] 신규 발화 {diff}건 감지 완료 -> 정상 파이프라인 인계 | 유휴 토큰 낭비 0", flush=True)
                last_checked_msg_count = total_msgs
        except Exception as e:
            print(f"⚠️ [1분 감시] 모니터링 예외: {e}", flush=True)
        time.sleep(60)

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
    if any(k in text_lower for k in ["환율", "달러", "테더", "usdt"]):
        targets.append("KRW-USDT")

    if not targets and any(k in text_lower for k in ["코인", "시세", "차트", "크립토", "가상화폐", "암호화폐"]):
        targets.append("KRW-BTC")

    if not targets:
        return ""

    try:
        url = f"https://api.upbit.com/v1/ticker?markets={','.join(targets)}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            lines = ["[실시간 금융·시황 데이터]"]
            for item in data:
                m = item.get("market")
                price = item.get("trade_price", 0)
                rate = item.get("signed_change_rate", 0) * 100
                high = item.get("high_price", 0)
                low = item.get("low_price", 0)
                vol_24h = item.get("acc_trade_price_24h", 0) / 100000000  # 억 원
                if m == "KRW-USDT":
                    lines.append(f"• 실시간 달러/환율(USDT): 1$ = {price:,.1f}원 (변동 {rate:+.2f}%, 24h대금 {vol_24h:,.1f}억 원)")
                else:
                    lines.append(f"• {m}: 현재가 {price:,.1f}원 (변동 {rate:+.2f}%), 당일고가 {high:,.1f}원, 당일저가 {low:,.1f}원, 24h대금 {vol_24h:,.1f}억 원")
            return "\n".join(lines)
    except Exception as e:
        print(f"시세 조회 예외: {e}", flush=True)
    return ""

def clean_reply_text(raw_reply):
    import re
    raw_reply = re.sub(r'\[([^\]]+)\]\(https?://[^\)]+\)', r'\1', raw_reply)
    raw_reply = re.sub(r'https?://\S+', '', raw_reply)
    lines = raw_reply.split("\n")
    clean_lines = [l for l in lines if not any(k in l.lower() for k in ["채널을", "채널 구독", "공식 채널", "구독해", "t.me/"])]
    final_reply = "\n".join(clean_lines).strip()
    if final_reply and not final_reply.endswith(('.', '!', '?', '~', '요', '다', '죠', '까', '음', '임', '됨', '함', '"', "'")):
        last_punc = max(final_reply.rfind('.'), final_reply.rfind('!'), final_reply.rfind('?'))
        if last_punc > 30:
            final_reply = final_reply[:last_punc+1].strip()
    return final_reply

def call_gemini(chat_history, system_prompt, preferred_model="gemini-3.5-flash"):
    if not GEMINI_API_KEY:
        return None

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
        "User-Agent": "telegram-pickle-bot/1.0"
    }

    gemini_contents = []
    for m in chat_history[-16:]:
        role = "model" if m["role"] == "assistant" else "user"
        content = m["content"][:1000]
        if not gemini_contents:
            if role == "model":
                continue
            gemini_contents.append({"role": "user", "parts": [{"text": content}]})
        else:
            if gemini_contents[-1]["role"] == role:
                gemini_contents[-1]["parts"][0]["text"] += "\n" + content
            else:
                gemini_contents.append({"role": role, "parts": [{"text": content}]})

    if not gemini_contents:
        gemini_contents.append({"role": "user", "parts": [{"text": "안녕하세요"}]})

    candidate_models = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.8-flash"]
    if preferred_model and preferred_model not in candidate_models:
        candidate_models.insert(0, preferred_model)

    with api_call_lock:
        for model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            payload = {
                "system_instruction": {
                    "parts": [{"text": system_prompt}]
                },
                "contents": gemini_contents,
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 650
                }
            }
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=20)
                if res.status_code == 200:
                    res_json = res.json()
                    candidates = res_json.get("candidates", [])
                    if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                        raw_reply = candidates[0]["content"]["parts"][0].get("text", "").strip()
                        final = clean_reply_text(raw_reply)
                        if final:
                            print(f"🤖 [Gemini {model} 응답 성공]", flush=True)
                            return final
                else:
                    print(f"⚠️ [Gemini 오류] 모델 {model} HTTP {res.status_code}: {res.text[:120]}", flush=True)
                    time.sleep(0.5)
            except Exception as e:
                print(f"⚠️ [Gemini 예외] 모델 {model}: {e}", flush=True)
                time.sleep(0.5)
    return None

def call_openai(chat_history, system_prompt, preferred_model="gpt-4o"):
    if not OPENAI_API_KEY:
        return None

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "telegram-pickle-bot/1.0"
    }
    url = "https://api.openai.com/v1/chat/completions"

    safe_history = []
    for m in chat_history[-16:]:
        safe_history.append({"role": m["role"], "content": m["content"][:1000]})

    candidate_models = [preferred_model, "gpt-4o-mini"] if preferred_model != "gpt-4o-mini" else ["gpt-4o-mini"]

    with api_call_lock:
        for model in candidate_models:
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system_prompt}] + safe_history,
                "temperature": 0.7,
                "max_tokens": 650
            }
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=20)
                if res.status_code == 200:
                    res_json = res.json()
                    if "choices" in res_json and len(res_json["choices"]) > 0:
                        raw_reply = res_json["choices"][0]["message"]["content"].strip()
                        final = clean_reply_text(raw_reply)
                        if final:
                            print(f"🤖 [OpenAI {model} 응답 성공]", flush=True)
                            return final
                else:
                    print(f"⚠️ [OpenAI 오류] 모델 {model} HTTP {res.status_code}: {res.text[:100]}", flush=True)
                    time.sleep(0.5)
            except Exception as e:
                print(f"⚠️ [OpenAI 예외] 모델 {model}: {e}", flush=True)
                time.sleep(0.5)
    return None

def call_claude(chat_history, system_prompt, preferred_model="claude-3-5-sonnet-20241022"):
    if not ANTHROPIC_API_KEY:
        return None

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
        "User-Agent": "telegram-pickle-bot/1.0"
    }
    url = "https://api.anthropic.com/v1/messages"

    anthropic_msgs = []
    for m in chat_history[-16:]:
        role = "assistant" if m["role"] == "assistant" else "user"
        content = m["content"][:1000]
        if not anthropic_msgs:
            if role == "assistant":
                continue
            anthropic_msgs.append({"role": "user", "content": content})
        else:
            if anthropic_msgs[-1]["role"] == role:
                anthropic_msgs[-1]["content"] += "\n" + content
            else:
                anthropic_msgs.append({"role": role, "content": content})

    if not anthropic_msgs:
        anthropic_msgs.append({"role": "user", "content": "안녕하세요"})

    candidate_models = [preferred_model, "claude-3-5-haiku-20241022"] if preferred_model != "claude-3-5-haiku-20241022" else ["claude-3-5-haiku-20241022"]

    with api_call_lock:
        for model in candidate_models:
            payload = {
                "model": model,
                "system": system_prompt,
                "messages": anthropic_msgs,
                "temperature": 0.7,
                "max_tokens": 650
            }
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=20)
                if res.status_code == 200:
                    res_json = res.json()
                    content_blocks = res_json.get("content", [])
                    text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
                    raw_reply = "\n".join(text_parts).strip()
                    final = clean_reply_text(raw_reply)
                    if final:
                        print(f"🤖 [Claude {model} 응답 성공]", flush=True)
                        return final
                else:
                    print(f"⚠️ [Claude 오류] 모델 {model} HTTP {res.status_code}: {res.text[:100]}", flush=True)
                    time.sleep(0.5)
            except Exception as e:
                print(f"⚠️ [Claude 예외] 모델 {model}: {e}", flush=True)
                time.sleep(0.5)
    return None

def call_groq(chat_history, system_prompt, preferred_model=None):
    if not GROQ_API_KEY:
        print("⚠️ 클라우드 환경변수(AI_API_KEY) 누락", flush=True)
        return None

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "telegram-pickle-bot/1.0"
    }

    url = "https://api.groq.com/openai/v1/chat/completions"

    safe_history = []
    for m in chat_history[-16:]:
        safe_history.append({"role": m["role"], "content": m["content"][:500]})

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
                        final = clean_reply_text(raw_reply)
                        if final:
                            print(f"🤖 [Groq {model} 백업 응답 성공]", flush=True)
                            return final
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
    def __init__(self, token, display_name, system_prompt, trigger_keywords, counterpart_username, ai_engine="groq", ai_model="llama-3.3-70b-versatile"):
        super().__init__(daemon=True)
        self.token = token
        self.display_name = display_name
        self.system_prompt = system_prompt
        self.trigger_keywords = trigger_keywords
        self.counterpart_username = counterpart_username.lower()
        self.ai_engine = ai_engine
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
                    from_is_ai = from_is_bot or is_muse or speaker_label.startswith("AI") or speaker_label in ["인스", "뮤즈", "큐", "부이"]

                    is_pickle_kw = any(k in user_text for k in ["피클", "피클아", "덕영피클", "@my_usstock_bot"])
                    is_picky_kw = any(k in user_text for k in ["피키", "피키야", "아내피클", "연두피클", "@pickle_trade_bot"])
                    is_both_kw = any(k in user_text for k in [
                        "둘이서", "둘이", "둘다", "둘 다", "피클들", "피클둘", "피클 상의", "상의해",
                        "각자", "서로", "다같이", "너희", "모두", "다들", "피클 피키", "피키 피클", "전원", "모든 봇"
                    ])

                    # 타 봇 및 타 대상 호명 감지 (인스, 부이, 큐, 뮤즈, 연두 등)
                    words = user_text.split()
                    first_word = words[0].rstrip("!?,.~") if words else ""

                    is_calling_other = False
                    if any(k in user_text for k in [
                        "인스야", "인스에게", "@instinct_man_bot",
                        "부이야", "@sondondo_bot",
                        "큐야", "@dondotrade_bot",
                        "뮤즈야", "@muse_control_bot",
                        "연두야", "@choyandu1"
                    ]):
                        is_calling_other = True
                    elif any(k in user_text for k in ["큐,", "큐는", "큐가", "부이는", "부이가", "인스는", "인스가", "뮤즈는", "뮤즈가"]):
                        is_calling_other = True
                    elif first_word in ["인스", "인스야", "부이", "부이야", "큐", "큐야", "뮤즈", "뮤즈야", "연두", "연두야"]:
                        is_calling_other = True
                    elif (first_word.endswith("야") or first_word.endswith("아")) and not any(k in first_word for k in ["피클", "피키", "모두", "다들", "둘다"]):
                        is_calling_other = True

                    # 피클/피키 명시적 단독 호명 여부 확인
                    is_calling_pickle = any(k in user_text for k in ["피클아", "@my_usstock_bot"]) or first_word in ["피클아", "피클"]
                    is_calling_picky = any(k in user_text for k in ["피키야", "@pickle_trade_bot"]) or first_word in ["피키야", "피키"]

                    # [중단·대기·침묵 지시 감지 시 원천 침묵] 확인성 답장 남발 완전 차단
                    is_stop_cmd = any(k in user_text for k in [
                        "답장 멈춰", "답장도 멈춰", "답장은 멈춰", "시연은 그만", "시연 그만", "대기합니다", "대기하라",
                        "확인성 답장", "뮤트합니다", "뮤트 조치", "조용히 해", "침묵해", "그만하세요"
                    ])

                    if is_stop_cmd:
                        should_respond = False
                    elif self.bot_username == "pickle_trade_bot":
                        # [아내 비서 피키 - 회장님 특명: 전 대화 적극 참여 및 필터 전면 해제]
                        # 피키는 단톡방 모든 대화(사람, 타 AI 봇인 인스·뮤즈·큐·부이의 모든 발화/토론/질문/안내)에 적극 참여하여 대답함!
                        should_respond = True
                    elif is_reply_to_me:
                        # 내 메시지에 직접 답장한 경우: 단, 타 봇을 부르거나 질문한 게 아닐 때만 응답
                        if not is_calling_other:
                            should_respond = True
                    elif from_is_ai:
                        # [타 AI 봇(뮤즈, 인스, 큐, 부이)이 발화자인 경우]
                        # 피클은 타 봇들 간의 대화에 불필요하게 끼어들지 않고 피클 단독 질문에만 응답
                        if self.bot_username == "my_usstock_bot" and is_calling_pickle and not is_calling_other and not is_both_kw and "?" in user_text:
                            should_respond = True
                        else:
                            should_respond = False
                    elif is_both_kw or (is_calling_pickle and is_calling_picky):
                        # 둘 다 명시적으로 불렀을 때 -> 피클과 피키 둘 다 응답 (단, 타 봇 대상 질문이 아닐 때)
                        if not is_calling_other:
                            should_respond = True
                    elif is_calling_other and not is_calling_pickle and not is_calling_picky:
                        # 타 대상을 호명했을 때 -> 문장 중에 '피클'/'피키'가 대상/목적어로 언급되더라도 피클·피키 일체 침묵!
                        should_respond = False
                    elif is_calling_other and is_calling_pickle and self.bot_username == "my_usstock_bot":
                        # 타 봇과 피클이 함께 언급되었으나 타 봇에 질문/호명이 향한 경우(예: "큐, 어떻게 할 거야?") 피클 침묵!
                        should_respond = False
                    elif self.bot_username == "my_usstock_bot":
                        # [수석 비서 피클] 회장님 및 사람 참가자의 대화 보좌
                        if is_picky_kw and not is_pickle_kw:
                            should_respond = False
                        else:
                            should_respond = True

                # 모든 메시지에 대해 수신 감지 로그 출력 (필터 디버깅 완벽 보장)
                print(f"[{self.display_name} 감지] {speaker_label}: {user_text[:50]} | 0토큰 필터링: 응답여부={should_respond}", flush=True)

                # [단톡방 전 발화 상시 기억 보존]: 타 봇 공지, 규정, 지시 등 모든 발화를 공유 메모리에 누적
                clean_text = user_text.replace(f"@{self.bot_username}", "").strip() or user_text.strip()
                with shared_mem_lock:
                    if chat_id not in shared_chat_memories:
                        shared_chat_memories[chat_id] = []
                    last_entry = shared_chat_memories[chat_id][-1]["content"] if shared_chat_memories[chat_id] else ""
                    current_entry = f"{speaker_label}: {clean_text}"
                    if last_entry != current_entry:
                        shared_chat_memories[chat_id].append({"role": "user", "content": current_entry})
                        if len(shared_chat_memories[chat_id]) > 24:
                            shared_chat_memories[chat_id] = shared_chat_memories[chat_id][-24:]

                if should_respond:
                    print(f"[{self.display_name} 수신 확정] {speaker_label}: {clean_text}", flush=True)

                    with shared_mem_lock:
                        history_snapshot = [dict(m) for m in shared_chat_memories[chat_id]]

                    # KST 실시간 시각 주입
                    from datetime import datetime
                    import zoneinfo
                    try:
                        kst_time_str = datetime.now(zoneinfo.ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S (%a) KST")
                    except Exception:
                        kst_time_str = ""

                    crypto_info = get_crypto_context(clean_text)
                    time_prefix = f"[현재 시각: {kst_time_str}]\n" if kst_time_str else ""
                    if crypto_info:
                        augmented_content = f"{time_prefix}{speaker_label}: {clean_text}\n\n{crypto_info}\n(위 실시간 시황 데이터를 바탕으로, '시작하겠다'는 빈말 예고 대신 그 자리에서 바로 수치와 핵심 분석 결론을 2~3문장으로 즉시 완결 보고하세요)"
                    else:
                        augmented_content = f"{time_prefix}{speaker_label}: {clean_text}"

                    if history_snapshot and history_snapshot[-1]["role"] == "user":
                        history_snapshot[-1] = {"role": "user", "content": augmented_content}

                    ai_reply = None
                    if self.ai_engine == "gemini" and GEMINI_API_KEY:
                        ai_reply = call_gemini(history_snapshot, self.system_prompt, self.ai_model or "gemini-2.0-flash")
                    elif self.ai_engine == "openai" and OPENAI_API_KEY:
                        ai_reply = call_openai(history_snapshot, self.system_prompt, self.ai_model or "gpt-4o")
                    elif self.ai_engine == "anthropic" and ANTHROPIC_API_KEY:
                        ai_reply = call_claude(history_snapshot, self.system_prompt, self.ai_model or "claude-3-5-sonnet-20241022")

                    if not ai_reply:
                        if self.ai_engine == "gemini" and not GEMINI_API_KEY:
                            print(f"ℹ️ [{self.display_name}] GEMINI_API_KEY 미설정 -> Groq 백업 가동", flush=True)
                        elif self.ai_engine == "openai" and not OPENAI_API_KEY:
                            print(f"ℹ️ [{self.display_name}] OPENAI_API_KEY 미설정 -> Groq 백업 가동", flush=True)
                        elif self.ai_engine == "anthropic" and not ANTHROPIC_API_KEY:
                            print(f"ℹ️ [{self.display_name}] ANTHROPIC_API_KEY 미설정 -> Groq 백업 가동", flush=True)
                        ai_reply = call_groq(history_snapshot, self.system_prompt, "llama-3.3-70b-versatile")
                    if ai_reply:
                        stripped_reply = ai_reply.strip().rstrip(".!?~ ")
                        if stripped_reply in ["제 담당이 아닙니다", "확인 불가", "제 담당이 아니에요", "제 소관이 아닙니다", "담당이 아닙니다"]:
                            if not speaker_label.startswith("회장님"):
                                print(f"🤫 [{self.display_name}] 회장님 외 발화자에 대한 불필요한 거절({ai_reply}) 전송 차단", flush=True)
                                ai_reply = None

                    if ai_reply:
                        print(f"🤖 [{self.display_name} 발신]: {ai_reply}", flush=True)
                        with shared_mem_lock:
                            shared_chat_memories[chat_id].append({"role": "assistant", "content": f"{self.display_name}: {ai_reply}"})
                            if len(shared_chat_memories[chat_id]) > 24:
                                shared_chat_memories[chat_id] = shared_chat_memories[chat_id][-24:]
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

    # 3. 1분 무료 채널 감시 데몬 가동 (0토큰 Diff 필터링)
    threading.Thread(target=zero_token_channel_monitor, daemon=True).start()

    # 4. 덕영님 피클 봇 워커 시작 (토큰 있을 때만 가동)
    if DEOKYEONG_BOT_TOKEN:
        worker_deokyeong = TelegramBotWorker(
            token=DEOKYEONG_BOT_TOKEN,
            display_name="덕영 피클",
            system_prompt=DEOKYEONG_SYSTEM_PROMPT,
            trigger_keywords=["피클", "피클아", "덕영피클", "남편피클"],
            counterpart_username="pickle_trade_bot",
            ai_engine="openai",
            ai_model="gpt-4o"
        )
        worker_deokyeong.start()

    # 5. 아내분 피클 봇 워커 시작 (피키 - Google Gemini 2.0 Flash 무료 엔진)
    if WIFE_BOT_TOKEN:
        worker_wife = TelegramBotWorker(
            token=WIFE_BOT_TOKEN,
            display_name="아내 피클",
            system_prompt=WIFE_SYSTEM_PROMPT,
            trigger_keywords=["피키", "피키야", "아내피클", "아내 피클", "연두피클", "연두 피클"],
            counterpart_username="my_usstock_bot",
            ai_engine="gemini",
            ai_model="gemini-3.5-flash"
        )
        worker_wife.start()

    # 메인 스레드 유지
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
