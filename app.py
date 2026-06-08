import os
from datetime import datetime
from flask import Flask, jsonify, render_template, request, session
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)
# Đặt secret key để mã hóa session (giúp lưu lịch sử chat riêng cho từng user)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "khoa-bao-mat-tam-thoi-123")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash") 

# Cấu hình tự động thử lại nếu server Google quá tải (Lỗi 503, 429)
retry_strategy = Retry(
    total=3,  # Thử lại tối đa 3 lần
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST", "GET"],
    backoff_factor=2 # Đợi 2s, 4s, 8s giữa các lần thử
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)

def ask_ai(user_message: str, use_search: bool = True, chat_history: list = None) -> tuple[str, str, list]:
    if not GEMINI_API_KEY:
        return "Chưa cấu hình GEMINI_API_KEY trên server.", "Lỗi hệ thống", chat_history

    if chat_history is None:
        chat_history = []

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
        
        # Đã fix lỗi: API yêu cầu dùng "google_search" thay vì "googleSearch"
        if use_search:
            payload["tools"] = [{"google_search": {}}]
        
        res = http.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        res.raise_for_status()
        
        response_data = res.json()
        reply = response_data["candidates"][0]["content"]["parts"][0]["text"]
        
        # Cập nhật điều kiện check xem AI có dùng data mạng thật không
        grounding_meta = response_data["candidates"][0].get("groundingMetadata", {})
        used_google = bool(
            grounding_meta.get("webSearchQueries") or 
            grounding_meta.get("searchEntryPoint") or 
            grounding_meta.get("groundingChunks")
        )
        status_text = "Nối mạng Google Search" if used_google else ("Tắt mạng" if not use_search else "Dùng não")
        
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "model", "content": reply})
        
        return reply, status_text, chat_history
    except requests.exceptions.RequestException as e:
        err_msg = "Google đang quá tải hoặc mạng có vấn đề. Bạn chờ xíu rồi gửi lại nhé."
        if hasattr(e, 'response') and e.response is not None:
            print(f"Lỗi API AI: {e.response.text}") # Ghi log ẩn thay vì in lỗi cho user
        return err_msg, "Lỗi kết nối", chat_history

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

    # Lấy lịch sử chat của user hiện tại
    history = session.get("chat_history", [])
    
    reply, search_status, new_history = ask_ai(message, use_search, history)
    
    # Cập nhật lại lịch sử vào session
    session["chat_history"] = new_history
    
    return jsonify({"reply": reply, "search_status": search_status})

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
        res = http.post(url, json=api_payload, timeout=40)
        res.raise_for_status()
        data = res.json()
        image_base64 = data['predictions'][0]['bytesBase64Encoded']
        return jsonify({"sticker_url": f"data:image/png;base64,{image_base64}"})
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            print(f"Lỗi Imagen: {e.response.text}")
            if e.response.status_code == 400:
                return jsonify({"error": "Mô tả vi phạm chính sách hoặc quá ngắn. Hãy thử mô tả khác rõ ràng hơn!"}), 400
        return jsonify({"error": "Lỗi tạo ảnh. Vui lòng thử lại sau."}), 500

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
        res = http.post(url, json=api_payload, timeout=30)
        res.raise_for_status()
        
        operation_name = res.json().get("name")
        return jsonify({"operation": operation_name})
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            print(f"Lỗi Veo Start: {e.response.text}")
            if e.response.status_code == 429:
                return jsonify({"error": "Đã hết lượt tạo video (Rate Limit). Vui lòng thử lại sau."}), 429
        return jsonify({"error": "Không thể bắt đầu tạo video."}), 500

@app.post("/api/video/status")
def check_video():
    payload = request.get_json(force=True)
    op_name = payload.get("operation")
    
    if not op_name:
        return jsonify({"error": "Thiếu mã tiến trình."}), 400
        
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/{op_name}?key={GEMINI_API_KEY}"
        res = http.get(url, timeout=20)
        res.raise_for_status()
        data = res.json()
        
        if data.get("done"):
            if "error" in data:
                return jsonify({"error": data["error"].get("message", "Lỗi tạo video từ Google.")}), 500
            uri = data["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
            return jsonify({"done": True, "video_url": uri})
        else:
            return jsonify({"done": False})
    except Exception as exc:
        print(f"Lỗi check video status: {exc}")
        return jsonify({"error": "Lỗi kiểm tra trạng thái video."}), 500

@app.post("/api/clear")
def clear():
    session.pop("chat_history", None)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
