import os
import json
import random
import unicodedata
import urllib.parse
import re
from datetime import datetime
import xml.etree.ElementTree as ET
from flask import Flask, jsonify, render_template, request, session
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "khoa-bao-mat-tam-thoi-123")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Tự động nhận Llama 3.3 xịn nhất. XÓA BIẾN MODEL_NAME TRÊN RENDER ĐI NHÉ!
MODEL_NAME = os.environ.get("MODEL_NAME", "llama-3.3-70b-versatile") 

def get_web_data(query: str) -> str:
    if len(query) < 2:
        return ""
    try:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=vi&gl=VN&ceid=VN:vi"
        res = requests.get(url, timeout=10)
        root = ET.fromstring(res.text)
        items = root.findall(".//item")[:3]
        if not items:
            return ""
        results = [f"{item.findtext('title')} (Nguồn: {item.findtext('link')})" for item in items]
        return "\n\n".join(results)
    except Exception:
        return ""

def ask_ai(user_message: str, use_search: bool = True, chat_history: list = None) -> tuple[str, str, list]:
    if not GROQ_API_KEY:
        return "Chưa cấu hình GROQ_API_KEY trên server.", "Lỗi hệ thống", chat_history
    if chat_history is None:
        chat_history = []

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    system_instruction = (
        "Bạn là trợ lý tiếng Việt. Hãy trả lời ngắn gọn, tự nhiên, đúng trọng tâm. "
        f"Thời gian hiện tại: {now_str}."
    )

    web_data = ""
    search_status = "Dùng não (Tắt mạng)"
    if use_search:
        web_data = get_web_data(user_message)
        if web_data:
            system_instruction += f"\n\nTin tức mới nhất để tham khảo:\n{web_data}"
            search_status = "Đã cào Google News"
        else:
            search_status = "Không tìm thấy data web"

    messages = [{"role": "system", "content": system_instruction}]
    for msg in chat_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": MODEL_NAME,
            "messages": messages
        }
        res = requests.post(url, headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json=payload, timeout=45)
        
        if res.status_code != 200:
            err_data = res.json()
            return f"Lỗi từ Groq: {err_data}", "Lỗi API", chat_history
            
        reply = res.json()["choices"][0]["message"]["content"]
        
        reply_clean = re.sub(r'<think>.*?</think>', '', reply, flags=re.DOTALL).strip()
        if not reply_clean:
            reply_clean = reply
        
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": reply_clean})
        
        return reply_clean, search_status, chat_history
    except requests.exceptions.RequestException as e:
        return f"Lỗi kết nối máy chủ: {str(e)}", "Lỗi Timeout", chat_history
    except Exception as e:
        return f"Lỗi kỹ thuật: {str(e)}", "Lỗi Code", chat_history

@app.get("/")
def index():
    # Phóng thẳng HF_TOKEN xuống cho trình duyệt tự lấy để vẽ ảnh
    return render_template("index.html", hf_token=HF_TOKEN)

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
