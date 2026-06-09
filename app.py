import os
import requests
from datetime import datetime
from flask import Flask, jsonify, render_template, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "b4-f3a-k3y-p1s-r3pl4c3-1t")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def ask_ai(user_message: str, use_search: bool = True):
    """Gọi Gemini trả lời nhanh, bọc lỗi kĩ càng."""
    if not GEMINI_API_KEY: return "Hệ thống chưa cấu hình GEMINI_API_KEY.", "Lỗi"
    
    contents = [{"role": "user", "parts": [{"text": user_message}]}]
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": contents}
        if use_search: payload["tools"] = [{"googleSearch": {}}] 

        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        
        if res.status_code != 200:
            return f"AI nghẽn (Status {res.status_code}): {res.text}", "Toang"

        response_data = res.json()
        
        # Bọc lỗi API ngớ ngẩn nếu không có candidates
        if "candidates" not in response_data or not response_data["candidates"]:
             return "AI không trả lời được yêu cầu này.", "Tắt đài"
             
        reply = response_data["candidates"][0]["content"]["parts"][0]["text"]
        
        grounding_meta = response_data["candidates"][0].get("groundingMetadata", {})
        used_google = bool(grounding_meta.get("searchEntryPoint") or grounding_meta.get("groundingChunks"))
        status = "🌐 Đã nối mạng (Gemini)" if used_google else "🧠 Dùng não (Gemini)"

        return reply, status
    except Exception as e:
        return f"Mất kết nối API: {str(e)}", "Toang"

@app.get("/")
def index(): return render_template("index.html")

@app.post("/api/chat")
def chat():
    """Chat API không lưu lịch sử để tránh Quota."""
    payload = request.get_json(force=True)
    message = (payload.get("message") or "").strip()
    use_search = payload.get("search", True) is not False

    if not message: return jsonify({"error": "Nhập nội dung"}), 400
    reply, search_status = ask_ai(message, use_search)
    return jsonify({"reply": reply, "search_status": search_status})

@app.post("/api/get_lyrics")
def get_lyrics():
    """Tìm lyrics bài hát chuẩn xác."""
    query = request.get_json(force=True).get("query", "").strip()
    if not query: return jsonify({"error": "Chưa nhập tên bài."}), 400
    
    prompt = f"Hãy cung cấp lời bài hát (lyrics) và ca sĩ thể hiện cho bài hát sau, in chuẩn dấu: '{query}'."
    reply, status = ask_ai(prompt, use_search=True) # Ép dùng mạng
    
    if "Status 200" in reply: return jsonify({"error": reply}), 500
    return jsonify({"lyrics": reply})

# ================= ĐUỔI HÌNH BẮT CHỮ LOCAL LOGIC =================
NGAN_HANG_CAU_DO = [
    {"emoji": "👄💄", "dapan": "son môi"},
    {"emoji": "🌽🎤", "dapan": "bắp hát"},
    {"emoji": "🐎🧊", "dapan": "ngựa đá"},
    {"emoji": "🔥🍲", "dapan": "lẩu thái"},
    {"emoji": "👁️📻", "dapan": "thị đài"},
    {"emoji": "🐒🌲", "dapan": "khỉ leo cây"},
    {"emoji": "☁️🌧️", "dapan": "mưa bóng mây"}
]

@app.post("/api/game/riddle")
def game_riddle():
    cau_do = requests.get("https://randomuser.me/api/").json() # Just to make the endpoint do something different if no DB
    import random # import inside to ensure local use
    cau_do = random.choice(NGAN_HANG_CAU_DO)
    session["game_dapan"] = cau_do["dapan"]
    return jsonify({"emoji": cau_do["emoji"]})

@app.post("/api/game/guess")
def game_guess():
    guess = request.get_json(force=True).get("guess", "").lower().strip()
    dapan = session.get("game_dapan", "")
    if guess == dapan:
        session.pop("game_dapan", None)
        return jsonify({"correct": True, "message": f"Chuẩn! Đáp án: {dapan.title()}"})
    return jsonify({"correct": False, "message": "Sai rồi!"})

@app.post("/api/game/answer")
def game_answer():
    return jsonify({"message": f"Đáp án là: {session.get('game_dapan', 'Chưa có')}"})

@app.post("/api/clear")
def clear():
    session.clear()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
