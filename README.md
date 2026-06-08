# Web bot page

Ban nay chuyen code bot Python thanh trang web co backend rieng. Co chat AI, boc link, nghe nhac, doc noi dung, va nut tai/gop MP4 bang `yt-dlp` + `ffmpeg`.

Chat AI mac dinh se lay data moi bang DuckDuckGo truoc khi tra loi. Neu tat checkbox lay data moi, cau tra loi co the bi gioi han theo data cu cua model.

## Can lam ngay

File Python goc dang de lo Telegram token va Groq API key. Hay vao Telegram BotFather va Groq de revoke/rotate key cu truoc khi dua code len online.

## Chay tren may

```powershell
cd outputs/web-bot-page
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GROQ_API_KEY="dien_key_moi_o_day"
python app.py
```

Mo trinh duyet vao:

```text
http://localhost:8000
```

## Dua len online

Dung Render, Railway, Fly.io hoac VPS deu duoc.

Thiet lap:

```text
Build command: pip install -r requirements.txt
Start command: gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120
Environment variable: GROQ_API_KEY=key_moi_cua_ban
Environment variable: DOWNLOAD_TIMEOUT=900
```

Neu host doc `Procfile` thi chi can dat bien moi truong `GROQ_API_KEY`.

App dang dung DuckDuckGo de lay data moi, khong can Google key.

Render co the doc `Aptfile` de cai `ffmpeg`. Neu host khac khong doc `Aptfile`, can cai `ffmpeg` rieng tren server.

## Nut tai/gop MP4

Nut `Tai & gop MP4` se tai video va audio ve server, gop thanh file MP4, roi trinh duyet tu tai file ve may.

Can luu y:

- Video dai co the mat vai phut.
- Host mien phi co the timeout hoac gioi han dung luong.
- Mot so link YouTube/Facebook co the bi chan boi IP cua host.
- Muon on dinh nen dung VPS Ubuntu co cai `python`, `yt-dlp`, `ffmpeg`.

## Nghe nhac va doc noi dung

Muc `Nghe nhac` tim bai bang `yt-dlp`, lay link audio va phat bang trinh duyet.

Muc `Doc noi dung` dung `speechSynthesis` cua trinh duyet, nen tieng doc phu thuoc may/Chrome/Edge dang mo web. No khong doc ra loa server nhu Termux nua.

## Vi sao khong lam HTML thuan

HTML thuan se lam lo API key trong trinh duyet. Cac viec goi AI, boc link bang `yt-dlp`, tai/gop video va chay lenh he thong phai nam o backend.
