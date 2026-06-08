import os
import json
import random
import unicodedata
import urllib.parse
from datetime import datetime
from flask import Flask, jsonify, render_template, request, session
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "khoa-bao-mat-tam-thoi-123")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash") 

# Bật lại chế độ tự động thử lại nếu Google quá tải
retry_strategy = Retry(
    total=3, 
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST", "GET"],
    backoff_factor=1
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)

def ask_ai(user_message: str, use_search: bool = True, chat_history: list = None) -> tuple[str, str, list]:
    if not GEMINI_API_KEY:
        return "Chưa cấu hình GEMINI_API_KEY.", "Lỗi hệ thống", chat_history
    if chat_history is None:
        chat_history = []

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    system_instruction = (
        "Bạn là trợ lý tiếng Việt, trả lời ngắn gọn, tự nhiên, đúng trọng tâm. "
        f"Thời gian hiện tại: {now_str}."
    )

    contents = []
    for msg in chat_history[-10:]:
        contents.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_instruction}]}
        }
        if use_search:
            payload["tools"] = [{"google_search": {}}]
        
        # Tăng thời gian chờ lên 30s để AI kịp lướt Google đọc tin tức
        res = http.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        res.raise_for_status()
        
        response_data = res.json()
        reply = response_data["candidates"][0]["content"]["parts"][0]["text"]
        
        grounding_meta = response_data["candidates"][0].get("groundingMetadata", {})
        used_google = bool(
            grounding_meta.get("webSearchQueries") or 
            grounding_meta.get("searchEntryPoint") or 
            grounding_meta.get("groundingChunks")
        )
        status_text = "Nối mạng Google Search" if used_google else ("Tắt mạng" if not use_search else "Dùng não")
        
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "model", "content": reply})
        
        return reply, status_text, chat_history
    except requests.exceptions.RequestException as e:
        return "Mạng nghẽn. Nếu mạng chậm quá, bạn thử TẮT dấu tích [Nối mạng web] rồi gửi lại xem sao nhé!", "Lỗi kết nối", chat_history

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api/chat")
def chat():
    payload = request.get_json(force=True)
    message = (payload.get("message") or "").strip()
    use_search = payload.get("search", True) is not False

    if not message:
        return jsonify({"error": "Nhập nội dung trước."}), 400

    history = session.get("chat_history", [])
    reply, search_status, new_history = ask_ai(message, use_search, history)
    session["chat_history"] = new_history
    return jsonify({"reply": reply, "search_status": search_status})


NGAN_HANG_CAU_DO = [
    {"emoji": "👄💄", "dapan": "son môi", "giaithich": "Cái môi + thỏi son"},
    {"emoji": "🌽🎤", "dapan": "bắp hát", "giaithich": "Trái bắp + cái micro"},
    {"emoji": "🐎🧊", "dapan": "ngựa đá", "giaithich": "Con ngựa + cục đá"},
    {"emoji": "🔥🍲", "dapan": "lẩu thái", "giaithich": "Lửa (cay nóng) + nồi lẩu"},
    {"emoji": "👁️📻", "dapan": "thị đài", "giaithich": "Mắt (thị) + cái đài"},
    {"emoji": "🐒🌲", "dapan": "khỉ leo cây", "giaithich": "Con khỉ + cái cây"},
    {"emoji": "🐮🎀", "dapan": "bò nơ", "giaithich": "Con bò + cái nơ (Bo-nớt)"},
    {"emoji": "☁️🌧️", "dapan": "mưa bóng mây", "giaithich": "Đám mây + trời mưa"},
    {"emoji": "⚽🥅", "dapan": "vào lưới", "giaithich": "Quả bóng + khung thành"},
    {"emoji": "🐸💧", "dapan": "ếch ngồi đáy giếng", "giaithich": "Con ếch + giọt nước"},
    {"emoji": "🐉🧚‍♀️", "dapan": "rồng bay phượng múa", "giaithich": "Con rồng + cô tiên bay"}
]

@app.post("/api/game/riddle")
def game_riddle():
    cau_do = random.choice(NGAN_HANG_CAU_DO)
    session["game_dapan"] = cau_do["dapan"]
    session["game_giaithich"] = cau_do["giaithich"]
    return jsonify({"emoji": cau_do["emoji"]})

@app.post("/api/game/guess")
def game_guess():
    payload = request.get_json(force=True)
    guess = (payload.get("guess") or "").strip().lower()
    dapan = session.get("game_dapan")
    giaithich = session.get("game_giaithich")
    
    if not dapan:
        return jsonify({"error": "Chưa có câu đố nào. Hãy lấy câu đố mới."}), 400
        
    def normalize_vn(text):
        return unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8').replace(" ", "")
        
    if normalize_vn(guess) == normalize_vn(dapan):
        session.pop("game_dapan", None)
        return jsonify({"correct": True, "message": f"Chính xác! Đáp án: {dapan.title()} ({giaithich})" })
    else:
        return jsonify({"correct": False, "message": "Sai rồi, đoán lại thử xem!"})

@app.post("/api/game/answer")
def game_answer():
    dapan = session.get("game_dapan")
    giaithich = session.get("game_giaithich")
    if not dapan:
        return jsonify({"error": "Chưa có câu đố nào đang chơi."}), 400
    
    session.pop("game_dapan", None)
    return jsonify({"message": f"Bó tay à? Đáp án là: {dapan.title()} ({giaithich})" })

@app.post("/api/clear")
def clear():
    session.pop("chat_history", None)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
