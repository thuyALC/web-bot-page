import os
import requests
from datetime import datetime
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash") 

chat_history = []

def ask_ai(user_message: str, use_search: bool = True) -> tuple[str, str]:
    """Gọi thẳng API Gemini, tự động xài Google Search xịn nếu bật"""
    if not GEMINI_API_KEY:
        return "Chưa cấu hình GEMINI_API_KEY trên server.", "Lỗi hệ thống"

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    system_instruction = (
        "Bạn là trợ lý tiếng Việt, trả lời ngắn gọn, tự nhiên, đúng trọng tâm. "
        f"Thời gian hiện tại: {now_str}."
    )

    contents = []
    for msg in chat_history[-10:]:
        contents.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
        
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_instruction}]}
        }
        
        # ĐÂY CHÍNH LÀ BÍ QUYẾT: Kích hoạt Google Search chính chủ cho API
        if use_search:
            payload["tools"] = [{"googleSearch": {}}]
        
        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=25)
        res.raise_for_status()
        
        response_data = res.json()
        reply = response_data["candidates"][0]["content"]["parts"][0]["text"]
        
        # Check xem AI có thực sự xài Google không để báo ra giao diện
        grounding_meta = response_data["candidates"][0].get("groundingMetadata", {})
        used_google = bool(grounding_meta.get("searchEntryPoint") or grounding_meta.get("groundingChunks"))
        
        status_text = "Nối mạng Google Search" if used_google else ("Tắt mạng" if not use_search else "Dùng não (Không cần search)")
        
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "model", "content": reply})
        
        return reply, status_text
    except Exception as e:
        err_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            err_msg += f" | {e.response.text}"
        return f"Lỗi gọi AI: {err_msg}", "Lỗi mạng"

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
        reply, search_status = ask_ai(message, use_search)
        return jsonify({"reply": reply, "search_status": search_status})
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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}"
        api_payload = {
            "instances": [{"prompt": f"Vector sticker style, clean die-cut edge, transparent background, {prompt}"}],
            "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}
        }
        res = requests.post(url, json=api_payload, timeout=30)
        res.raise_for_status()
        data = res.json()
        image_base64 = data['predictions'][0]['bytesBase64Encoded']
        return jsonify({"sticker_url": f"data:image/png;base64,{image_base64}"})
    except Exception as exc:
        return jsonify({"error": f"Lỗi Imagen: {str(exc)}"}), 500

@app.post("/api/video/start")
def start_video():
    payload = request.get_json(force=True)
    prompt = (payload.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"error": "Cần mô tả để làm video."}), 400
    if not GEMINI_API_KEY:
         return jsonify({"error": "Chưa cấu hình GEMINI_API_KEY."}), 500

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/veo-3.1-generate-preview:predictLongRunning?key={GEMINI_API_KEY}"
        api_payload = {"instances": [{"prompt": prompt}]}
        res = requests.post(url, json=api_payload, timeout=30)
        res.raise_for_status()
        
        operation_name = res.json().get("name")
        return jsonify({"operation": operation_name})
    except Exception as exc:
        return jsonify({"error": f"Lỗi Veo: {str(exc)}"}), 500

@app.post("/api/video/status")
def check_video():
    payload = request.get_json(force=True)
    op_name = payload.get("operation")
    
    if not op_name:
        return jsonify({"error": "Thiếu mã tiến trình."}), 400
        
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/{op_name}?key={GEMINI_API_KEY}"
        res = requests.get(url, timeout=20)
        res.raise_for_status()
        data = res.json()
        
        if data.get("done"):
            uri = data["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
            return jsonify({"done": True, "video_url": uri})
        else:
            return jsonify({"done": False})
    except Exception as exc:
        return jsonify({"error": f"Lỗi lúc check status: {str(exc)}"}), 500

@app.post("/api/clear")
def clear():
    chat_history.clear()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))