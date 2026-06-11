import json
import os
import random
import re
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup
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
    gmt7 = timezone(timedelta(hours=7))
    return datetime.now(tz=gmt7).strftime("%d/%m/%Y %H:%M:%S (GMT+7)")

def system_prompt_vi() -> str:
    return (
        "Bạn là trợ lý AI thông minh, bắt buộc trả lời bằng tiếng Việt. "
        f"Thời gian hiện tại tại Việt Nam: {now_str()}. "
        "QUAN TRỌNG – Luật trả lời:\n"
        "1. Trả lời TRỰC TIẾP vào câu hỏi, KHÔNG nói vòng vo.\n"
        "2. Dựa vào dữ liệu được cung cấp, hãy phân tích thật ĐẦY ĐỦ, CÓ CHI TIẾT (ngày, giờ, địa điểm cụ thể).\n"
        "3. Trình bày rõ ràng, dùng Markdown, gạch đầu dòng hoặc số thứ tự cho dễ đọc.\n"
        "4. Nếu thông tin không có trong dữ liệu tìm kiếm, hãy nói rõ là chưa có thông tin cập nhật, KHÔNG tự bịa."
    )

def extract_text_openai_style(data: dict) -> str:
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""

def extract_text_from_gemini(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts if "text" in p).strip()

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
    if not r.get("ok"):
        return r.get("error", "Tavily không trả về dữ liệu."), "Lỗi Tavily"

    data = r["data"]
    raw_answer = data.get("answer", "")
    sources = data.get("sources", [])

    context_parts = []
    if raw_answer:
        context_parts.append(f"Tóm tắt: {raw_answer}")
    for s in sources[:4]:
        title = s.get("title", "")
        content = s.get("content", "")[:400]
        url = s.get("url", "")
        if title or content:
            context_parts.append(f"- {title}: {content} ({url})")
    context = "\n".join(context_parts) or "Không có dữ liệu."

    synthesis_prompt = (
        f"Dựa vào dữ liệu tìm kiếm dưới đây, hãy trả lời câu hỏi: '{query}'\n\n"
        f"DỮ LIỆU:\n{context}\n\n"
        "Yêu cầu: Trả lời hoàn toàn bằng tiếng Việt, đầy đủ chi tiết, rõ ràng, "
        "KHÔNG nói 'dựa vào dữ liệu trên', chỉ trả lời thẳng vào nội dung."
    )

    reply, status = ask_github_models(synthesis_prompt)
    if status != "skip":
        return reply, "Tavily + GitHub Models"

    reply, status = ask_openrouter(synthesis_prompt)
    if status != "skip":
        return reply, "Tavily + OpenRouter"

    return f"*(Chế độ thô)*\n{raw_answer}\n\nNguồn tham khảo:\n{context}", "Tavily Raw (Lỗi AI)"

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
    reply, status = ask_github_models(message)
    if status != "skip":
        return reply, status

    reply, status = ask_openrouter(message)
    if status != "skip":
        return reply, status

    reply, status = tavily_answer(message)
    if "Lỗi" not in status:
        return reply, "Tavily Search (Gemini Backup)"

    return gemini_err, "Lỗi – Tất cả dịch vụ không khả dụng"

