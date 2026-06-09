import json
import os
import random
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template, request


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "b4-f3a-k3y-p1s-r3pl4c3-1t")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "").strip()

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

HERMES_TOOL_NAME = "hermes_agent_search"
HERMES_TOOL = {
    "functionDeclarations": [
        {
            "name": HERMES_TOOL_NAME,
            "description": (
                "Call Hermes-Agent to fetch and process fresh news or current data. "
                "Use this when the user asks about news, recent events, prices, "
                "schedules, results, or anything that needs up-to-date information."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {
                        "type": "STRING",
                        "description": "The user's question or search query for Hermes-Agent.",
                    },
                    "locale": {
                        "type": "STRING",
                        "description": "Preferred locale, for example vi-VN.",
                    },
                },
                "required": ["query"],
            },
        }
    ]
}

FRESH_QUERY_KEYWORDS = (
    "tin tuc",
    "tin moi",
    "moi nhat",
    "hom nay",
    "bao moi",
    "thoi su",
    "su kien",
    "gia",
    "lich",
    "ket qua",
    "cap nhat",
    "news",
    "latest",
    "today",
)


def normalize_text(value: str) -> str:
    return (value or "").lower()


def looks_like_fresh_query(message: str) -> bool:
    text = normalize_text(message)
    return any(keyword in text for keyword in FRESH_QUERY_KEYWORDS)


def extract_text_from_gemini(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        return ""

    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts).strip()


def call_hermes_agent(query: str, locale: str = "vi-VN") -> dict:
    """Gọi Tavily Search API để lấy thông tin mới nhất."""
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
        # Tavily trả về field "answer" (tóm tắt AI) và "results" (danh sách bài)
        answer = data.get("answer", "")
        results = data.get("results", [])

        if not answer and results:
            # Tự tổng hợp từ top results nếu không có answer
            snippets = [
                f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
                for r in results[:3]
            ]
            answer = "\n".join(snippets)

        return {"ok": True, "data": {"answer": answer, "sources": results}}
    except Exception as exc:
        return {"ok": False, "error": f"Lỗi kết nối Tavily: {exc}"}


def hermes_direct_answer(query: str, result: dict) -> tuple[str, str]:
    if not result.get("ok"):
        return result.get("error", "Hermes-Agent không trả về dữ liệu."), "Lỗi Hermes-Agent"

    data = result.get("data")
    if isinstance(data, dict):
        for key in ("answer", "summary", "content", "text", "result"):
            if data.get(key):
                return str(data[key]), "Tavily Search"
        return json.dumps(data, ensure_ascii=False, indent=2), "Tavily Search"

    return str(data), "Tavily Search"


def hermes_fallback(query: str, gemini_err_msg: str) -> tuple[str, str]:
    """Khi Gemini lỗi, tự động gọi Tavily để tìm kiếm thay thế."""
    if not TAVILY_API_KEY:
        return gemini_err_msg, "Lỗi Gemini"
    result = call_hermes_agent(query)
    if result.get("ok"):
        answer, _ = hermes_direct_answer(query, result)
        return answer, "Tavily Search (Gemini quá tải)"
    # Hermes cũng lỗi → trả thông báo Gemini gốc
    return gemini_err_msg, "Lỗi Gemini"


