# گزارش جامع وب‌اپلیکیشن DataGPT

<div dir="rtl">

## فهرست مطالب

1. [مقدمه](#مقدمه)
2. [موارد استفاده](#موارد-استفاده)
3. [راهنمای استفاده](#راهنمای-استفاده)
4. [راهنمای استقرار (Deployment)](#راهنمای-استقرار)
5. [مستندات API](#مستندات-api)
6. [معماری فنی](#معماری-فنی)

---

## مقدمه

### DataGPT چیست؟

**DataGPT** یک وب‌اپلیکیشن پیشرفته است که امکان گفتگو با منابع داده‌ای مختلف را به زبان طبیعی فراهم می‌کند. این سیستم با استفاده از تکنولوژی **RAG (Retrieval-Augmented Generation)** و مدل‌های زبان بزرگ (LLM)، به کاربران اجازه می‌دهد بدون نیاز به دانش SQL یا برنامه‌نویسی، از اسناد، پایگاه‌های داده و فایل‌های اکسل خود سوال بپرسند.

### ویژگی‌های کلیدی

#### 🔍 بازیابی هوشمند
- جستجوی معنایی مبتنی بر Vector در اسناد (RAG)
- تکه‌بندی متن با آگاهی از زمینه و امتیازدهی شباهت
- ردیابی خودکار منبع با سیستم استنادات

#### 💾 هوشمندی پایگاه داده
- کشف خودکار schema و تحلیل توسط LLM برای پایگاه‌های SQL (MySQL، PostgreSQL، SQLite) و MongoDB
- ترجمه زبان طبیعی به کوئری‌های SQL/NoSQL
- منطق تلاش مجدد تطبیقی با تصحیح خطا - یادگیری از کوئری‌های ناموفق
- بازسازی schema برای ساختارهای پایگاه داده در حال تغییر

#### 📊 تحلیل صفحات گسترده
- کوئری‌زنی مبتنی بر Pandas برای فایل‌های Excel/CSV (حداکثر 5 فایل در هر Collection)
- پروفایل‌سازی خودکار داده - انواع ستون‌ها، تحلیل مقادیر null، تشخیص مقادیر یکتا
- بازرسی هوشمند داده - پیشنهاد مقادیر صحیح زمانی که کوئری نتیجه خالی برمی‌گرداند

#### 🔐 امنیت و عملکرد
- رمزنگاری سرتاسر (RSA + AES-ECB) برای تمام ارتباطات client-server
- پاسخ‌های جریانی (streaming) مبتنی بر WebSocket برای تأخیر کم
- کنترل دسترسی به ازای هر Collection با مجوزهای کاربر

#### 🎯 شفافیت کوئری
- نمایش کوئری‌های SQL/Pandas واقعی و نتایج خام
- ردیابی لحظه‌ای اجرای کوئری با تاریخچه تلاش‌ها
- بدون جعبه سیاه - مشاهده دقیق آنچه کوئری می‌شود

---

## موارد استفاده

### 1. تحلیل اسناد و مدارک

**سناریو:** یک سازمان دارای صدها PDF از قراردادها، گزارش‌ها و مدارک فنی است.

**راه‌حل با DataGPT:**
- ایجاد یک Collection از نوع Document-based
- آپلود تمام فایل‌های PDF
- پرسش سوالات به زبان طبیعی:
  - "قراردادهایی که در سال 1402 منقضی می‌شوند را پیدا کن"
  - "خلاصه‌ای از گزارش‌های فصل سوم به من بده"
  - "آیا در این اسناد به موضوع امنیت سایبری اشاره شده است؟"

### 2. تحلیل دیتابیس کسب‌وکار

**سناریو:** مدیر فروش نیاز به گزارش‌های سریع از دیتابیس فروش دارد اما SQL بلد نیست.

**راه‌حل با DataGPT:**
- اتصال دیتابیس MySQL یا PostgreSQL شرکت به سیستم
- پرسش سوالات تجاری:
  - "مجموع فروش ماه گذشته چقدر بوده؟"
  - "10 مشتری برتر به لحاظ میزان خرید را نشان بده"
  - "تعداد سفارش‌های در حال انتظار را بشمار"
  - "محصولاتی که موجودی کمتر از 10 دارند کدامند؟"

### 3. تحلیل گزارش‌های اکسل

**سناریو:** تیم منابع انسانی گزارش‌های ماهانه حضور و غیاب را در Excel نگه می‌دارد.

**راه‌حل با DataGPT:**
- آپلود فایل‌های Excel ماهانه (حداکثر 5 فایل)
- تحلیل داده:
  - "میانگین ساعت کاری کارکنان در ماه گذشته چقدر بوده؟"
  - "کارمندانی که بیش از 3 روز غیبت داشتند را نشان بده"
  - "توزیع کارکنان بر اساس بخش‌ها چگونه است؟"

### 4. پشتیبانی مشتری

**سناریو:** تیم پشتیبانی نیاز به دسترسی سریع به مستندات محصول دارد.

**راه‌حل با DataGPT:**
- ایجاد Collection از راهنماهای کاربری و FAQ
- پاسخگویی سریع به سوالات مشتریان با استناد به اسناد
- کاهش زمان پاسخگویی از ساعت‌ها به ثانیه‌ها

### 5. تحقیقات علمی

**سناریو:** محقق نیاز به جستجو در مقالات و پایان‌نامه‌ها دارد.

**راه‌حل با DataGPT:**
- ساخت Collection از مقالات PDF
- یافتن سریع منابع مرتبط با موضوع خاص
- استخراج اطلاعات و آمار از متون علمی

---

## راهنمای استفاده

### پیش‌نیازها

قبل از شروع، موارد زیر را نصب کنید:
- Python 3.8+
- Django 4.x
- vLLM (برای اجرای مدل LLM)
- ChromaDB
- Redis (برای WebSocket)

### مرحله 1: نصب و راه‌اندازی

#### 1.1 نصب وابستگی‌ها

```bash
# نصب پکیج‌های اصلی
pip install -r requirements.txt

# نصب درایورهای اختیاری پایگاه داده (در صورت نیاز)
pip install pymysql              # برای MySQL
pip install psycopg2-binary      # برای PostgreSQL
pip install pymongo              # برای MongoDB
```

#### 1.2 اعمال مایگریشن‌های دیتابیس

```bash
python manage.py migrate
```

#### 1.3 ایجاد کاربر ادمین

```bash
python manage.py createsuperuser
```

#### 1.4 اجرای سرور Django

```bash
python manage.py runserver
```

### مرحله 2: راه‌اندازی سرور LLM (vLLM)

برای استفاده کامل از قابلیت‌های سیستم، باید سرور vLLM را راه‌اندازی کنید:

```bash
# در WSL یا لینوکس
vllm serve <model_name> --port 8000 --gpu-memory-utilization 0.9
```

**نکته:** آدرس سرور LLM را در فایل `main/utilities/variables.py` تنظیم کنید.

### مرحله 3: استفاده از سیستم

#### 3.1 ایجاد Collection (مجموعه)

1. به صفحه Collections بروید
2. روی "Create new collection" کلیک کنید
3. نوع Collection را انتخاب کنید:

**الف) Document-based Collection (مبتنی بر اسناد):**
- نام Collection را وارد کنید
- فایل‌های PDF، TXT یا سایر اسناد را آپلود کنید
- توضیحات (اختیاری) اضافه کنید
- روی "Create" کلیک کنید

**ب) Database-backed Collection (مبتنی بر دیتابیس):**
- نام Collection را وارد کنید
- نوع دیتابیس را انتخاب کنید (SQLite, MySQL, PostgreSQL, MongoDB)
- برای SQLite: فایل .db یا .sqlite را آپلود کنید
- برای سایر دیتابیس‌ها: Connection String را وارد کنید
  - مثال MySQL: `mysql://username:password@host:port/database`
  - مثال PostgreSQL: `postgresql://username:password@host:port/database`
  - مثال MongoDB: `mongodb://username:password@host:port/database`
- اطلاعات اضافی درباره دیتابیس (اختیاری)
- روی "Create" کلیک کنید و منتظر تحلیل schema بمانید

**ج) Excel/CSV-backed Collection (مبتنی بر اکسل):**
- نام Collection را وارد کنید
- حداکثر 5 فایل Excel یا CSV را آپلود کنید
- توضیحات درباره داده‌ها (اختیاری)
- روی "Create" کلیک کنید

#### 3.2 ایجاد Thread (گفتگو)

1. روی "New Thread" کلیک کنید
2. نام Thread را وارد کنید
3. Collection پایه را انتخاب کنید (اختیاری)
4. Thread ایجاد می‌شود

#### 3.3 چت با داده‌ها

**برای اسناد (Document Collections):**
1. Thread مورد نظر را انتخاب کنید
2. بین دو حالت انتخاب کنید:
   - **Standard Mode:** گفتگوی معمولی با LLM
   - **RAG Mode:** جستجو در اسناد
3. در RAG Mode می‌توانید تنظیمات زیر را تغییر دهید:
   - تعداد نتایج بازیابی (Top K)
   - تعداد نتایج نهایی (Top N)
   - Similarity Threshold

**برای دیتابیس و اکسل:**
1. Thread مورد نظر را انتخاب کنید
2. بین دو حالت انتخاب کنید:
   - **Standard Mode:** گفتگوی معمولی
   - **Database Mode:** کوئری‌زنی از دیتابیس/اکسل
3. سوال خود را به زبان طبیعی بپرسید

**نمونه سوالات:**

*برای SQL Database:*
```
- جدول‌های موجود در این دیتابیس چیست؟
- 10 رکورد اول از جدول users را نشان بده
- مجموع فروش سال 2024 چقدر است؟
- مشتریانی که از کالیفرنیا هستند را پیدا کن
- تعداد سفارش‌های ماه گذشته چقدر بوده؟
```

*برای Excel/CSV:*
```
- 20 سطر اول را نشان بده
- میانگین ستون price چقدر است؟
- سطرهایی که status آنها 'completed' است را فیلتر کن
- بر اساس category گروه‌بندی کن و مجموع amounts را محاسبه کن
- مقادیر یکتای ستون region را نشان بده
```

#### 3.4 مشاهده جزئیات کوئری

برای Collection های دیتابیسی و اکسل:
1. بعد از دریافت پاسخ، روی دکمه "View Context" کلیک کنید
2. کوئری SQL/Pandas اجرا شده را مشاهده کنید
3. نتایج خام را ببینید
4. تاریخچه تلاش‌ها را (در صورت خطا و retry) بررسی کنید

### مرحله 4: مدیریت دسترسی‌ها

#### 4.1 ایجاد گروه کاربری

1. به پنل Admin Django بروید (`/admin`)
2. Groups را انتخاب کنید
3. گروه جدید ایجاد کنید (مثلاً "Sales Team")

#### 4.2 اختصاص دسترسی به Collection

1. به صفحه Collection بروید
2. Allowed Groups را انتخاب کنید
3. گروه‌های مجاز را تعیین کنید

**نکته:** فقط کاربران عضو گروه‌های مجاز می‌توانند Collection را ببینند و از آن استفاده کنند.

---

## راهنمای استقرار

### روش 1: استقرار روی سرور لینوکس

#### الف) پیش‌نیازها

```bash
# به‌روزرسانی سیستم
sudo apt update && sudo apt upgrade -y

# نصب Python و ابزارهای مورد نیاز
sudo apt install python3 python3-pip python3-venv nginx redis-server -y

# نصب CUDA (برای استفاده از GPU با vLLM)
# راهنمای نصب CUDA را از سایت NVIDIA دنبال کنید
```

#### ب) دانلود و راه‌اندازی پروژه

```bash
# کلون کردن پروژه
git clone <repository_url>
cd RAG-webapp

# ایجاد محیط مجازی
python3 -m venv venv
source venv/bin/activate

# نصب وابستگی‌ها
pip install -r requirements.txt
pip install gunicorn uvicorn[standard]
```

#### ج) تنظیمات Django

```bash
# ایجاد فایل .env
nano .env
```

محتویات فایل `.env`:

```env
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,your-server-ip
DATABASE_URL=postgresql://user:password@localhost/dbname
REDIS_URL=redis://localhost:6379/0
```

```bash
# اعمال مایگریشن‌ها
python manage.py migrate

# جمع‌آوری فایل‌های استاتیک
python manage.py collectstatic --noinput

# ایجاد superuser
python manage.py createsuperuser
```

#### د) راه‌اندازی Gunicorn با Systemd

ایجاد فایل سرویس:

```bash
sudo nano /etc/systemd/system/datagpt.service
```

محتویات فایل:

```ini
[Unit]
Description=DataGPT Django Application
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
RuntimeDirectory=gunicorn
WorkingDirectory=/path/to/RAG-webapp
Environment="PATH=/path/to/RAG-webapp/venv/bin"
ExecStart=/path/to/RAG-webapp/venv/bin/gunicorn \
          --workers 4 \
          --bind unix:/run/gunicorn/datagpt.sock \
          RAG.wsgi:application

[Install]
WantedBy=multi-user.target
```

فعال‌سازی و شروع سرویس:

```bash
sudo systemctl daemon-reload
sudo systemctl start datagpt
sudo systemctl enable datagpt
sudo systemctl status datagpt
```

#### ه) راه‌اندازی Daphne برای WebSocket

ایجاد فایل سرویس:

```bash
sudo nano /etc/systemd/system/datagpt-ws.service
```

محتویات فایل:

```ini
[Unit]
Description=DataGPT WebSocket Server
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/RAG-webapp
Environment="PATH=/path/to/RAG-webapp/venv/bin"
ExecStart=/path/to/RAG-webapp/venv/bin/daphne \
          -u /run/daphne/datagpt-ws.sock \
          RAG.asgi:application

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl start datagpt-ws
sudo systemctl enable datagpt-ws
```

#### و) پیکربندی Nginx

```bash
sudo nano /etc/nginx/sites-available/datagpt
```

محتویات فایل:

```nginx
upstream django {
    server unix:/run/gunicorn/datagpt.sock;
}

upstream websocket {
    server unix:/run/daphne/datagpt-ws.sock;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    client_max_body_size 100M;

    location /static/ {
        alias /path/to/RAG-webapp/staticfiles/;
    }

    location /media/ {
        alias /path/to/RAG-webapp/media/;
    }

    location /ws/ {
        proxy_pass http://websocket;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

فعال‌سازی سایت:

```bash
sudo ln -s /etc/nginx/sites-available/datagpt /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### ز) راه‌اندازی vLLM

ایجاد فایل سرویس برای vLLM:

```bash
sudo nano /etc/systemd/system/vllm.service
```

محتویات:

```ini
[Unit]
Description=vLLM Server
After=network.target

[Service]
Type=simple
User=your-user
Environment="CUDA_VISIBLE_DEVICES=0"
WorkingDirectory=/home/your-user
ExecStart=/usr/local/bin/vllm serve meta-llama/Meta-Llama-3-8B-Instruct \
          --port 8000 \
          --gpu-memory-utilization 0.9 \
          --max-model-len 4096

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl start vllm
sudo systemctl enable vllm
```

#### ح) راه‌اندازی SSL با Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### روش 2: استقرار با Docker

#### الف) ایجاد Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# نصب وابستگی‌های سیستمی
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# کپی و نصب requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn uvicorn[standard] daphne

# کپی پروژه
COPY . .

# جمع‌آوری فایل‌های استاتیک
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "RAG.wsgi:application"]
```

#### ب) ایجاد docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: datagpt
      POSTGRES_USER: datagptuser
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

  web:
    build: .
    command: gunicorn --bind 0.0.0.0:8000 RAG.wsgi:application
    volumes:
      - .:/app
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    environment:
      - DATABASE_URL=postgresql://datagptuser:secure_password@db:5432/datagpt
      - REDIS_URL=redis://redis:6379/0

  websocket:
    build: .
    command: daphne -b 0.0.0.0 -p 8001 RAG.asgi:application
    volumes:
      - .:/app
    ports:
      - "8001:8001"
    depends_on:
      - db
      - redis
    environment:
      - DATABASE_URL=postgresql://datagptuser:secure_password@db:5432/datagpt
      - REDIS_URL=redis://redis:6379/0

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    depends_on:
      - web
      - websocket

volumes:
  postgres_data:
  static_volume:
  media_volume:
```

#### ج) اجرای Docker Compose

```bash
# ساخت و اجرای کانتینرها
docker-compose up -d

# اعمال مایگریشن‌ها
docker-compose exec web python manage.py migrate

# ایجاد superuser
docker-compose exec web python manage.py createsuperuser

# مشاهده لاگ‌ها
docker-compose logs -f
```

### روش 3: استقرار روی Windows Server

#### الف) نصب پیش‌نیازها

1. دانلود و نصب Python 3.10+ از [python.org](https://www.python.org)
2. دانلود و نصب Redis از [Redis for Windows](https://github.com/microsoftarchive/redis/releases)
3. دانلود و نصب PostgreSQL (اختیاری)

#### ب) راه‌اندازی پروژه

```powershell
# ایجاد محیط مجازی
python -m venv venv
.\venv\Scripts\activate

# نصب وابستگی‌ها
pip install -r requirements.txt
pip install waitress

# اعمال مایگریشن‌ها
python manage.py migrate

# اجرای سرور با Waitress
waitress-serve --port=8000 RAG.wsgi:application
```

#### ج) راه‌اندازی به عنوان Windows Service

از ابزار NSSM (Non-Sucking Service Manager) استفاده کنید:

```powershell
# دانلود NSSM
# https://nssm.cc/download

# نصب سرویس
nssm install DataGPT "C:\path\to\venv\Scripts\python.exe" "C:\path\to\manage.py runserver 0.0.0.0:8000"

# شروع سرویس
nssm start DataGPT
```

---

## مستندات API

### معرفی

DataGPT از Django REST Framework استفاده نمی‌کند، اما endpoint های مشخصی برای عملیات مختلف دارد. تمام ارتباطات client-server رمزنگاری شده است (RSA + AES-ECB).

### احراز هویت

سیستم از Django Session Authentication استفاده می‌کند. برای دسترسی به API ها باید ابتدا لاگین کنید.

#### ورود (Login)

**Endpoint:** `/users/login/`  
**Method:** `POST`  
**Content-Type:** `application/x-www-form-urlencoded`

**پارامترها:**
```
username: نام کاربری
password: رمز عبور
```

**پاسخ موفق:**
- Redirect به صفحه اصلی
- ایجاد session cookie

### Endpoints اصلی

#### 1. لیست Thread ها

**Endpoint:** `/`  
**Method:** `GET`  
**احراز هویت:** Required

**پاسخ:**
```html
صفحه HTML با لیست تمام Thread های کاربر
```

#### 2. مشاهده یک Thread

**Endpoint:** `/<thread_id>/`  
**Method:** `GET` / `POST`  
**احراز هویت:** Required

**پارامترهای GET:**
- `thread_id`: شناسه Thread (integer)

**پارامترهای POST:**
- `encrypted_aes_key`: کلید AES رمزنگاری شده با RSA

**پاسخ:**
```html
صفحه HTML با لیست پیام‌های Thread
پیام‌ها رمزنگاری شده با AES ارسال می‌شوند
```

#### 3. ایجاد Thread جدید

**Endpoint:** `/create_rag`  
**Method:** `POST`  
**احراز هویت:** Required

**پارامترها:**
```
new-rag-name: نام Thread جدید (required)
base-collection-id: شناسه Collection پایه (optional)
files: فایل‌های آپلود شده (multiple files)
```

**مثال با cURL:**
```bash
curl -X POST http://localhost:8000/create_rag \
  -H "Cookie: sessionid=YOUR_SESSION_ID" \
  -F "new-rag-name=My Research Thread" \
  -F "base-collection-id=1" \
  -F "files=@document1.pdf" \
  -F "files=@document2.pdf"
```

**پاسخ موفق:**
- Redirect به Thread جدید

#### 4. لیست Collection ها

**Endpoint:** `/collections/`  
**Method:** `GET`  
**احراز هویت:** Required

**پاسخ:**
```html
صفحه HTML با لیست تمام Collection های قابل دسترس
```

#### 5. مشاهده یک Collection

**Endpoint:** `/collections/<collection_id>/`  
**Method:** `GET`  
**احراز هویت:** Required

**پارامترها:**
- `collection_id`: شناسه Collection (integer)

**پاسخ:**
```html
صفحه HTML با جزئیات Collection و لیست اسناد
```

#### 6. ایجاد Collection جدید

**Endpoint:** `/create_collection`  
**Method:** `POST`  
**احراز هویت:** Required (فقط Supervisor)

**پارامترها:**

*برای Document-based Collection:*
```
new-collection-name: نام Collection (required)
collection-type: "document" (required)
description: توضیحات (optional)
allowed-groups: لیست شناسه گروه‌ها (multiple select)
files: فایل‌های اسناد (multiple files)
```

*برای Database-backed Collection:*
```
new-collection-name: نام Collection (required)
collection-type: "database" (required)
database-type: "sqlite" | "mysql" | "postgresql" | "mongodb" (required)
connection-string: رشته اتصال یا فایل (required)
db-extra-knowledge: اطلاعات اضافی (optional)
allowed-groups: لیست شناسه گروه‌ها (multiple select)
```

*برای Excel/CSV Collection:*
```
new-collection-name: نام Collection (required)
collection-type: "excel" (required)
excel-files: فایل‌های Excel/CSV - حداکثر 5 فایل (required)
description: توضیحات (optional)
allowed-groups: لیست شناسه گروه‌ها (multiple select)
```

**مثال با Python requests:**

```python
import requests

session = requests.Session()

# ورود
login_data = {'username': 'admin', 'password': 'password'}
session.post('http://localhost:8000/users/login/', data=login_data)

# ایجاد Collection از نوع دیتابیس
collection_data = {
    'new-collection-name': 'Sales Database',
    'collection-type': 'database',
    'database-type': 'mysql',
    'connection-string': 'mysql://user:pass@localhost:3306/sales_db',
    'db-extra-knowledge': 'This is the main sales database',
    'allowed-groups': [1, 2]  # شناسه گروه‌ها
}

response = session.post('http://localhost:8000/create_collection', data=collection_data)
print(response.status_code)
```

**پاسخ موفق:**
- Redirect به صفحه Collection جدید
- تحلیل schema در پس‌زمینه انجام می‌شود

#### 7. اضافه کردن اسناد به Thread

**Endpoint:** `/Add_docs?thread_id=<thread_id>/`  
**Method:** `POST`  
**احراز هویت:** Required

**پارامترها:**
```
thread_id: شناسه Thread (در URL)
files: فایل‌های جدید (multiple files)
```

#### 8. اضافه کردن اسناد به Collection

**Endpoint:** `/Add_docs?collection_id=<collection_id>/`  
**Method:** `POST`  
**احراز هویت:** Required (فقط Supervisor)

**پارامترها:**
```
collection_id: شناسه Collection (در URL)
files: فایل‌های جدید (multiple files)
```

#### 9. حذف Thread

**Endpoint:** `/delete_thread?thread_id=<thread_id>/`  
**Method:** `GET`  
**احراز هویت:** Required

**پارامترها:**
```
thread_id: شناسه Thread (در URL)
```

**پاسخ موفق:**
- Redirect به صفحه اصلی

#### 10. حذف Collection

**Endpoint:** `/delete_collection?collection_id=<collection_id>/`  
**Method:** `GET`  
**احراز هویت:** Required (فقط Supervisor)

**پارامترها:**
```
collection_id: شناسه Collection (در URL)
```

#### 11. بازسازی ایندکس Collection

**Endpoint:** `/reindex_collection?collection_id=<collection_id>/`  
**Method:** `GET`  
**احراز هویت:** Required (فقط Supervisor)

**پارامترها:**
```
collection_id: شناسه Collection (در URL)
```

**توضیح:**
این endpoint فقط برای Collection های Document-based کاربرد دارد و vector index را بازسازی می‌کند.

#### 12. دانلود فایل از Collection

**Endpoint:** `/download_file?collection_id=<collection_id>&file_index=<file_index>/`  
**Method:** `GET`  
**احراز هویت:** Required

**پارامترها:**
```
collection_id: شناسه Collection (در URL)
file_index: شماره فایل در لیست (در URL)
```

**پاسخ:**
دانلود فایل با Content-Type مناسب

### WebSocket API (برای چت Real-time)

#### اتصال به WebSocket

**URL:** `ws://your-domain/ws/chat/<thread_id>/`  
**Protocol:** WebSocket

#### پیام‌های ارسالی به سرور

**فرمت JSON:**

*حالت Standard:*
```json
{
  "message": "encrypted_message_with_AES",
  "mode": "standard",
  "aes_key": "encrypted_aes_key_with_RSA"
}
```

*حالت RAG:*
```json
{
  "message": "encrypted_message_with_AES",
  "mode": "rag",
  "aes_key": "encrypted_aes_key_with_RSA",
  "top_k": 10,
  "top_n": 5,
  "similarity_threshold": 0.3
}
```

*حالت Database:*
```json
{
  "message": "encrypted_message_with_AES",
  "mode": "database",
  "aes_key": "encrypted_aes_key_with_RSA"
}
```

#### پیام‌های دریافتی از سرور

**پیام معمولی (Streaming):**
```json
{
  "type": "stream",
  "message": "encrypted_token_with_AES"
}
```

**پیام پایان:**
```json
{
  "type": "end",
  "message_id": 123,
  "source_nodes": [...]  // فقط در حالت RAG
}
```

**پیام خطا:**
```json
{
  "type": "error",
  "message": "encrypted_error_message"
}
```

**مثال با JavaScript:**

```javascript
const threadId = 1;
const ws = new WebSocket(`ws://localhost:8000/ws/chat/${threadId}/`);

ws.onopen = function() {
    console.log('WebSocket connected');
    
    // ارسال پیام
    const message = {
        message: encryptedMessage,  // رمزنگاری شده با AES
        mode: 'database',
        aes_key: encryptedAESKey    // رمزنگاری شده با RSA
    };
    
    ws.send(JSON.stringify(message));
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    if (data.type === 'stream') {
        // رمزگشایی و نمایش token
        const token = decryptAES(data.message, aesKey);
        appendToChat(token);
    } else if (data.type === 'end') {
        console.log('Response completed');
    }
};

ws.onerror = function(error) {
    console.error('WebSocket error:', error);
};

ws.onclose = function() {
    console.log('WebSocket closed');
};
```

### کدهای وضعیت (Status Codes)

- `200 OK`: درخواست موفق
- `302 Found`: Redirect
- `400 Bad Request`: پارامترهای نامعتبر
- `401 Unauthorized`: نیاز به ورود
- `403 Forbidden`: عدم دسترسی
- `404 Not Found`: منبع یافت نشد
- `500 Internal Server Error`: خطای سرور

### محدودیت‌ها و نکات

1. **حداکثر حجم آپلود:** پیش‌فرض Django (2.5 MB) - قابل تغییر در settings
2. **حداکثر تعداد فایل‌های Excel در یک Collection:** 5 فایل
3. **رمزنگاری:** تمام پیام‌های چت باید با AES-ECB رمزنگاری شوند
4. **کلید AES:** باید با کلید عمومی RSA سرور رمزنگاری شود
5. **Session Timeout:** پیش‌فرض Django (2 هفته)
6. **Rate Limiting:** در حال حاضر فعال نیست - توصیه می‌شود در production اضافه شود

### نمونه کد کامل - Python Client

```python
import requests
import json
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
import base64
import websocket

class DataGPTClient:
    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.session = requests.Session()
        self.aes_key = get_random_bytes(32)
        self.login(username, password)
        
    def login(self, username, password):
        """ورود به سیستم"""
        login_url = f"{self.base_url}/users/login/"
        data = {'username': username, 'password': password}
        response = self.session.post(login_url, data=data)
        if response.status_code == 200:
            print("Login successful")
        else:
            raise Exception("Login failed")
    
    def encrypt_aes(self, plaintext):
        """رمزنگاری با AES-ECB"""
        cipher = AES.new(self.aes_key, AES.MODE_ECB)
        # Padding
        padding_length = 16 - (len(plaintext) % 16)
        padded = plaintext + (chr(padding_length) * padding_length)
        encrypted = cipher.encrypt(padded.encode('utf-8'))
        return base64.b64encode(encrypted).decode('utf-8')
    
    def decrypt_aes(self, ciphertext):
        """رمزگشایی AES-ECB"""
        cipher = AES.new(self.aes_key, AES.MODE_ECB)
        decrypted = cipher.decrypt(base64.b64decode(ciphertext))
        # Remove padding
        padding_length = decrypted[-1]
        return decrypted[:-padding_length].decode('utf-8')
    
    def create_collection(self, name, collection_type, **kwargs):
        """ایجاد Collection جدید"""
        url = f"{self.base_url}/create_collection"
        
        data = {
            'new-collection-name': name,
            'collection-type': collection_type
        }
        
        if collection_type == 'database':
            data['database-type'] = kwargs.get('database_type')
            data['connection-string'] = kwargs.get('connection_string')
            data['db-extra-knowledge'] = kwargs.get('extra_knowledge', '')
        
        response = self.session.post(url, data=data)
        return response.status_code == 200
    
    def create_thread(self, name, files=None, base_collection_id=None):
        """ایجاد Thread جدید"""
        url = f"{self.base_url}/create_rag"
        
        data = {'new-rag-name': name}
        if base_collection_id:
            data['base-collection-id'] = base_collection_id
        
        files_data = []
        if files:
            for file_path in files:
                files_data.append(('files', open(file_path, 'rb')))
        
        response = self.session.post(url, data=data, files=files_data)
        
        for _, f in files_data:
            f.close()
        
        return response.status_code == 200
    
    def chat_websocket(self, thread_id, message, mode='standard', **kwargs):
        """ارسال پیام از طریق WebSocket"""
        ws_url = f"ws://{self.base_url.replace('http://', '')}/ws/chat/{thread_id}/"
        
        # رمزنگاری پیام
        encrypted_message = self.encrypt_aes(message)
        
        # رمزنگاری کلید AES (نیاز به کلید عمومی سرور دارد)
        # این قسمت را باید بر اساس کلید عمومی واقعی سرور پیاده‌سازی کنید
        encrypted_aes_key = "..."  # Implement RSA encryption
        
        payload = {
            'message': encrypted_message,
            'mode': mode,
            'aes_key': encrypted_aes_key
        }
        
        if mode == 'rag':
            payload.update({
                'top_k': kwargs.get('top_k', 10),
                'top_n': kwargs.get('top_n', 5),
                'similarity_threshold': kwargs.get('similarity_threshold', 0.3)
            })
        
        # اتصال WebSocket و ارسال پیام
        ws = websocket.create_connection(ws_url)
        ws.send(json.dumps(payload))
        
        # دریافت پاسخ
        response = ""
        while True:
            result = ws.recv()
            data = json.loads(result)
            
            if data['type'] == 'stream':
                token = self.decrypt_aes(data['message'])
                response += token
                print(token, end='', flush=True)
            elif data['type'] == 'end':
                print("\n\nResponse completed!")
                break
        
        ws.close()
        return response

# استفاده
if __name__ == "__main__":
    client = DataGPTClient("http://localhost:8000", "admin", "password")
    
    # ایجاد Collection
    client.create_collection(
        name="My Database",
        collection_type="database",
        database_type="sqlite",
        connection_string="/path/to/database.db"
    )
    
    # ایجاد Thread
    client.create_thread(
        name="Research Chat",
        files=["document1.pdf", "document2.pdf"]
    )
    
    # ارسال پیام
    client.chat_websocket(
        thread_id=1,
        message="خلاصه این اسناد را به من بده",
        mode="rag",
        top_k=10
    )
```

---

## معماری فنی

### نمای کلی

DataGPT یک وب‌اپلیکیشن مبتنی بر Django است که از معماری چند لایه استفاده می‌کند:

```
┌─────────────────────────────────────────┐
│         Frontend (HTML/CSS/JS)          │
│  Bootstrap + jQuery + CryptoJS          │
└──────────────┬──────────────────────────┘
               │
               ├─ HTTP/HTTPS (RESTful)
               ├─ WebSocket (Real-time Chat)
               │
┌──────────────▼──────────────────────────┐
│          Django Application             │
│  ┌───────────────────────────────────┐  │
│  │         Views Layer               │  │
│  │  - Authentication                 │  │
│  │  - Request/Response Handling      │  │
│  └─────────┬─────────────────────────┘  │
│            │                             │
│  ┌─────────▼─────────────────────────┐  │
│  │      Business Logic Layer         │  │
│  │  - RAG Processing                 │  │
│  │  - Database Query Generation      │  │
│  │  - Excel/CSV Analysis             │  │
│  └─────────┬─────────────────────────┘  │
│            │                             │
│  ┌─────────▼─────────────────────────┐  │
│  │       Data Access Layer           │  │
│  │  - Models (ORM)                   │  │
│  │  - Vector DB (ChromaDB)           │  │
│  │  - SQL/NoSQL Connections          │  │
│  └───────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │
               ├─ PostgreSQL/SQLite (Metadata)
               ├─ ChromaDB (Vector Storage)
               ├─ Redis (WebSocket/Cache)
               └─ vLLM Server (LLM Inference)
```

### Stack تکنولوژی

#### Backend
- **Django 4.x**: Web framework اصلی
- **Django Channels**: پشتیبانی WebSocket
- **ChromaDB**: Vector database برای RAG
- **LlamaIndex**: Framework برای RAG pipeline
- **Pandas**: تحلیل Excel/CSV
- **SQLAlchemy/PyMongo**: اتصال به دیتابیس‌های خارجی

#### Frontend
- **Bootstrap 5**: UI framework
- **jQuery**: JavaScript library
- **CryptoJS**: رمزنگاری سمت کلاینت
- **JSEncrypt**: RSA encryption

#### Infrastructure
- **vLLM**: سرور LLM با قابلیت streaming
- **Redis**: Message broker برای Channels
- **Nginx**: Reverse proxy و load balancing
- **Gunicorn/Daphne**: WSGI/ASGI servers

### مدل داده (Data Models)

#### User
از مدل پیش‌فرض Django استفاده می‌شود با امکان تعریف Groups.

#### Document
```python
class Document(models.Model):
    user = ForeignKey(User)
    name = CharField(max_length=256)
    loc = CharField(max_length=512)  # مسیر فایل
    public = BooleanField(default=False)
    description = TextField(max_length=1024)
    time_created = DateTimeField(auto_now_add=True)
    sha256 = CharField(max_length=64)  # Hash فایل
```

#### Collection
```python
class Collection(models.Model):
    user_created = ForeignKey(User)
    name = CharField(max_length=128)
    docs = ManyToManyField(Document)
    allowed_groups = ManyToManyField(Group)
    description = TextField(max_length=1024)
    time_created = DateTimeField(auto_now_add=True)
    loc = CharField(max_length=512)
    
    # نوع Collection
    collection_type = CharField(choices=[
        ('document', 'Document-based'),
        ('database', 'Database-backed'),
        ('excel', 'Excel/CSV-backed')
    ])
    
    # فیلدهای مخصوص Database
    db_type = CharField(choices=[
        ('mysql', 'MySQL'),
        ('postgresql', 'PostgreSQL'),
        ('sqlite', 'SQLite'),
        ('mongodb', 'MongoDB')
    ])
    db_connection_string = TextField()
    db_schema_analysis = TextField()  # تحلیل LLM از schema
    db_extra_knowledge = TextField()  # اطلاعات اضافی
    
    # فیلدهای مخصوص Excel
    excel_file_paths = JSONField()  # لیست مسیر فایل‌ها
```

#### Thread
```python
class Thread(models.Model):
    user = ForeignKey(User)
    name = CharField(max_length=32)
    docs = ManyToManyField(Document)
    loc = CharField(max_length=512)  # مسیر vector DB
    description = TextField(max_length=1024)
    time_created = DateTimeField(auto_now_add=True)
    base_collection = ForeignKey(Collection, null=True)
```

#### ChatMessage
```python
class ChatMessage(models.Model):
    thread = ForeignKey(Thread)
    user = ForeignKey(User)
    rag_response = BooleanField(default=False)
    message = TextField()
    timestamp = DateTimeField(auto_now_add=True)
    source_nodes = JSONField()  # منابع RAG
```

### جریان کاری (Workflow)

#### 1. Document-based RAG Flow

```
User Query
    ↓
[Encrypt with AES]
    ↓
[Send via WebSocket]
    ↓
[Decrypt on Server]
    ↓
[Query Vector DB (ChromaDB)]
    ↓
[Retrieve Top-K Chunks]
    ↓
[Rerank with Similarity Score]
    ↓
[Select Top-N Chunks]
    ↓
[Build Context Prompt]
    ↓
[Send to vLLM Server]
    ↓
[Stream Response Tokens]
    ↓
[Encrypt Each Token]
    ↓
[Send to Client via WebSocket]
    ↓
[Decrypt and Display]
```

#### 2. Database Query Flow

```
User Question
    ↓
[Understand Intent]
    ↓
[Load DB Schema Analysis]
    ↓
[Generate SQL/NoSQL Query via LLM]
    ↓
[Execute Query on Database]
    ↓
    ├─ Success → [Format Results]
    │               ↓
    │           [Send to LLM for Natural Language Response]
    │
    └─ Error → [Analyze Error]
                    ↓
                [Retry with Corrected Query (Max 3 times)]
                    ↓
                    ├─ Success → Continue
                    └─ Fail → [Return User-Friendly Error]
```

#### 3. Excel Query Flow

```
User Question
    ↓
[Load Excel Files with Pandas]
    ↓
[Analyze Data Structure]
    ↓
[Generate Pandas Code via LLM]
    ↓
[Execute Code]
    ↓
    ├─ Success → [Format Results]
    └─ Error → [Retry with Correction]
         ↓
     [Send Results to LLM]
         ↓
     [Generate Natural Language Response]
```

### امنیت

#### رمزنگاری
- **RSA-2048**: رمزنگاری کلید AES
- **AES-256-ECB**: رمزنگاری پیام‌های چت
- **HTTPS**: رمزنگاری transport layer (در production)

#### احراز هویت و مجوزها
- **Django Authentication**: مدیریت session و کاربر
- **Group-based Access Control**: کنترل دسترسی به Collection ها
- **Permission Decorators**: `@login_required`, `@permission_required`

#### محافظت در برابر حملات
- **CSRF Protection**: Django CSRF middleware
- **XSS Protection**: Template auto-escaping
- **SQL Injection**: استفاده از ORM و parameterized queries
- **File Upload Validation**: بررسی نوع و حجم فایل

### عملکرد و مقیاس‌پذیری

#### Optimization Techniques
1. **Database Indexing**: ایندکس‌گذاری روی فیلدهای پرجستجو
2. **Vector DB Caching**: ذخیره نتایج جستجوی مشابه
3. **Redis Caching**: کش کردن schema analysis
4. **Lazy Loading**: بارگذاری تنبل برای Collection های بزرگ
5. **Async Processing**: استفاده از Channels برای عملیات طولانی

#### Scalability Considerations
- **Horizontal Scaling**: افزودن سرورهای Django بیشتر با load balancer
- **Database Sharding**: تقسیم vector DB بر اساس کاربر
- **LLM Server Pool**: چندین instance vLLM برای توان عملیاتی بیشتر
- **Redis Cluster**: مقیاس‌پذیری message broker

### نظارت و Logging

#### Logging Levels
```python
import logging

logger = logging.getLogger(__name__)

# DEBUG: جزئیات برنامه برای debugging
logger.debug(f"Query generated: {query}")

# INFO: اطلاعات عمومی
logger.info(f"Collection created: {collection_name}")

# WARNING: هشدارها
logger.warning(f"Retry attempt {attempt}/3")

# ERROR: خطاهای قابل بازیابی
logger.error(f"Database connection failed: {error}")

# CRITICAL: خطاهای بحرانی
logger.critical(f"System shutdown: {reason}")
```

#### Monitoring Metrics
- تعداد query های روزانه
- میانگین زمان پاسخ
- نرخ خطا و retry
- استفاده از منابع (CPU, RAM, GPU)
- تعداد کاربران فعال همزمان

---

## نتیجه‌گیری

DataGPT یک پلتفرم قدرتمند برای تعامل با داده‌های متنوع به زبان طبیعی است که:

✅ از انواع منابع داده پشتیبانی می‌کند (اسناد، دیتابیس، Excel)  
✅ امنیت بالا با رمزنگاری سرتاسر دارد  
✅ رابط کاربری ساده و کاربرپسند  
✅ قابلیت مقیاس‌پذیری و سفارشی‌سازی  
✅ شفافیت کامل در کوئری‌ها و نتایج  

این سیستم می‌تواند در سازمان‌ها، موسسات تحقیقاتی و شرکت‌های مختلف برای افزایش بهره‌وری و تسریع دسترسی به اطلاعات استفاده شود.

---

## پشتیبانی و تماس

برای سوالات و پشتیبانی:
- **مستندات:** این فایل
- **Issues:** GitHub Issues (در صورت وجود مخزن)
- **Email:** [ایمیل پشتیبانی]

---

**نسخه:** 1.0  
**تاریخ:** دی 1404 (ژانویه 2026)  
**وضعیت:** فعال و در حال توسعه

</div>
