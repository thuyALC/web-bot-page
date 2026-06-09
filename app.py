import os
from flask import Flask, jsonify, render_template, request
import requests

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash" 

@app.get("/")
def index(): return render_template("index.html")

@app.post("/api/chat")
def chat():
    data = request.get_json()
    message = data.get("message", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"role": "user", "parts": [{"text": message}]}]}
    if data.get("search"): payload["tools"] = [{"google_search": {}}]
    
    try:
        res = requests.post(url, json=payload, timeout=30).json()
        return jsonify({"reply": res["candidates"][0]["content"]["parts"][0]["text"]})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.post("/api/ghost_story")
def ghost():
    topic = request.get_json().get("topic", "đêm khuya")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    res = requests.post(url, json={"contents": [{"parts": [{"text": f"Kể truyện ma rùng rợn về: {topic}"}]}]}, timeout=30)
    return jsonify({"story": res.json()["candidates"][0]["content"]["parts"][0]["text"]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
