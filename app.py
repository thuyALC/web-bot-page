import json
import os
import random
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "b4-f3a-k3y-p1s-r3pl4c3-1t")

# ── API Keys ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY      = os.environ.get("GEMINI_API_KEY", "").strip()
OPENROUTER_API_KEY  = os.environ.get("OPENROUTER_API_KEY", "").strip()
GITHUB_TOKEN        = os.environ.get("GITHUB_TOKEN", "").strip()
TAVILY_API_KEY      = os.environ.get("TAVILY_API_KEY", "").strip()

GEMINI_MODEL        = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
OPENROUTER_MODEL    = os.environ.get("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free")
GITHUB_MODEL        = os.environ.get("GITHUB_MODEL", "gpt-4o-mini")

# ── Gemini Tool định nghĩa ────────────────────────────────────────────────────
HERMES_TOOL_NAME = "tavily_search"
HERMES_TOOL = {
    "functionDeclarations": [
        {
            "name": HERMES_TOOL_NAME,
            "description": (
                "Search for fresh news, current data, prices, schedules, or recent events."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Search query."},
                    "locale": {"type": "STRING", "description": "Locale, e.g. vi-VN."},
                },
                "required": ["query"],
            },
        }
    ]
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def now_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

def system_prompt_vi() -> str:
    return (
        "Bạn là trợ lý tiếng Việt thông minh. Trả lời đầy đủ, chi tiết, có cấu trúc rõ ràng. "
        "Giải thích kỹ, dùng ví dụ cụ thể khi cần, không bỏ sót thông tin quan trọng. "
        f"Thời gian hiện tại: {now_str()}. "
        "Khi cần tin tức / dữ liệu mới hãy gọi tool tavily_search. "
        "Câu hỏi kiến thức chung thì tự trả lời, không cần gọi tool."
    )

def extract_text_openai_style(data: dict) -> str:
    """Parse response dạng OpenAI (OpenRouter / GitHub Models)."""
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""

def extract_text_from_gemini(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()

# ── Tavily Search ─────────────────────────────────────────────────────────────
def call_tavily(query: str) -> dict:
    if not TAVILY_API_KEY:
        return {"ok": False, "error": "Chưa cấu hình TAVILY_API_KEY."}
    try:
        res = requests.post(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "include_answer": True,
                "max_results": 5,
            },
            timeout=20,
        )
        if res.status_code != 200:
            return {"ok": False, "error": f"Tavily lỗi {res.status_code}."}
        data = res.json()
        answer = data.get("answer", "")
        results = data.get("results", [])
        if not answer and results:
            snippets = [
                f"- {r.get('title','')}: {r.get('content','')[:200]}"
                for r in results[:3]
            ]
            answer = "\n".join(snippets)
        return {"ok": True, "data": {"answer": answer, "sources": results}}
    except Exception as exc:
        return {"ok": False, "error": f"Lỗi Tavily: {exc}"}

def tavily_answer(query: str) -> tuple[str, str]:
    r = call_tavily(query)
    if r.get("ok"):
        data = r["data"]
        return data.get("answer") or json.dumps(data, ensure_ascii=False), "Tavily Search"
    return r.get("error", "Tavily không trả về dữ liệu."), "Lỗi Tavily"

# ── OpenRouter fallback ───────────────────────────────────────────────────────
def ask_openrouter(message: str) -> tuple[str, str]:
    if not OPENROUTER_API_KEY:
        return "", "skip"
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://ai-workspace.app",
                "X-Title": "AI Workspace",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt_vi()},
                    {"role": "user", "content": message},
                ],
                "max_tokens": 2048,
            },
            timeout=30,
        )
        if res.status_code != 200:
            return "", "skip"
        reply = extract_text_openai_style(res.json())
        if reply:
            return reply, f"OpenRouter ({OPENROUTER_MODEL.split('/')[-1]})"
        return "", "skip"
    except Exception:
        return "", "skip"

# ── GitHub Models fallback ────────────────────────────────────────────────────
def ask_github_models(message: str) -> tuple[str, str]:
    if not GITHUB_TOKEN:
        return "", "skip"
    try:
        res = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "model": GITHUB_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt_vi()},
                    {"role": "user", "content": message},
                ],
                "max_tokens": 2048,
            },
            timeout=30,
        )
        if res.status_code != 200:
            return "", "skip"
        reply = extract_text_openai_style(res.json())
        if reply:
            return reply, f"GitHub Models ({GITHUB_MODEL})"
        return "", "skip"
    except Exception:
        return "", "skip"

# ── Fallback chain khi Gemini lỗi ────────────────────────────────────────────
def ai_fallback(message: str, gemini_err: str) -> tuple[str, str]:
    """Thử lần lượt: GitHub Models → OpenRouter → Tavily."""
    reply, status = ask_github_models(message)
    if status != "skip":
        return reply, status

    reply, status = ask_openrouter(message)
    if status != "skip":
        return reply, status

    reply, status = tavily_answer(message)
    if "Lỗi" not in status:
        return reply, "Tavily Search (Gemini quá tải)"

    return gemini_err, "Lỗi – Tất cả dịch vụ không khả dụng"

