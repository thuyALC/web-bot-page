import os
import json
import random
import unicodedata
from datetime import datetime
from flask import Flask, jsonify, render_template, request, session
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "khoa-bao-mat-tam-thoi-123")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash") 

def ask_ai(user_message: str, use_search: bool = True, chat_history: list = None) -> tuple[str, str, list]:
    if not GEMINI_API_KEY:
        return "Hệ thống chưa được cấu hình API Key.", "Lỗi hệ thống", chat_history
    if chat_history is None: chat_history = []

    contents = []
    for msg in chat_history[-10:]:
        contents.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": contents}
        if use_search:
            payload["tools"] = [{"google_search": {}}]
        
        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=45)
        if res.status_code != 200:
            err_msg = res.json().get("error", {}).get("message", "Lỗi không xác định")
            return f"Lỗi từ máy chủ: {err_msg}", "Lỗi API", chat_history
            
        response_data = res.json()
        reply = response_data["candidates"][0]["content"]["parts"][0]["text"]
        
        grounding_meta = response_data["candidates"][0].get("groundingMetadata", {})
        used_google = bool(
            grounding_meta.get("webSearchQueries") or 
            grounding_meta.get("searchEntryPoint") or 
            grounding_meta.get("groundingChunks")
        )
        
        if used_google:
            status_text = "🌐 Dữ liệu cập nhật từ Google Search"
        else:
            status_text = "🧠 Dữ liệu nội bộ từ AI"
            
        if not use_search:
            status_text = "⚡ Đang ở chế độ Offline (Dùng não)"
            
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "model", "content": reply})
        return reply, status_text, chat_history
    except requests.exceptions.RequestException as e:
        return f"Mạng nghẽn hoặc lỗi kết nối: {str(e)}", "Lỗi Mạng", chat_history
    except Exception as e:
        return f"Lỗi kỹ thuật: {str(e)}", "Lỗi Code", chat_history

@app.get("/")
def index(): 
    return render_template("index.html")

@app.post("/api/chat")
def chat():
    payload = request.get_json(force=True)
    message = payload.get("message", "").strip()
    use_search = payload.get("search", True)
    if not message: return jsonify({"error": "Vui lòng nhập nội dung"}), 400
    
    history = session.get("chat_history", [])
    reply, status, new_history = ask_ai(message, use_search, history)
    session["chat_history"] = new_history
    return jsonify({"reply": reply, "search_status": status})

@app.post("/api/ghost_story")
def ghost_story():
    topic = request.get_json(force=True).get("topic", "đêm khuya")
    prompt = f"Hãy viết một câu chuyện ma rùng rợn, giật gân, bất ngờ và cuốn hút về chủ đề: {topic}. Viết chi tiết, dài khoảng 300 chữ, văn phong trôi chảy đậm chất kể chuyện."
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=45)
        story = res.json()["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"story": story})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================= TRÒ CHƠI =================
NGAN_HANG_CAU_DO = [
    {"emoji": "👄💄", "dapan": "son môi", "giaithich": "Cái môi + thỏi son"},
    {"emoji": "🌽🎤", "dapan": "bắp hát", "giaithich": "Trái bắp + micro"},
    {"emoji": "🐎🧊", "dapan": "ngựa đá", "giaithich": "Con ngựa + cục đá"},
    {"emoji": "🔥🍲", "dapan": "lẩu thái", "giaithich": "Lửa (cay nóng) + nồi lẩu"},
    {"emoji": "👁️📻", "dapan": "thị đài", "giaithich": "Mắt (thị) + cái đài"},
    {"emoji": "🐒🌲", "dapan": "khỉ leo cây", "giaithich": "Con khỉ + cái cây"},
    {"emoji": "🐮🎀", "dapan": "bò nơ", "giaithich": "Con bò + cái nơ"},
    {"emoji": "☁️🌧️", "dapan": "mưa bóng mây", "giaithich": "Đám mây + trời mưa"},
    {"emoji": "⚽🥅", "dapan": "vào lưới", "giaithich": "Quả bóng + khung thành"}
]

@app.post("/api/game/riddle")
def game_riddle():
    cau_do = random.choice(NGAN_HANG_CAU_DO)
    session["game_dapan"] = cau_do["dapan"]
    session["game_giaithich"] = cau_do["giaithich"]
    return jsonify({"emoji": cau_do["emoji"]})

@app.post("/api/game/guess")
def game_guess():
    guess = request.get_json(force=True).get("guess", "").lower()
    dapan = session.get("game_dapan", "")
    if not dapan: return jsonify({"error": "Vui lòng lấy câu đố mới."}), 400
    
    def normalize_vn(text):
        return unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8').replace(" ", "")
        
    if normalize_vn(guess) == normalize_vn(dapan):
        giaithich = session.pop("game_giaithich", "")
        session.pop("game_dapan", None)
        return jsonify({"correct": True, "message": f"Chính xác! Đáp án: {dapan.title()} ({giaithich})"})
    return jsonify({"correct": False, "message": "Sai rồi, đoán lại thử xem!"})

@app.post("/api/game/answer")
def game_answer():
    dapan = session.get("game_dapan", "")
    giaithich = session.get("game_giaithich", "")
    if not dapan: return jsonify({"error": "Chưa có câu đố nào đang chơi."}), 400
    session.pop("game_dapan", None)
    return jsonify({"message": f"Bó tay à? Đáp án là: {dapan.title()} ({giaithich})"})

@app.post("/api/clear")
def clear():
    session.clear()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
