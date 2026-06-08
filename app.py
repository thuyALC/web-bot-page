import os
import random
from datetime import datetime
from flask import Flask, jsonify, render_template, request, session
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "khoa-bao-mat-tam-thoi-123")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash" 

def ask_ai(user_message: str, use_search: bool = True, chat_history: list = None) -> tuple[str, str, list]:
    if not GEMINI_API_KEY:
        return "Chưa cấu hình GEMINI_API_KEY.", "Lỗi hệ thống", chat_history
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
            return f"Lỗi Google: {res.text}", "Lỗi API", chat_history
            
        reply = res.json()["candidates"][0]["content"]["parts"][0]["text"]
        
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "model", "content": reply})
        return reply, "Đã phản hồi", chat_history
    except Exception as e:
        return f"Lỗi: {str(e)}", "Lỗi kỹ thuật", chat_history

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api/chat")
def chat():
    payload = request.get_json(force=True)
    message = payload.get("message", "").strip()
    history = session.get("chat_history", [])
    reply, status, new_history = ask_ai(message, True, history)
    session["chat_history"] = new_history
    return jsonify({"reply": reply})

@app.post("/api/ghost_story")
def ghost_story():
    topic = request.get_json(force=True).get("topic", "đêm khuya")
    prompt = f"Hãy viết một câu chuyện ma cực kỳ rùng rợn và bất ngờ về chủ đề: {topic}. Hãy dùng văn phong kể chuyện truyền cảm."
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=45)
        story = res.json()["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"story": story})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post("/api/clear")
def clear():
    session.clear()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