# ── Gemini (main) ─────────────────────────────────────────────────────────────
def ask_ai(user_message: str, use_search: bool = True) -> tuple[str, str]:
    if not GEMINI_API_KEY:
        return ai_fallback(user_message, "Chưa cấu hình GEMINI_API_KEY.")

    gemini_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    contents = [
        {
            "role": "user",
            "parts": [{"text": f"{system_prompt_vi()}\n\nNgười dùng: {user_message}"}],
        }
    ]

    try:
        payload = {"contents": contents}
        if use_search:
            payload["tools"] = [HERMES_TOOL]

        res = requests.post(
            gemini_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if res.status_code != 200:
            if res.status_code == 429:
                err = "Gemini quá hạn mức (429)."
            elif res.status_code in (401, 403):
                err = "API key Gemini không hợp lệ."
            elif res.status_code >= 500:
                err = "Máy chủ Gemini lỗi 5xx."
            else:
                err = f"Gemini lỗi {res.status_code}."
            return ai_fallback(user_message, err)

        response_data = res.json()
        candidates = response_data.get("candidates") or []
        if not candidates:
            return ai_fallback(user_message, "Gemini không trả về candidates.")

        candidate_content = candidates[0].get("content", {})
        parts = candidate_content.get("parts", [])
        function_call = next(
            (p.get("functionCall") for p in parts if p.get("functionCall")), None
        )

        # Gemini muốn gọi Tavily tool
        if function_call and function_call.get("name") == HERMES_TOOL_NAME:
            args = function_call.get("args") or {}
            q = args.get("query") or user_message
            tavily_result = call_tavily(q)

            contents.append(candidate_content)
            contents.append({
                "role": "function",
                "parts": [{
                    "functionResponse": {
                        "name": HERMES_TOOL_NAME,
                        "response": tavily_result,
                    }
                }],
            })

            final_res = requests.post(
                gemini_url,
                json={"contents": contents, "tools": [HERMES_TOOL]},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if final_res.status_code == 200:
                final_reply = extract_text_from_gemini(final_res.json())
                if final_reply:
                    return final_reply, "Tavily + Gemini"
            # Nếu Gemini lỗi ở bước 2, trả thẳng kết quả Tavily
            if tavily_result.get("ok"):
                ans = tavily_result["data"].get("answer", "")
                return ans or json.dumps(tavily_result["data"], ensure_ascii=False), "Tavily Search"
            return ai_fallback(user_message, "Gemini + Tavily đều lỗi.")

        reply = "".join(p.get("text", "") for p in parts).strip()
        if not reply:
            return ai_fallback(user_message, "Gemini trả về rỗng.")
        return reply, "Gemini"

    except Exception as exc:
        return ai_fallback(user_message, f"Lỗi kết nối Gemini: {exc}")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/chat")
def chat():
    payload = request.get_json(force=True)
    message = (payload.get("message") or "").strip()
    use_search = payload.get("search", True) is not False
    if not message:
        return jsonify({"error": "Nhập nội dung"}), 400
    reply, status = ask_ai(message, use_search)
    is_error = "Lỗi" in status
    return jsonify({"reply": reply, "search_status": status, "is_error": is_error})


@app.post("/api/get_lyrics")
def get_lyrics():
    query = request.get_json(force=True).get("query", "").strip()
    if not query:
        return jsonify({"error": "Chưa nhập tên bài hát."}), 400
    prompt = f"Cung cấp lời bài hát và ca sĩ thể hiện cho: '{query}'."
    reply, status = ask_ai(prompt, use_search=True)
    if "Lỗi" in status:
        return jsonify({"error": reply}), 500
    return jsonify({"lyrics": reply})


@app.post("/api/ghost_story")
def ghost_story():
    topic = request.get_json(force=True).get("topic", "đêm khuya").strip()
    prompt = f"Sáng tác truyện ma ngắn rùng rợn về: {topic}."
    reply, status = ask_ai(prompt, use_search=False)
    if "Lỗi" in status:
        return jsonify({"error": reply}), 500
    return jsonify({"story": reply})


# ── Game: Đuổi Hình Bắt Chữ ──────────────────────────────────────────────────
# Format: "hint" là gợi ý hiển thị (emoji + text), "dapan" là đáp án chuẩn
NGAN_HANG_CAU_DO = [
    # Động vật
    {"hint": "🐴 + 🦵",        "dapan": "ngựa đá"},
    {"hint": "🐒 + 🌳",        "dapan": "khỉ leo cây"},
    {"hint": "🐟 + 🌊",        "dapan": "cá bơi"},
    {"hint": "🐕 + 🦴",        "dapan": "chó gặm xương"},
    {"hint": "🐸 + 🍃",        "dapan": "ếch ngồi lá"},
    {"hint": "🦁 + 👑",        "dapan": "sư tử vua"},
    {"hint": "🐘 + 👃",        "dapan": "voi vòi dài"},
    {"hint": "🐧 + ❄️",        "dapan": "chim cánh cụt băng"},
    {"hint": "🦊 + 🌲",        "dapan": "cáo rừng"},
    {"hint": "🐺 + 🌕",        "dapan": "sói tru trăng"},
    # Đồ vật / hành động
    {"hint": "💋 + 💄",        "dapan": "son môi"},
    {"hint": "🌽 + 🎵",        "dapan": "bắp hát"},
    {"hint": "🔥 + 🍲",        "dapan": "lửa nấu lẩu"},
    {"hint": "☁️ + 🌧️",       "dapan": "mây mưa"},
    {"hint": "👁️ + 📏",       "dapan": "mắt nhìn thẳng"},
    {"hint": "✂️ + 📄",        "dapan": "kéo cắt giấy"},
    {"hint": "🔑 + 🚪",        "dapan": "chìa khóa mở cửa"},
    {"hint": "📚 + 🌙",        "dapan": "học đêm"},
    {"hint": "🎸 + 🔥",        "dapan": "guitar điện"},
    {"hint": "⚽ + 🥅",        "dapan": "đá bóng ghi bàn"},
    # Thức ăn
    {"hint": "🍚 + 🍳",        "dapan": "cơm chiên"},
    {"hint": "🍜 + 🌶️",       "dapan": "mì cay"},
    {"hint": "🥚 + 💔",        "dapan": "trứng vỡ"},
    {"hint": "🍰 + 🎂",        "dapan": "bánh sinh nhật"},
    {"hint": "🧃 + 🍊",        "dapan": "nước cam"},
    # Thiên nhiên
    {"hint": "🌞 + 🌊",        "dapan": "nắng biển"},
    {"hint": "🌸 + 💨",        "dapan": "hoa bay gió"},
    {"hint": "⛰️ + ❄️",       "dapan": "núi tuyết"},
    {"hint": "🌈 + ☔",        "dapan": "cầu vồng sau mưa"},
    {"hint": "🌴 + 🏖️",       "dapan": "dừa bãi biển"},
    # Con người / cảm xúc
    {"hint": "😴 + 💤",        "dapan": "ngủ ngon"},
    {"hint": "😂 + 😭",        "dapan": "khóc cười"},
    {"hint": "💪 + 🏋️",       "dapan": "tập gym"},
    {"hint": "🧠 + 💡",        "dapan": "nảy ý tưởng"},
    {"hint": "👶 + 🍼",        "dapan": "em bé bú sữa"},
    {"hint": "👩‍❤️‍👨 + 💍", "dapan": "đôi uyên ương"},
    {"hint": "🤝 + 💼",        "dapan": "bắt tay ký kết"},
    # Công nghệ
    {"hint": "💻 + ☕",        "dapan": "lập trình uống cà phê"},
    {"hint": "📱 + 🔋",        "dapan": "điện thoại sạc pin"},
    {"hint": "🤖 + 🧠",        "dapan": "robot thông minh"},
    {"hint": "🎮 + 🕹️",       "dapan": "chơi game"},
    {"hint": "📡 + 🌐",        "dapan": "phát sóng internet"},
    # Thành ngữ / vui
    {"hint": "🐌 + 🏃",        "dapan": "chậm mà chắc"},
    {"hint": "🦋 + 🌺",        "dapan": "bướm hút mật"},
    {"hint": "🐜 + 🍎",        "dapan": "kiến tha mồi"},
    {"hint": "🐓 + 🌅",        "dapan": "gà gáy sáng"},
    {"hint": "🐢 + 🏁",        "dapan": "rùa về đích"},
    {"hint": "🦅 + 🏔️",       "dapan": "đại bàng bay cao"},
    {"hint": "🐝 + 🍯",        "dapan": "ong làm mật"},
    {"hint": "🦋 + 😴",        "dapan": "nằm mơ hóa bướm"},
]

game_memory: dict = {}


@app.post("/api/game/riddle")
def game_riddle():
    cau_do = random.choice(NGAN_HANG_CAU_DO)
    user_ip = request.remote_addr
    game_memory[user_ip] = cau_do["dapan"]
    return jsonify({"emoji": cau_do["hint"]})


@app.post("/api/game/guess")
def game_guess():
    guess = (request.get_json(force=True).get("guess") or "").lower().strip()
    user_ip = request.remote_addr
    dapan = game_memory.get(user_ip, "")
    if not dapan:
        return jsonify({"error": "Bấm 'Câu hỏi mới' trước đã."}), 400
    if guess == dapan.lower():
        game_memory.pop(user_ip, None)
        return jsonify({"correct": True, "message": f"✅ Chuẩn! Đáp án: {dapan}"})
    return jsonify({"correct": False, "message": "❌ Sai rồi! Thử lại nhé."})


@app.post("/api/game/answer")
def game_answer():
    user_ip = request.remote_addr
    dapan = game_memory.pop(user_ip, "")
    if not dapan:
        return jsonify({"error": "Chưa có câu đố đang chơi."}), 400
    return jsonify({"message": f"Đáp án: {dapan}"})


@app.post("/api/clear")
def clear():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
