import os
import random
from datetime import datetime
from flask import Flask, jsonify, render_template, request
import requests

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash" 

# Biến lưu trạng thái game toàn cục (thay cho session để không bao giờ lỗi)
game_data = {"dapan": "", "giaithich": ""}
chat_history = []

def ask_ai(user_message, use_search=True):
    if not GEMINI_API_KEY: return "Chưa cấu hình GEMINI_API_KEY.", "Lỗi"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"role": "user", "parts": [{"text": user_message}]}]}
    if use_search: payload["tools"] = [{"google_search": {}}]
    
    try:
        res = requests.post(url, json=payload, timeout=30).json()
        return res["candidates"][0]["content"]["parts"][0]["text"], "Đã xử lý"
    except: return "Lỗi AI rồi bạn ơi.", "Lỗi"

@app.get("/")
def index(): return render_template("index.html")

@app.post("/api/chat")
def chat():
    data = request.get_json()
    reply, status = ask_ai(data["message"], data.get("search", True))
    return jsonify({"reply": reply, "search_status": status})

@app.post("/api/ghost_story")
def ghost():
    topic = request.get_json().get("topic", "đêm khuya")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    res = requests.post(url, json={"contents": [{"parts": [{"text": f"Kể truyện ma về: {topic}"}]}]}, timeout=30)
    return jsonify({"story": res.json()["candidates"][0]["content"]["parts"][0]["text"]})

@app.post("/api/game/riddle")
def riddle():
    NGAN_HANG = [
        {"emoji": "👄💄", "dapan": "son môi", "giai": "Cái môi + thỏi son"},
        {"emoji": "🐎🧊", "dapan": "ngựa đá", "giai": "Con ngựa + cục đá"}
    ]
    cau = random.choice(NGAN_HANG)
    game_data["dapan"] = cau["dapan"]
    game_data["giai"] = cau["giai"]
    return jsonify({"emoji": cau["emoji"]})

@app.post("/api/game/guess")
def guess():
    user_guess = request.get_json().get("guess", "").lower()
    if user_guess == game_data["dapan"]:
        return jsonify({"correct": True, "message": f"Đúng! {game_data['giai']}"})
    return jsonify({"correct": False, "message": "Sai rồi!"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