def ask_ai(user_message: str, use_search: bool = True):
    """Gemini answers normally, or calls Hermes-Agent as a Gemini tool."""
    if not GEMINI_API_KEY:
        return hermes_fallback(user_message, "Hệ thống chưa cấu hình GEMINI_API_KEY.")

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    system_prompt = (
        "Bạn là trợ lý tiếng Việt. Trả lời ngắn gọn, tự nhiên. "
        f"Thời gian hiện tại: {now_str}. "
        "Khi câu hỏi cần tin tức hoặc dữ liệu mới, hãy gọi tool hermes_agent_search. "
        "Khi câu hỏi có thể trả lời bằng kiến thức chung, tự trả lời không gọi tool."
    )

    contents = [
        {
            "role": "user",
            "parts": [{"text": f"{system_prompt}\n\nNguoi dung: {user_message}"}],
        }
    ]
    gemini_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

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
                err_msg = "Gemini đang bận (quá hạn mức). Vui lòng thử lại sau ít phút."
            elif res.status_code in (401, 403):
                err_msg = "API key Gemini không hợp lệ hoặc không có quyền truy cập."
            elif res.status_code >= 500:
                err_msg = "Máy chủ Gemini đang gặp sự cố. Vui lòng thử lại sau."
            else:
                err_msg = f"Gemini lỗi {res.status_code}."
            return hermes_fallback(user_message, err_msg)

        response_data = res.json()
        candidates = response_data.get("candidates") or []
        if not candidates:
            return hermes_fallback(user_message, "Gemini không trả về câu trả lời.")

        candidate_content = candidates[0].get("content", {})
        parts = candidate_content.get("parts", [])
        function_call = next(
            (part.get("functionCall") for part in parts if part.get("functionCall")),
            None,
        )

        if function_call and function_call.get("name") == HERMES_TOOL_NAME:
            args = function_call.get("args") or {}
            hermes_query = args.get("query") or user_message
            hermes_locale = args.get("locale") or "vi-VN"
            hermes_result = call_hermes_agent(hermes_query, hermes_locale)

            contents.append(candidate_content)
            contents.append(
                {
                    "role": "function",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": HERMES_TOOL_NAME,
                                "response": hermes_result,
                            }
                        }
                    ],
                }
            )

            final_res = requests.post(
                gemini_url,
                json={"contents": contents, "tools": [HERMES_TOOL]},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            if final_res.status_code != 200:
                return hermes_direct_answer(hermes_query, hermes_result)

            final_reply = extract_text_from_gemini(final_res.json())
            if final_reply:
                return final_reply, "Hermes-Agent + Gemini"

            return hermes_direct_answer(hermes_query, hermes_result)

        reply = "".join(part.get("text", "") for part in parts).strip()
        if not reply:
            return "Gemini không trả về nội dung text.", "Lỗi Gemini"

        return reply, "Gemini"
    except Exception as exc:
        return hermes_fallback(user_message, f"Lỗi kết nối Gemini: {exc}")


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
    reply, search_status = ask_ai(message, use_search)
    # Classify status type for frontend badge color
    is_error = any(x in search_status for x in ("Lỗi", "Loi", "Error"))
    return jsonify({"reply": reply, "search_status": search_status, "is_error": is_error})


@app.post("/api/get_lyrics")
def get_lyrics():
    query = request.get_json(force=True).get("query", "").strip()
    if not query:
        return jsonify({"error": "Chua nhap ten bai hat."}), 400

    prompt = f"Hay cung cap loi bai hat va ca si the hien cho bai hat/cau hat sau: '{query}'."
    reply, status = ask_ai(prompt, use_search=True)

    if "Toang" in status or "Loi" in status:
        return jsonify({"error": reply}), 500
    return jsonify({"lyrics": reply})


@app.post("/api/ghost_story")
def ghost_story():
    topic = request.get_json(force=True).get("topic", "dem khuya").strip()
    prompt = f"Sang tac truyen ma ngan rung ron ve: {topic}."
    reply, status = ask_ai(prompt, use_search=False)

    if "Toang" in status or "Loi" in status:
        return jsonify({"error": reply}), 500
    return jsonify({"story": reply})


NGAN_HANG_CAU_DO = [
    {"emoji": "moi + son", "dapan": "son moi"},
    {"emoji": "bap + hat", "dapan": "bap hat"},
    {"emoji": "ngua + da", "dapan": "ngua da"},
    {"emoji": "lua + lau", "dapan": "lau thai"},
    {"emoji": "mat + dai", "dapan": "thi dai"},
    {"emoji": "khi + cay", "dapan": "khi leo cay"},
    {"emoji": "may + mua", "dapan": "mua bong may"},
]

game_memory = {}


@app.post("/api/game/riddle")
def game_riddle():
    cau_do = random.choice(NGAN_HANG_CAU_DO)
    user_ip = request.remote_addr
    game_memory[user_ip] = cau_do["dapan"]
    return jsonify({"emoji": cau_do["emoji"]})


@app.post("/api/game/guess")
def game_guess():
    guess = request.get_json(force=True).get("guess", "").lower().strip()
    user_ip = request.remote_addr
    dapan = game_memory.get(user_ip, "")

    if not dapan:
        return jsonify({"error": "Bam Lay cau do truoc da."}), 400

    if guess == dapan:
        game_memory.pop(user_ip, None)
        return jsonify({"correct": True, "message": f"Chuan! Dap an: {dapan.title()}"})
    return jsonify({"correct": False, "message": "Sai roi!"})


@app.post("/api/game/answer")
def game_answer():
    user_ip = request.remote_addr
    dapan = game_memory.get(user_ip, "")
    if not dapan:
        return jsonify({"error": "Chua co cau do dang choi."}), 400
    game_memory.pop(user_ip, None)
    return jsonify({"message": f"Dap an la: {dapan.title()}"})


@app.post("/api/clear")
def clear():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
