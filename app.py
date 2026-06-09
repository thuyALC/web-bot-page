import os
import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash" 

def ask_ai(user_message: str, use_search: bool = True, chat_history: list = None):
    if not GEMINI_API_KEY:
        return "Chưa cấu hình GEMINI_API_KEY trên Render.", "Lỗi hệ thống", chat_history
    if chat_history is None:
        chat_history = []

    contents = []
    for msg in chat_history[-10:]:
        contents.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": contents}
        if use_search:
            payload["tools"] = [{"googleSearch": {}}] 

        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=45)

        if res.status_code != 200:
            err_msg = res.json().get("error", {}).get("message", res.text)
            return f"Lỗi từ Google: {err_msg}", "Lỗi API", chat_history

        response_data = res.json()
        reply = response_data["candidates"][0]["content"]["parts"][0]["text"]

        grounding_meta = response_data["candidates"][0].get("groundingMetadata", {})
        used_google = bool(grounding_meta.get("searchEntryPoint") or grounding_meta.get("groundingChunks"))
        status_text = "Nối mạng Google Search" if used_google else "Dùng não (Không cần mạng)"

        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "model", "content": reply})

        return reply, status_text, chat_history
    except Exception as e:
        return f"Lỗi kỹ thuật: {str(e)}", "Lỗi Code", chat_history

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api/chat")
def chat():
    payload = request.get_json(force=True)
    message = (payload.get("message") or "").strip()
    use_search = payload.get("search", True) is not False
    history = payload.get("history", [])

    if not message:
        return jsonify({"error": "Nhập nội dung trước đã bạn ơi."}), 400

    reply, search_status, new_history = ask_ai(message, use_search, history)
    return jsonify({"reply": reply, "search_status": search_status, "history": new_history})

@app.post("/api/ghost_story")
def ghost_story():
    payload = request.get_json(force=True)
    topic = (payload.get("topic") or "đêm khuya").strip()
    if not GEMINI_API_KEY:
        return jsonify({"error": "Chưa cấu hình GEMINI_API_KEY."}), 500

    prompt = f"Hãy sáng tác một câu chuyện ma ngắn thật rùng rợn, bất ngờ và ám ảnh về chủ đề: {topic}. Giọng văn cuốn hút, rợn gáy."

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
        api_payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        res = requests.post(url, json=api_payload, headers={"Content-Type": "application/json"}, timeout=45)

        if res.status_code != 200:
            err_msg = res.json().get("error", {}).get("message", res.text)
            return jsonify({"error": f"Lỗi API Google: {err_msg}"}), 500

        story = res.json()["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"story": story})
    except Exception as e:
        return jsonify({"error": f"Lỗi kỹ thuật: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
