import os
import requests
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "b4-f3a-k3y-p1s-r3pl4c3-1t")

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

def ask_groq_fallback(user_message: str, use_search: bool):
    """Lốp dự phòng: Xài Groq + RSS khi Gemini quá tải/hết Quota"""
    if not GROQ_API_KEY:
        return "Gemini báo hết Quota/Lỗi, mà bạn lại chưa cấu hình GROQ_API_KEY trên Render để làm dự phòng!", "Toang Toàn Tập"
    
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    sys_msg = f"Bạn là trợ lý tiếng Việt. Trả lời ngắn gọn, tự nhiên. Thời gian: {now_str}."
    status_text = "🧠 Dùng não (Groq Cứu Hộ)"
    
    if use_search:
        news = get_rss_news(user_message)
        if news:
            sys_msg += f"\nTin tức tham khảo:\n{news}"
            status_text = "🌐 Đọc báo RSS (Groq Cứu Hộ)"
    
    try:
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": GROQ_MODEL, 
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_message}
                ]
            },
            timeout=30
        )
        if res.status_code == 200:
            reply = res.json()["choices"][0]["message"]["content"]
            return reply, status_text
            
        return f"Gemini sập, gọi Groq cũng báo lỗi: {res.text}", "Toang Groq"
    except Exception as e:
        return f"Lỗi gọi Groq dự phòng: {str(e)}", "Lỗi Mạng"

def ask_ai(user_message: str, use_search: bool = True):
    """Hàm AI Chính (Ưu tiên Gemini, xịt thì nhảy ngay sang Groq)"""
    if not GEMINI_API_KEY: return "Hệ thống chưa cấu hình GEMINI_API_KEY.", "Lỗi"
    
    contents = [{"role": "user", "parts": [{"text": user_message}]}]
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": contents}
        if use_search: payload["tools"] = [{"googleSearch": {}}] 

        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        
        # CHÌA KHÓA Ở ĐÂY: Nếu Gemini trả về 429 Quota Exceeded hoặc bất kỳ lỗi nào, ĐÁ SANG GROQ
        if res.status_code != 200:
            return ask_groq_fallback(user_message, use_search)

        response_data = res.json()
        if "candidates" not in response_data or not response_data["candidates"]:
             return ask_groq_fallback(user_message, use_search)
             
        reply = response_data["candidates"][0]["content"]["parts"][0]["text"]
        
        grounding_meta = response_data["candidates"][0].get("groundingMetadata", {})
        used_google = bool(grounding_meta.get("searchEntryPoint") or grounding_meta.get("groundingChunks"))
        status = "🌐 Đã nối mạng (Gemini)" if used_google else "🧠 Dùng não (Gemini)"

        return reply, status
    except Exception:
        # Lỗi timeout hoặc đứt mạng, thử gọi Groq vớt vát
        return ask_groq_fallback(user_message, use_search)

@app.get("/")
def index(): return render_template("index.html")

@app.post("/api/chat")
def chat():
    payload = request.get_json(force=True)
    message = (payload.get("message") or "").strip()
    use_search = payload.get("search", True) is not False

    if not message: return jsonify({"error": "Nhập nội dung"}), 400
    reply, search_status = ask_ai(message, use_search)
    return jsonify({"reply": reply, "search_status": search_status})

@app.post("/api/get_lyrics")
def get_lyrics():
    query = request.get_json(force=True).get("query", "").strip()
    if not query: return jsonify({"error": "Chưa nhập tên bài hát."}), 400
    
    prompt = f"Hãy cung cấp lời bài hát (lyrics) và ca sĩ thể hiện cho bài hát/câu hát sau: '{query}'."
    reply, status = ask_ai(prompt, use_search=True) 
    
    if "Toang" in status or "Lỗi" in status: 
        return jsonify({"error": reply}), 500
    return jsonify({"lyrics": reply})

@app.post("/api/ghost_story")
def ghost_story():
    topic = request.get_json(force=True).get("topic", "đêm khuya").strip()
    prompt = f"Sáng tác truyện ma ngắn rùng rợn về: {topic}."
    reply, status = ask_ai(prompt, use_search=False)
    
    if "Toang" in status or "Lỗi" in status: 
        return jsonify({"error": reply}), 500
    return jsonify({"story": reply})

# ================= ĐUỔI HÌNH BẮT CHỮ LOCAL LOGIC =================
import random
NGAN_HANG_CAU_DO = [
    {"emoji": "👄💄", "dapan": "son môi"},
    {"emoji": "🌽🎤", "dapan": "bắp hát"},
    {"emoji": "🐎🧊", "dapan": "ngựa đá"},
    {"emoji": "🔥🍲", "dapan": "lẩu thái"},
    {"emoji": "👁️📻", "dapan": "thị đài"},
    {"emoji": "🐒🌲", "dapan": "khỉ leo cây"},
    {"emoji": "☁️🌧️", "dapan": "mưa bóng mây"}
]
# Dùng bộ nhớ tạm global thay vì session để chống sập khi Render khởi động lại
game_memory = {}

@app.post("/api/game/riddle")
def game_riddle():
    cau_do = random.choice(NGAN_HANG_CAU_DO)
    user_ip = request.remote_addr
    game_memory[user_ip] = cau_do["dapan"]
    return jsonify({"emoji": cau_do["emoji"]})

@app.post("/api/game/guess")
def game_guess():
    guess = request.get_json(force=True).get("guess", "").lower().strip()
    user_ip = request.remote_addr
    dapan = game_memory.get(user_ip, "")
    
    if not dapan: return jsonify({"error": "Bấm Lấy câu đố trước đã."}), 400
    
    if guess == dapan:
        game_memory.pop(user_ip, None)
        return jsonify({"correct": True, "message": f"Chuẩn! Đáp án: {dapan.title()}"})
    return jsonify({"correct": False, "message": "Sai rồi!"})

@app.post("/api/game/answer")
def game_answer():
    user_ip = request.remote_addr
    dapan = game_memory.get(user_ip, "")
    if not dapan: return jsonify({"error": "Chưa có câu đố đang chơi."}), 400
    game_memory.pop(user_ip, None)
    return jsonify({"message": f"Đáp án là: {dapan.title()}"})

@app.post("/api/clear")
def clear():
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
