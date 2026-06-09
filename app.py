import os
import requests
import urllib.parse
import xml.etree.ElementTree as ET
import re
from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "") 

GEMINI_MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"

def get_rss_news(query: str) -> str:
    if len(query) < 2: return ""
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=vi&gl=VN&ceid=VN:vi"
        res = requests.get(url, timeout=10)
        root = ET.fromstring(res.text)
        items = root.findall(".//item")[:3]
        return "\n".join([f"- {item.findtext('title')} ({item.findtext('link')})" for item in items])
    except: return ""

def ask_groq_fallback(user_message: str, use_search: bool, chat_history: list):
    if not GROQ_API_KEY:
        return "Gemini đang nghẽn. Lên Render thêm biến GROQ_API_KEY làm lốp dự phòng ngay nhé.", "Lỗi cạn API", chat_history
    
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
                return jsonify({"story": story_text + "\n\n*(Ghi chú: Máy chủ chính kẹt nên AI dự phòng kể tạm)*"})
        
        return jsonify({"error": "Máy chủ đang tắc đường, đéo ai rảnh kể truyện. Vui lòng thử lại sau!"}), 500
    except Exception as e:
        return jsonify({"error": f"Lỗi kỹ thuật: {str(e)}"}), 500

@app.post("/api/read_url")
def read_url():
    payload = request.get_json(force=True)
    url = payload.get("url", "").strip()
    if not url: return jsonify({"error": "Chưa nhập link truyện."}), 400
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.5"
        }
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, "html.parser")
        title = soup.title.string if soup.title else "Không rõ tiêu đề"
        
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'button', 'form', 'noscript']):
            tag.decompose()
        
        content = ""
        target_classes = ['chapter-c', 'chapter-content', 'noidung', 'story-detail-content', 'chuong-c', 'noidungchuong']
        content_divs = soup.find_all('div', class_=target_classes)
        
        if content_divs:
            main_div = max(content_divs, key=lambda d: len(d.get_text()))
            for br in main_div.find_all("br"):
                br.replace_with("\n")
            content = main_div.get_text(separator="\n", strip=True)
        else:
            for br in soup.find_all("br"):
                br.replace_with("\n")
            paragraphs = soup.find_all('p')
            if paragraphs:
                content = "\n".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
            else:
                content = soup.get_text(separator='\n', strip=True)
        
        content = re.sub(r'\n\s*\n', '\n\n', content)
        
        if len(content) < 150:
            return jsonify({"error": "Bị Cloudflare chặn mõm hoặc web không có chữ."}), 400
            
        return jsonify({"title": title, "content": content})
    except Exception as e:
        return jsonify({"error": f"Lỗi cào web: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
