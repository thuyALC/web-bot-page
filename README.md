# Web bot page

Ban nay chuyen code bot Python thanh trang web co backend rieng.

## Chat AI

Chat AI dung Gemini lam model chinh. Hermes-Agent duoc tich hop thanh tool trong payload Gemini API:

- Cau hoi thong thuong: Gemini tu tra loi.
- Cau hoi can tin tuc/du lieu moi: Gemini goi tool `hermes_agent_search`, backend goi Hermes-Agent, sau do dua ket qua ve lai Gemini de viet cau tra loi.
- Khi Gemini loi hoac het quota: neu cau hoi co dau hieu can tin moi, backend goi Hermes-Agent truc tiep de tra ket qua thay vi dung RSS/Groq.

App khong con dung RSS hoac Groq cho fallback tin tuc.

## Chay tren may

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GEMINI_API_KEY="gemini_key_cua_ban"
$env:HERMES_AGENT_URL="https://hermes-agent-cua-ban.example.com/search"
$env:HERMES_AGENT_API_KEY="neu_agent_can_key"
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
Environment variable: GEMINI_API_KEY=key_cua_ban
Environment variable: HERMES_AGENT_URL=url_endpoint_cua_hermes_agent
Environment variable: HERMES_AGENT_API_KEY=neu_agent_can_key
Environment variable: GEMINI_MODEL=gemini-2.5-flash
```

`HERMES_AGENT_URL` nen nhan request POST JSON:

```json
{
  "query": "cau hoi hoac tu khoa",
  "locale": "vi-VN"
}
```

Endpoint co the tra JSON co mot trong cac field `answer`, `summary`, `content`, `text`, `result`, hoac tra text thuan.

## Luu y bao mat

Khong dua API key len GitHub. Dat key trong Environment Variables cua host.