# ── Gemini (main) ─────────────────────────────────────────────────────────────
def ask_ai(user_message: str, use_search: bool = True) -> tuple[str, str]:
    if not GEMINI_API_KEY:
        return ai_fallback(user_message, "Chưa cấu hình GEMINI_API_KEY.")

    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt_vi()}]},
        "contents": [{"role": "user", "parts": [{"text": user_message}]}]
    }

    if use_search:
        payload["tools"] = [HERMES_TOOL]

    try:
        res = requests.post(
            gemini_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        
        if res.status_code != 200:
            return ai_fallback(user_message, f"Gemini lỗi {res.status_code}")

        response_data = res.json()
        candidates = response_data.get("candidates") or []
        if not candidates:
            return ai_fallback(user_message, "Gemini không trả về kết quả.")

        candidate_content = candidates[0].get("content", {})
        parts = candidate_content.get("parts", [])
        function_call = next((p.get("functionCall") for p in parts if "functionCall" in p), None)

        if function_call and function_call.get("name") == HERMES_TOOL_NAME:
            args = function_call.get("args") or {}
            q = args.get("query") or user_message
            tavily_result = call_tavily(q)

            payload["contents"].append(candidate_content)
            payload["contents"].append({
                "role": "function",
                "parts": [{
                    "functionResponse": {
                        "name": HERMES_TOOL_NAME,
                        "response": {"result": tavily_result}
                    }
                }]
            })

            final_res = requests.post(
                gemini_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            
            if final_res.status_code == 200:
                final_reply = extract_text_from_gemini(final_res.json())
                if final_reply:
                    return final_reply, "Tavily + Gemini"
            
            if tavily_result.get("ok"):
                return tavily_answer(q)
            return ai_fallback(user_message, "Gemini + Tavily đều lỗi.")

        reply = "".join(p.get("text", "") for p in parts if "text" in p).strip()
        if not reply:
            return ai_fallback(user_message, "Gemini trả về rỗng.")
        return reply, "Gemini"

    except Exception as exc:
        return ai_fallback(user_message, f"Lỗi kết nối Gemini: {exc}")

# ── GAME CÀO DỮ LIỆU TỪ WIKIPEDIA (MỚI) ──────────────────────────────────────
FALLBACK_SCRAMBLE = [
    {"title": "PROXY", "meaning": "Một hệ thống máy chủ trung gian giúp ẩn danh hoặc định tuyến lại lưu lượng mạng."},
    {"title": "EXCEL", "meaning": "Phần mềm bảng tính dùng để quản lý dữ liệu, xuất nhập tồn kho và sử dụng các hàm tính toán."},
    {"title": "MAGISK", "meaning": "Một công cụ mạnh mẽ mã nguồn mở được sử dụng để can thiệp quyền hệ thống (root) trên thiết bị Android."},
    {"title": "GEMINI", "meaning": "Một mô hình ngôn ngữ lớn, trí tuệ nhân tạo có thể trò chuyện và xử lý dữ liệu thông minh."}
]

def scrape_wikipedia_word():
    for _ in range(5):
        try:
            res = requests.get("https://vi.wikipedia.org/wiki/Đặc_biệt:Ngẫu_nhiên", timeout=5)
            soup = BeautifulSoup(res.text, "html.parser")
            
            title_element = soup.find("h1", id="firstHeading")
            if not title_element: continue
            title = title_element.text
            
            meaning = ""
            paragraphs = soup.select(".mw-parser-output > p")
            for p in paragraphs:
                text = p.text.strip()
                if len(text) > 30:
                    meaning = text
                    break
                    
            clean_title = re.sub(r'\(.*?\)', '', title).strip()
            
            # Chỉ lấy từ khóa ngắn gọn
            if 3 <= len(clean_title) <= 20 and meaning:
                return {"title": clean_title, "meaning": meaning}
        except:
            continue
            
    return random.choice(FALLBACK_SCRAMBLE)

@app.route("/api/game/scramble", methods=["GET"])
def game_scramble():
    data = scrape_wikipedia_word()
    dap_an_goc = data['title'].upper()
    goi_y = data['meaning']
    
    # Che đáp án trong phần gợi ý để không bị lộ
    goi_y_da_che = re.sub(re.escape(data['title']), "___", goi_y, flags=re.IGNORECASE)
    
    dap_an_khong_khoang_trang = dap_an_goc.replace(" ", "")
    chu_cai_xao_tron = list(dap_an_khong_khoang_trang)
    random.shuffle(chu_cai_xao_tron)
    
    return jsonify({
        "chu_de": "Bách khoa toàn thư (Wikipedia)",
        "goi_y": goi_y_da_che,
        "dap_an": dap_an_goc,
        "so_luong": len(dap_an_khong_khoang_trang),
        "xao_tron": chu_cai_xao_tron
    })

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

@app.post("/api/clear")
def clear():
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
