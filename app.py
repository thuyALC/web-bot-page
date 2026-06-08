import os
import requests
from datetime import datetime
from flask import Flask, jsonify, render_template, request
from duckduckgo_search import DDGS

app = Flask(__name__)

# Nhận key từ môi trường của Render
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "llama-3.3-70b-versatile")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

chat_history = []

def get_duckduckgo_data(query: str) -> str:
    try:
        results = DDGS().text(f"{query} tin tức", max_results=3)
        if not results:
            return ""
        formatted_results = [f"{r.get('title', '')}\n{r.get('body', '')}\nNguồn: {r.get('href', '')}" for r in results]
        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"Lỗi tìm kiếm: {str(e)}"

def ask_ai(user_message: str, web_data: str = "") -> str:
    if not GROQ_API_KEY:
        return "Chưa cấu hình GROQ_API_KEY trên server."

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    messages = [
        {
            "role": "system",
            "content": (
                "Ban la tro ly tieng Viet, tra loi ngan gon, dung trong tam. "
                "Neu co du lieu web, uu tien dung du lieu do. "
                f"Thoi gian hien tai: {now_str}."
            ),
        }
    ]

    if web_data:
        messages.append({"role": "system", "content": f"Du lieu tham khao:\n{web_data}"})

    messages.extend(chat_history[-10:])
    messages.append({"role": "user", "content": user_message})

    try:
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL_NAME, "messages": messages},
            timeout=25,
        )
        res.raise_for_status()
        reply = res.json()["choices"][0]["message"]["content"]
        chat_history.extend([{"role": "user", "content": user_message}, {"role": "assistant", "content": reply}])
        return reply
    except Exception as e:
        return f"Lỗi gọi API AI: {str(e)}"

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/api/chat")
def chat():
    payload = request.get_json(force=True)
    message = (payload.get("message") or "").strip()
    use_search = payload.get("search", True) is not False

    if not message:
        return jsonify({"error": "Nhập nội dung trước."}), 400

    try:
        web_data = get_duckduckgo_data(message) if use_search else ""
        search_status = "Đã lấy data web" if web_data and "Lỗi" not in web_data else "Tắt data/Không tìm thấy"
        return jsonify({"reply": ask_ai(message, web_data), "search_status": search_status})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.post("/api/sticker")
def create_sticker():
    payload = request.get_json(force=True)
    prompt = (payload.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"error": "Cần có mô tả."}), 400
    if not GEMINI_API_KEY:
         return jsonify({"error": "Chưa cấu hình GEMINI_API_KEY."}), 500

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-images:predict?key={GEMINI_API_KEY}"
        api_payload = {
            "instances": [{"prompt": f"Vector sticker style, clean die-cut edge, transparent background, {prompt}"}],
            "parameters": {"sampleCount": 1}
        }
        res = requests.post(url, json=api_payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        image_base64 = data['predictions'][0]['bytesBase64Encoded']
        return jsonify({"sticker_url": f"data:image/png;base64,{image_base64}"})
    except Exception as exc:
        return jsonify({"error": f"Lỗi: {str(exc)}"}), 500

@app.post("/api/video")
def create_video():
    payload = request.get_json(force=True)
    image_url = (payload.get("image_url") or "").strip()
    prompt = (payload.get("prompt") or "").strip()

    if not image_url or not prompt:
        return jsonify({"error": "Cần link ảnh và mô tả."}), 400
    if not GEMINI_API_KEY:
         return jsonify({"error": "Chưa cấu hình GEMINI_API_KEY."}), 500

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/veo-3.0-generate-video:predict?key={GEMINI_API_KEY}"
        api_payload = {
            "instances": [{"prompt": prompt, "image": {"url": image_url}}],
            "parameters": {"aspectRatio": "16:9"}
        }
        res = requests.post(url, json=api_payload, timeout=60)
        res.raise_for_status()
        return jsonify({"video_url": res.json()['predictions'][0]['videoUrl']})
    except Exception as exc:
        return jsonify({"error": f"Lỗi: {str(exc)}"}), 500

@app.post("/api/clear")
def clear():
    chat_history.clear()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))