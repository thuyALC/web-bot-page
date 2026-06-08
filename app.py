import os
import json
import unicodedata
from datetime import datetime
from flask import Flask, jsonify, render_template, request, session
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "khoa-bao-mat-tam-thoi-123")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash") 

retry_strategy = Retry(
    total=3, 
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST", "GET"],
    backoff_factor=2
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
        return "Mạng nghẽn hoặc Google quá tải. Đợi tí thử lại nha.", "Lỗi kết nối", chat_history

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

@app.post("/api/sticker")
def create_sticker():
    payload = request.get_json(force=True)
    prompt = (payload.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"error": "Cần có mô tả."}), 400
    if not GEMINI_API_KEY:
         return jsonify({"error": "Chưa cấu hình API Key."}), 500

    try:
        # Quay lại chuẩn REST API chính xác của Google AI Studio
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}"
        api_payload = {
            "instances": [{"prompt": f"Vector sticker style, clean die-cut edge, transparent background, {prompt}"}],
            "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}
        }
        res = http.post(url, json=api_payload, timeout=40)
        
        # Bắt lỗi rõ ràng nếu Google từ chối lệnh
        if res.status_code != 200:
            err_data = res.json()
            err_msg = err_data.get("error", {}).get("message", "Lỗi tạo ảnh")
            return jsonify({"error": f"Google từ chối vì: {err_msg}"}), 400

        data = res.json()
        image_base64 = data["predictions"][0]["bytesBase64Encoded"]
        return jsonify({"sticker_url": f"data:image/png;base64,{image_base64}"})
    except Exception as e:
        return jsonify({"error": f"Lỗi kết nối: {str(e)}"}), 500

# ================= TÍNH NĂNG TRÒ CHƠI =================
@app.post("/api/game/riddle")
def game_riddle():
    if not GEMINI_API_KEY:
        return jsonify({"error": "Chưa cấu hình API Key."}), 500
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
        prompt = """Bạn là quản trò chơi Đuổi Hình Bắt Chữ tiếng Việt.
        Hãy tạo một câu đố bằng 2-3 Emoji. 
        Ví dụ: 🌽🎤 -> bắp hát, 🐎🧊 -> ngựa đá.
        Chỉ trả về JSON với cấu trúc: {"emoji": "...", "dapan": "...", "giaithich": "..."}"""
        
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        res = http.post(url, json=payload, timeout=20)
        res.raise_for_status()
        
        data = res.json()
        riddle_json = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
        
        session["game_dapan"] = riddle_json["dapan"].strip().lower()
        session["game_giaithich"] = riddle_json["giaithich"]
        return jsonify({"emoji": riddle_json["emoji"]})
    except Exception as e:
        return jsonify({"error": "AI đang bí ý tưởng. Nhấn lấy câu đố lại nhé!"}), 500

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

@app.post("/api/clear")
def clear():
    session.pop("chat_history", None)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
