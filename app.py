import os
import json
import random
import unicodedata
import urllib.parse
import base64
from datetime import datetime
from flask import Flask, jsonify, render_template, request, session
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "khoa-bao-mat-tam-thoi-123")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# Đã nâng cấp model lên bản 2.5-flash vì 1.5-flash bị Google ngừng hỗ trợ
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash") 

def ask_ai(user_message: str, use_search: bool = True, chat_history: list = None) -> tuple[str, str, list]:
    if not GEMINI_API_KEY:
        return "Chưa cấu hình GEMINI_API_KEY.", "Lỗi hệ thống", chat_history
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
        if use_search:
            payload["tools"] = [{"google_search": {}}]
        
        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=45)
        
        if res.status_code != 200:
            err_data = res.json()
            err_msg = err_data.get("error", {}).get("message", str(res.text))
            return f"Lỗi từ Google: {err_msg}", "Lỗi API", chat_history
            
        response_data = res.json()
        reply = response_data["candidates"][0]["content"]["parts"][0]["text"]
        
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
        return f"Lỗi kết nối máy chủ: {str(e)}", "Lỗi Timeout", chat_history
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

    if not message:
        return jsonify({"error": "Nhập nội dung trước."}), 400

    history = session.get("chat_history", [])
    reply, search_status, new_history = ask_ai(message, use_search, history)
    session["chat_history"] = new_history
    return jsonify({"reply": reply, "search_status": search_status})


# ================= STICKER VỚI GEMINI 2.5 FLASH IMAGE =================
@app.post("/api/sticker")
def create_sticker():
    payload = request.get_json(force=True)
    prompt = (payload.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"error": "Cần có mô tả."}), 400
    if not GEMINI_API_KEY:
        return jsonify({"error": "Chưa cấu hình GEMINI_API_KEY."}), 500

    try:
        # Sử dụng model gemini-2.5-flash-image chuyên tạo ảnh của Google bằng API Key hiện tại
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={GEMINI_API_KEY}"
        
        sticker_prompt = f"Cute 2D vector sticker, clean white die-cut border, flat design, isolated on white background, {prompt}"
        api_payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": sticker_prompt}]
                }
            ]
        }
        
        res = requests.post(url, json=api_payload, headers={"Content-Type": "application/json"}, timeout=45)
        
        if res.status_code != 200:
            err_data = res.json()
            err_msg = err_data.get("error", {}).get("message", str(res.text))
            return jsonify({"error": f"Lỗi Google Image: {err_msg}"}), 500
            
        data = res.json()
        
        try:
            parts = data["candidates"][0]["content"]["parts"]
            image_part = next((p for p in parts if "inlineData" in p), None)
            
            if image_part:
                img_b64 = image_part["inlineData"]["data"]
                mime_type = image_part["inlineData"].get("mimeType", "image/png")
                return jsonify({"sticker_url": f"data:{mime_type};base64,{img_b64}"})
            else:
                text_msg = parts[0].get("text", "Không tạo được ảnh (có thể do từ khóa nhạy cảm).")
                return jsonify({"error": f"AI từ chối: {text_msg}"}), 400
                
        except (KeyError, IndexError):
            return jsonify({"error": "Dữ liệu ảnh trả về bị lỗi định dạng."}), 500

    except Exception as e:
        return jsonify({"error": f"Lỗi kỹ thuật: {str(e)}"}), 500


# ================= TRÒ CHƠI =================
NGAN_HANG_CAU_DO = [
    {"emoji": "👄💄", "dapan": "son môi", "giaithich": "Cái môi + thỏi son"},
    {"emoji": "🌽🎤", "dapan": "bắp hát", "giaithich": "Trái bắp + cái micro"},
    {"emoji": "🐎🧊", "dapan": "ngựa đá", "giaithich": "Con ngựa + cục đá"},
    {"emoji": "🔥🍲", "dapan": "lẩu thái", "giaithich": "Lửa (cay nóng) + nồi lẩu"},
    {"emoji": "👁️📻", "dapan": "thị đài", "giaithich": "Mắt (thị) + cái đài"},
    {"emoji": "🐒🌲", "dapan": "khỉ leo cây", "giaithich": "Con khỉ + cái cây"},
    {"emoji": "🐮🎀", "dapan": "bò nơ", "giaithich": "Con bò + cái nơ (Bo-nớt)"},
    {"emoji": "☁️🌧️", "dapan": "mưa bóng mây", "giaithich": "Đám mây + trời mưa"},
    {"emoji": "⚽🥅", "dapan": "vào lưới", "giaithich": "Quả bóng + khung thành"},
    {"emoji": "🐸💧", "dapan": "ếch ngồi đáy giếng", "giaithich": "Con ếch + giọt nước"},
    {"emoji": "🐉🧚‍♀️", "dapan": "rồng bay phượng múa", "giaithich": "Con rồng + cô tiên bay"}
]

@app.post("/api/game/riddle")
def game_riddle():
    cau_do = random.choice(NGAN_HANG_CAU_DO)
    session["game_dapan"] = cau_do["dapan"]
    session["game_giaithich"] = cau_do["giaithich"]
    return jsonify({"emoji": cau_do["emoji"]})

@app.post("/api/game/guess")
def game_guess():
    payload = request.get_json(force=True)
    guess = (payload.get("guess") or "").strip().lower()
    dapan = session.get("game_dapan")
    giaithich = session.get("game_giaithich")
    
    if not dapan:
        return jsonify({"error": "Chưa có câu đố nào. Hãy lấy câu đố mới."}), 400
        
    def normalize_vn(text):
        return unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8').replace(" ", "")
        
    if normalize_vn(guess) == normalize_vn(dapan):
        session.pop("game_dapan", None)
        return jsonify({"correct": True, "message": f"Chính xác! Đáp án: {dapan.title()} ({giaithich})" })
    else:
        return jsonify({"correct": False, "message": "Sai rồi, đoán lại thử xem!"})

@app.post("/api/game/answer")
def game_answer():
    dapan = session.get("game_dapan")
    giaithich = session.get("game_giaithich")
    if not dapan:
        return jsonify({"error": "Chưa có câu đố nào đang chơi."}), 400
    
    session.pop("game_dapan", None)
    return jsonify({"message": f"Bó tay à? Đáp án là: {dapan.title()} ({giaithich})" })

@app.post("/api/clear")
def clear():
    session.pop("chat_history", None)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
