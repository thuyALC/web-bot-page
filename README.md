# 🚀 HỆ THỐNG WORKSPACE PREMIUM & GIẢI TRÍ ĐA PHƯƠNG TIỆN

Một hệ sinh thái Web đa năng tích hợp Trợ lý Trí tuệ Nhân tạo (AI Chatbot), Công cụ Tiện ích và Không gian Giải trí (Mini Games, Board Games, Retro Games) với giao diện Glassmorphism 3D hiện đại.

Hệ thống được thiết kế tối ưu, có khả năng tự động sinh nội dung vô hạn (Generative AI) và trang bị cơ chế Fallback (dự phòng) qua nhiều nền tảng AI khác nhau để đảm bảo hoạt động liên tục 24/7.

---

## 🌟 TÍNH NĂNG NỔI BẬT

### 1. Trợ Lý AI & Tiện Ích (Workspace)
*   **Chat AI Đa Luồng:** Tích hợp Gemini 2.5 Flash làm Core AI, kết hợp Tavily Search để tìm kiếm thông tin thời gian thực (Real-time Online Search).
*   **Hệ thống Fallback Thông Minh:** Tự động chuyển hướng sang GitHub Models (GPT-4o-mini) hoặc OpenRouter (Mistral) nếu Gemini gặp sự cố mạng hoặc hết quota.
*   **Trích xuất Lyric Nhạc:** Công cụ AI tự động tra cứu lời bài hát và thông tin ca sĩ nhanh chóng.
*   **Terminal Giả lập:** Hiển thị kết quả truy vấn, log hệ thống bằng giao diện console chuyên nghiệp.

### 2. Khu Vực Trò Chơi AI Sinh Vô Hạn (AI Generative Games)
*   **🧩 Giải Mã Ký Tự:** AI tự động sáng tác các câu đố đảo chữ theo độ khó (Dễ/Trung Bình/Khó) không bao giờ trùng lặp. Có kho dữ liệu dự phòng (Offline Backup) khi mất mạng.
*   **💡 Câu Đố Trí Tuệ:** Hỏi xoáy đáp xoay, đố vui dân gian và đố mẹo. Dữ liệu được đúc kết trực tiếp từ AI ngay thời điểm bấm nút, tích hợp cơ chế nhận diện câu trả lời thông minh (Fuzzy Match).

### 3. Khu Vực Cờ Bàn & Giải Trí Xả Stress (Board Games)
*   **🧱 Xếp Hình 2D (Tetris):** Game xếp gạch kinh điển với thuật toán va chạm chuẩn xác và tính điểm combo.
*   **⭕ Cờ Caro (Gomoku vs AI Bot):** Tích hợp AI chặn thông minh có khả năng tính toán hệ số điểm công/thủ để quyết đấu với người chơi.

### 4. Khu Vực Game Ký Ức Tuổi Thơ (Web Games Links)
*   **🔫 Counter-Strike 1.6 (WebAssembly):** Tích hợp cổng chơi CS 1.6 trực tiếp trên nền web.
*   **🐲 Gunbound Web (DragonBound):** Khởi động nhanh máy chủ bắn súng tọa độ huyền thoại.

### 🛑 Đặc Biệt: Menu Ma Giáo (Hack Tool)
Hệ thống tích hợp sẵn một "Hack Menu" ẩn góc phải màn hình cho phép can thiệp vào logic game:
*   Xóa 4 dòng móng nhà trong Tetris.
*   Hack làm chậm thời gian rơi (x5) của Tetris.
*   Tẩy sạch toàn bộ cờ phòng ngự của AI Bot trong Caro.

---

## 🛠️ CÔNG NGHỆ SỬ DỤNG
*   **Backend:** Python (Flask, Requests, BeautifulSoup4)
*   **Frontend:** HTML5, CSS3 (Glassmorphism, Flexbox/Grid), Vanilla JavaScript (Canvas API).
*   **AI & APIs:** Google Gemini API, Tavily Search API, OpenRouter API, GitHub Models.
*   **Server/Deployment:** Gunicorn (Sẵn sàng deploy lên Heroku, Render, VPS...).

---

## ⚙️ HƯỚNG DẪN CÀI ĐẶT & CHẠY LOKAL

### Bước 1: Yêu cầu môi trường
Đảm bảo máy tính của bạn đã cài đặt **Python 3.9+** trở lên.

### Bước 2: Tải mã nguồn và cài thư viện
Mở Terminal/CMD, di chuyển vào thư mục dự án và chạy lệnh sau để cài đặt các thư viện cần thiết:
```bash
pip install -r requirements.txt



Bước 3: Cấu hình Biến môi trường (Environment Variables)

Để các tính năng AI và Search hoạt động, bạn cần cấu hình các API Key. Hệ thống sử dụng các biến sau (có thể thiết lập qua Terminal hoặc thêm vào hệ thống):
Tên Biến	Mô Tả	Bắt Buộc
GEMINI_API_KEY	Key chính để chạy AI và tạo mini-games. Lấy tại Google AI Studio.	Có
TAVILY_API_KEY	Key tìm kiếm Online real-time. Lấy tại Tavily.	Tùy chọn
OPENROUTER_API_KEY	Key dự phòng (Fallback) gọi mô hình Mistral.	Tùy chọn
GITHUB_TOKEN	Key dự phòng (Fallback) gọi mô hình GPT-4o-mini.	Tùy chọn
FLASK_SECRET_KEY	Chuỗi bảo mật nội bộ của Flask.	Tùy chọn
PORT	Cổng khởi chạy Web Server (Mặc định: 8000).	Tùy chọn

Bước 4: Khởi chạy máy chủ Web

Chạy lệnh sau để khởi động App:
Bash

python app.py

Sau đó mở trình duyệt và truy cập vào: http://localhost:8000
🚀 HƯỚNG DẪN TRIỂN KHAI (DEPLOYMENT)

Dự án đã được thiết lập sẵn các file cần thiết để triển khai lên các nền tảng đám mây:

    Procfile: Lệnh khởi chạy server thực tế web: gunicorn app:app.

    Aptfile: Dùng để tải các extension hệ thống (nếu dùng trên Heroku).

    requirements.txt: Danh sách thư viện.

Chỉ cần đẩy mã nguồn này lên Github và kết nối với các dịch vụ như Render.com hoặc Heroku, cấu hình đầy đủ biến môi trường (Environment Variables) trên bảng điều khiển của họ là ứng dụng sẽ chạy Online.

Chúc bạn có trải nghiệm tuyệt vời với Premium Workspace! 🎮✨

