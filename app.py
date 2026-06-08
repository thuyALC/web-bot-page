import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request, send_file


app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "llama-3.3-70b-versatile")
chat_history = []
VIDEO_FORMATS = {
    "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best",
    "720": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best",
    "480": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best",
}


def get_duckduckgo_data(query: str) -> str:
    try:
        url = "https://lite.duckduckgo.com/lite/"
        today = datetime.now().strftime("%d/%m/%Y")
        search_query = f"{query} moi nhat hom nay {today}"
        res = requests.post(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"q": search_query},
            timeout=8,
        )
        soup = BeautifulSoup(res.text, "html.parser")
        results = []
        links = soup.find_all("a", class_="result-link")
        snippets = soup.find_all("td", class_="result-snippet")

        for index, link in enumerate(links[:8]):
            title = link.get_text(" ", strip=True)
            href = link.get("href", "").strip()
            snippet = snippets[index].get_text(" ", strip=True) if index < len(snippets) else ""
            if title or snippet:
                results.append(f"{title}\n{snippet}\nNguon: {href}")

        if results:
            return "\n\n".join(results)

        fallback_snippets = [
            item.get_text(" ", strip=True)
            for item in soup.find_all("td", class_="result-snippet")[:8]
        ]
        return "\n\n".join(fallback_snippets)
    except Exception:
        return ""


def get_web_data(query: str) -> tuple[str, str]:
    duck_data = get_duckduckgo_data(query)
    if duck_data:
        return f"Nguon tim kiem: DuckDuckGo\n\n{duck_data}", "DuckDuckGo: da lay data web"
    return "", "DuckDuckGo: khong lay duoc data web"


def ask_ai(user_message: str, web_data: str = "") -> str:
    if not GROQ_API_KEY:
        return "Chua cau hinh GROQ_API_KEY tren server."

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    messages = [
        {
            "role": "system",
            "content": (
                "Ban la tro ly tieng Viet, tra loi ngan gon, dung trong tam. "
                "Neu co du lieu web moi nhat, phai uu tien du lieu web do thay vi kien thuc cu cua model. "
                "Neu du lieu web khong du de ket luan, hay noi ro la chua xac minh duoc. "
                f"Thoi gian hien tai: {now_str}."
            ),
        }
    ]

    if web_data:
        messages.append(
            {"role": "system", "content": f"Du lieu tham khao moi nhat:\n{web_data}"}
        )

    messages.extend(chat_history[-10:])
    messages.append({"role": "user", "content": user_message})

    res = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": MODEL_NAME, "messages": messages},
        timeout=25,
    )
    res.raise_for_status()
    reply = res.json()["choices"][0]["message"]["content"]
    chat_history.extend(
        [{"role": "user", "content": user_message}, {"role": "assistant", "content": reply}]
    )
    return reply


def extract_media_links(url: str, quality: str) -> list[str]:
    formats = {
        **VIDEO_FORMATS,
        "audio": "bestaudio[ext=m4a]/bestaudio",
    }
    fmt = formats.get(quality, formats["720"])
    cmd = [
        "yt-dlp",
        "-g",
        "-f",
        fmt,
        "--no-playlist",
        "--force-ipv4",
        "--extractor-args",
        "youtube:player_client=android,web",
        url,
    ]
    output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=45)
    return [line.strip() for line in output.splitlines() if line.strip().startswith("http")]


def find_audio(query: str) -> dict:
    target = query if query.startswith(("http://", "https://")) else f"ytsearch1:{query}"
    cmd = [
        "yt-dlp",
        target,
        "-f",
        "bestaudio[ext=m4a]/bestaudio",
        "--no-playlist",
        "--force-ipv4",
        "--extractor-args",
        "youtube:player_client=android,web",
        "--print",
        "%(title)s",
        "--print",
        "%(url)s",
    ]
    output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=45)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    audio_url = next((line for line in reversed(lines) if line.startswith("http")), "")
    title = next((line for line in lines if not line.startswith("http")), query)
    if not audio_url:
        raise RuntimeError("Khong lay duoc link audio.")
    return {"title": title, "url": audio_url}


def download_merged_mp4(url: str, quality: str) -> tuple[str, Path]:
    if quality not in VIDEO_FORMATS:
        raise ValueError("Chon 1080p, 720p hoac 480p de tai MP4.")

    temp_dir = tempfile.mkdtemp(prefix="web-bot-download-")
    output_template = str(Path(temp_dir) / "video.%(ext)s")
    timeout = int(os.environ.get("DOWNLOAD_TIMEOUT", "600"))
    cmd = [
        "yt-dlp",
        "-f",
        VIDEO_FORMATS[quality],
        "--merge-output-format",
        "mp4",
        "--no-playlist",
        "--force-ipv4",
        "--extractor-args",
        "youtube:player_client=android,web",
        "-o",
        output_template,
        url,
    ]

    try:
        subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        files = sorted(Path(temp_dir).glob("*.mp4"))
        if not files:
            raise RuntimeError("Tai xong nhung khong thay file MP4. Server co the thieu ffmpeg.")
        return temp_dir, files[0]
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/chat")
def chat():
    payload = request.get_json(force=True)
    message = (payload.get("message") or "").strip()
    use_search = payload.get("search", True) is not False

    if not message:
        return jsonify({"error": "Nhap noi dung truoc."}), 400

    try:
        web_data, search_status = get_web_data(message) if use_search else ("", "Da tat lay data moi")
        return jsonify({"reply": ask_ai(message, web_data), "search_status": search_status})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/extract")
def extract():
    payload = request.get_json(force=True)
    url = (payload.get("url") or "").strip()
    quality = payload.get("quality") or "720"

    if not url:
        return jsonify({"error": "Nhap link truoc."}), 400

    try:
        return jsonify({"links": extract_media_links(url, quality)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/download")
def download():
    payload = request.get_json(force=True)
    url = (payload.get("url") or "").strip()
    quality = payload.get("quality") or "720"

    if not url:
        return jsonify({"error": "Nhap link truoc."}), 400

    try:
        temp_dir, file_path = download_merged_mp4(url, quality)
        response = send_file(
            file_path,
            as_attachment=True,
            download_name=f"video_{quality}p.mp4",
            mimetype="video/mp4",
        )
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response
    except subprocess.CalledProcessError as exc:
        error_text = (exc.output or str(exc))[-1200:]
        return jsonify({"error": error_text}), 500
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/play")
def play():
    payload = request.get_json(force=True)
    query = (payload.get("query") or "").strip()

    if not query:
        return jsonify({"error": "Nhap ten bai hoac link truoc."}), 400

    try:
        return jsonify(find_audio(query))
    except subprocess.CalledProcessError as exc:
        error_text = (exc.output or str(exc))[-1200:]
        return jsonify({"error": error_text}), 500
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/clear")
def clear():
    chat_history.clear()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
