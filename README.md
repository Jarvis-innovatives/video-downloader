# SnapGrab — Video & MP3 Downloader (Django Application)

SnapGrab is a web application built with **Django** and a dark theme UI design system for downloading videos and audio from YouTube, Instagram, and TikTok.

## Features

- **Full Django 5 Backend Architecture**: Built with Python 3.12 and Django 5.x.
- **SQLite ORM Database Logging**: Every download request is logged via Django's `DownloadLog` model and accessible via Django Admin.
- **Modern Dark UI Design**: Signal orange accent theme, fontshare fonts (Clash Display & Satoshi), card glow effects, and responsive layout.
- **Format & Quality Selection**: Support for video formats (240p up to 4K) and MP3 audio extraction (128 to 320 kbps).
- **Interactive API Endpoints**: Django JSON API endpoints (`/api/fetch/` and `/api/download/`).

## Setup and Running Locally

### 1. Requirements
- Python 3.10+
- Django 5.x

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Create Superuser (Optional - for Django Admin)
```bash
python manage.py createsuperuser
```

### 5. Start Development Server
```bash
python manage.py runserver
```

Open your browser and navigate to `http://127.0.0.1:8000/`.
