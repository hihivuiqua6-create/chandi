# ⚡ Buff Bot — Telegram Bot + Admin Panel

Bot Telegram buff TikTok với admin panel đẹp, kết nối tới Buff API sẵn có.

---

## 🚀 Deploy lên Render

### Bước 1 — Push lên GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

### Bước 2 — Deploy trên Render
1. Vào [render.com](https://render.com) → **New → Web Service**
2. Chọn GitHub repo vừa tạo
3. Render tự đọc `render.yaml`. Nếu tạo tay:
   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120`
4. Bấm **Deploy**

### Bước 3 — Cài đặt sau deploy
1. Vào `https://YOUR-APP.onrender.com/admin`
2. Đăng nhập mật khẩu mặc định: **`admin123`** (đổi ngay!)
3. Vào **Cài đặt Bot** → điền Bot Token, Admin IDs, Buff API URL
4. Vào **Nhóm bắt buộc** → thêm nhóm cần user join
5. Đặt giới hạn buff/ngày

---

## 📦 Build & Start commands

| | Command |
|---|---|
| **Build** | `pip install -r requirements.txt` |
| **Start** | `gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120` |

---

## ⚙️ Cấu hình (đều làm từ Admin Panel)

| Mục | Mô tả |
|---|---|
| Bot Token | Lấy từ @BotFather |
| Admin IDs | ID Telegram của admin (lấy từ @userinfobot), cách nhau dấu phẩy |
| Buff API URL | URL của source buff đã deploy (source kia) |
| Giới hạn/ngày | Số lượt buff tối đa mỗi user mỗi ngày |
| Nhóm bắt buộc | User phải join đủ mới được buff |

---

## 🤖 Lệnh Bot

### User
| Lệnh | Mô tả |
|---|---|
| `/start` | Bắt đầu, kiểm tra nhóm |
| `/buff <link>` | Buff TikTok video/profile |
| `/status` | Xem lượt còn lại hôm nay |
| `/help` | Hướng dẫn sử dụng |

### Admin (ẩn với user thường)
| Lệnh | Mô tả |
|---|---|
| `/admin` | Xem thống kê nhanh |
| `/broadcast <tin>` | Gửi thông báo tới tất cả |
| `/ban <user_id>` | Cấm user |
| `/unban <user_id>` | Bỏ cấm |
| `/setlimit <số>` | Đặt giới hạn buff/ngày |
| `/setapi <url>` | Đặt buff API URL |
| `/stats` | Thống kê chi tiết |
| `/listusers` | Danh sách users |

---

## 🔒 Luồng buff của user

1. User gửi `/start`
2. Bot kiểm tra user đã join đủ nhóm chưa
3. Nếu chưa → gửi nút Join từng nhóm
4. User join → nhấn **✅ Đã tham gia tất cả**
5. Bot xác nhận → welcome message
6. User gửi `/buff https://tiktok.com/...`
7. Bot kiểm tra ban + nhóm + limit ngày
8. Bot lấy captcha từ Buff API → gửi ảnh
9. User nhập captcha
10. Bot xác thực → hiện danh sách services
11. User chọn service
12. Bot chạy buff → báo kết quả
13. **Nếu rời nhóm** → không buff được nữa (check mỗi lần buff)

---

## 📁 Cấu trúc thư mục

```
buffbot/
├── main.py              # Entry point
├── database.py          # SQLite operations
├── buff_api.py          # Kết nối Buff API
├── bot/
│   ├── handlers.py      # Lệnh user
│   ├── admin_handlers.py # Lệnh admin (ẩn)
│   └── bot_runner.py    # Khởi động bot
├── admin/
│   ├── routes.py        # FastAPI routes admin panel
│   └── templates/       # Giao diện web
├── requirements.txt
├── render.yaml
└── Procfile
```

---

## ⚠️ Lưu ý

- **Free tier Render** sẽ sleep sau 15 phút không dùng → lần đầu vào sẽ chậm
- Render free **không lưu file** giữa các deploy → SQLite sẽ reset khi re-deploy
- Để lưu dữ liệu bền vững: nâng lên Render Paid hoặc dùng PostgreSQL (liên hệ dev)
- Bot cần quyền **admin** trong nhóm để check thành viên
