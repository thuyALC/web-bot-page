import os
import random
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, jsonify, render_template, request, session
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "khoa-bao-mat-tam-thoi-123")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "") 

GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"

def get_rss_news(query: str) -> str:
    """Cào Google News làm mắt cho Groq"""
    if len(query) < 2: return ""
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=vi&gl=VN&ceid=VN:vi"
        res = requests.get(url, timeout=10)
        root = ET.fromstring(res.text)
        items = root.findall(".//item")[:3]
        return "\n".join([f"- {item.findtext('title')} ({item.findtext('link')})" for item in items])
    except: return ""

def ask_groq_fallback(user_message: str, use_search: bool, chat_history: list):
    """Groq làm lốp dự phòng khi Gemini lỗi"""
    if not GROQ_API_KEY:
        return "Gemini đang quá tải. Hãy thêm GROQ_API_KEY trên Render làm dự phòng.", "Lỗi API", chat_history
    
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    sys_msg = f"Bạn là trợ lý tiếng Việt. Trả lời ngắn gọn, tự nhiên. Thời gian hiện tại: {now_str}."
    status_text = "Dùng não (Groq Cứu Hộ)"
    
    if use_search:
        news = get_rss_news(user_message)
        if news:
            sys_msg += f"\nTin tức tham khảo:\n{news}"
            status_text = "Đọc báo RSS (Groq Cứu Hộ)"
    
    messages = [{"role": "system", "content": sys_msg}]
    for msg in chat_history[-10:]:
        role = "assistant" if msg["role"] == "model" else msg["role"]
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})
    
    try:
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={"model": GROQ_MODEL, "messages": messages},
            timeout=30
        )
        if res.status_code == 200:
            reply = res.json()["choices"][0]["message"]["content"]
            chat_history.append({"role": "user", "content": user_message})
            chat_history.append({"role": "model", "content": reply})
            return reply, status_text, chat_history
        return f"Lỗi Groq: {res.text}", "Lỗi API Dự phòng", chat_history
    except Exception as e:
        return f"Mất kết nối Groq: {str(e)}", "Toang", chat_history

def ask_ai(user_message: str, use_search: bool = True, chat_history: list = None):
    """Hàm AI Chính (Gemini)"""
    if chat_history is None: chat_history = []
    if not GEMINI_API_KEY: return "Chưa cấu hình GEMINI_API_KEY.", "Lỗi hệ thống", chat_history

    contents = [{"role": msg["role"], "parts": [{"text": msg["content"]}]} for msg in chat_history[-10:]]
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": contents}
        if use_search: payload["tools"] = [{"googleSearch": {}}] 

        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        
        # Nhảy sang lốp dự phòng nếu Gemini sập hoặc báo Quota
        if res.status_code != 200:
            return ask_groq_fallback(user_message, use_search, chat_history)

        data = res.json()
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        
        grounding_meta = data["candidates"][0].get("groundingMetadata", {})
        used_google = bool(grounding_meta.get("searchEntryPoint") or grounding_meta.get("groundingChunks"))
        status = "Nối mạng Google (Gemini)" if used_google else "Dùng não (Gemini)"

        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "model", "content": reply})
        return reply, status, chat_history
    except Exception:
        return ask_groq_fallback(user_message, use_search, chat_history)

@app.get("/")
def index(): 
    return render_template("index.html")

@app.post("/api/chat")
def chat():
    payload = request.get_json(force=True)
    message = (payload.get("message") or "").strip()
    use_search = payload.get("search", True) is not False
    history = session.get("chat_history", [])

    if not message: return jsonify({"error": "Nhập nội dung"}), 400
    reply, search_status, new_history = ask_ai(message, use_search, history)
    session["chat_history"] = new_history
    return jsonify({"reply": reply, "search_status": search_status})

@app.post("/api/get_lyrics")
def get_lyrics():
    payload = request.get_json(force=True)
    query = payload.get("query", "").strip()
    if not query: return jsonify({"error": "Chưa nhập tên bài hát."}), 400
    
    prompt = f"Hãy tìm và cung cấp lời bài hát (lyrics) dựa trên thông tin sau: '{query}'. Cho biết tên bài hát và ca sĩ trước khi in lời."
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        res = requests.post(url, json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]}, timeout=30)
        if res.status_code == 200:
            return jsonify({"lyrics": res.json()["candidates"][0]["content"]["parts"][0]["text"]})
            
        if GROQ_API_KEY:
            g_res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}]}, timeout=30
            )
            if g_res.status_code == 200:
                return jsonify({"lyrics": g_res.json()["choices"][0]["message"]["content"]})
        return jsonify({"error": "Máy chủ đang bận, vui lòng thử lại sau."}), 500
    except Exception as e:
        return jsonify({"error": f"Lỗi: {str(e)}"}), 500

@app.post("/api/ghost_story")
def ghost_story():
    topic = request.get_json(force=True).get("topic", "đêm khuya").strip()
    prompt = f"Sáng tác truyện ma ngắn rùng rợn về: {topic}."
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        res = requests.post(url, json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]}, timeout=30)
        if res.status_code == 200:
            return jsonify({"story": res.json()["candidates"][0]["content"]["parts"][0]["text"]})
            
        if GROQ_API_KEY:
            g_res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}]}, timeout=30
            )
            if g_res.status_code == 200:
                return jsonify({"story": g_res.json()["choices"][0]["message"]["content"]})
        return jsonify({"error": "Máy chủ đang tắc đường, thử lại sau!"}), 500
    except Exception as e:
        return jsonify({"error": f"Lỗi: {str(e)}"}), 500

# ================= TRÒ CHƠI ĐUỔI HÌNH BẮT CHỮ LOCAL =================
NGAN_HANG_CAU_DO = [
    {"emoji": "👄💄", "dapan": "son môi", "giaithich": "Cái môi + thỏi son"},
    {"emoji": "🌽🎤", "dapan": "bắp hát", "giaithich": "Trái bắp + micro"},
    {"emoji": "🐎🧊", "dapan": "ngựa đá", "giaithich": "Con ngựa + cục đá"},
    {"emoji": "🔥🍲", "dapan": "lẩu thái", "giaithich": "Lửa (cay nóng) + nồi lẩu"},
    {"emoji": "👁️📻", "dapan": "thị đài", "giaithich": "Mắt (thị) + cái đài"},
    {"emoji": "🐒🌲", "dapan": "khỉ leo cây", "giaithich": "Con khỉ + cái cây"},
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
    return jsonify({"correct": False, "message": "Sai rồi, thử lại nhé!"})

@app.post("/api/game/answer")
def game_answer():
    dapan = session.get("game_dapan", "")
    giaithich = session.get("game_giaithich", "")
    if not dapan: return jsonify({"error": "Chưa có câu đố đang chơi."}), 400
    session.pop("game_dapan", None)
    return jsonify({"message": f"Đáp án là: {dapan.title()} ({giaithich})"})

@app.post("/api/clear")
def clear():
    session.clear()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
