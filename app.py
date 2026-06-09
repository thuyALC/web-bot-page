import os
import requests
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

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
    """Lốp dự phòng: Xài Groq + RSS khi Gemini quá tải"""
    if not GROQ_API_KEY:
        return "Gemini đang nghẽn. Hãy lên Render thêm biến GROQ_API_KEY làm lốp dự phòng để bot không sập nhé.", "Lỗi cạn API", chat_history
    
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    sys_msg = f"Bạn là trợ lý tiếng Việt. Trả lời ngắn gọn, tự nhiên. Thời gian: {now_str}."
    
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
        return f"Groq cũng báo lỗi: {res.text}", "Toang cả 2 AI", chat_history
    except Exception as e:
        return f"Lỗi Groq Fallback: {str(e)}", "Toang", chat_history

def ask_ai(user_message: str, use_search: bool = True, chat_history: list = None):
    """Hàm AI Chính (Ưu tiên Gemini)"""
    if chat_history is None: chat_history = []
    if not GEMINI_API_KEY: return "Chưa cấu hình GEMINI_API_KEY.", "Lỗi", chat_history

    contents = [{"role": msg["role"], "parts": [{"text": msg["content"]}]} for msg in chat_history[-10:]]
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": contents}
        if use_search: payload["tools"] = [{"googleSearch": {}}] 

        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)

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
    history = payload.get("history", [])

    if not message: return jsonify({"error": "Nhập nội dung"}), 400
    reply, search_status, new_history = ask_ai(message, use_search, history)
    return jsonify({"reply": reply, "search_status": search_status, "history": new_history})

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
                json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}]},
                timeout=30
            )
            if g_res.status_code == 200:
                story_text = g_res.json()["choices"][0]["message"]["content"]
                return jsonify({"story": story_text + "\n\n*(Ghi chú: Truyện này do AI dự phòng kể do máy chủ chính tắc đường)*"})
        
        return jsonify({"error": "Máy chủ đang tắc đường, đéo ai rảnh kể truyện. Vui lòng thử lại sau 1 phút!"}), 500
    except Exception as e:
        return jsonify({"error": f"Lỗi kỹ thuật: {str(e)}"}), 500

# ================= ĐỔI HÀM ĐỌC TRUYỆN THÀNH TÌM LỜI BÀI HÁT =================
@app.post("/api/get_lyrics")
def get_lyrics():
    payload = request.get_json(force=True)
    query = payload.get("query", "").strip()
    if not query: return jsonify({"error": "Chưa nhập tên bài hát hoặc câu hát."}), 400
    
    prompt = f"Hãy tìm và cung cấp lời bài hát (lyrics) dựa trên thông tin sau: '{query}'. Nếu đây là một câu hát, hãy cho biết tên bài hát và ca sĩ trình bày trước khi in ra toàn bộ lời bài hát."
    
    try:
        # Gọi Gemini
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        res = requests.post(url, json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]}, timeout=30)
        
        if res.status_code == 200:
            return jsonify({"lyrics": res.json()["candidates"][0]["content"]["parts"][0]["text"]})
            
        # Fallback qua Groq nếu Gemini hết quota
        if GROQ_API_KEY:
            g_res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}]},
                timeout=30
            )
            if g_res.status_code == 200:
                return jsonify({"lyrics": g_res.json()["choices"][0]["message"]["content"]})
                
        return jsonify({"error": "Máy chủ đang bận, vui lòng thử lại sau nhé."}), 500
    except Exception as e:
        return jsonify({"error": f"Lỗi tìm kiếm: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
