# Instagram Auto

Bot de Telegram para automatizar la descarga, edición y publicación programada de videos en múltiples cuentas Business de Instagram.

## Stack

Python 3.11+ · python-telegram-bot · yt-dlp · ffmpeg · supabase-py · APScheduler · Oracle Cloud ARM

## Arrancar en local

```
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env   # rellenar valores reales
py main.py
```

Ver [00_OVERVIEW.md](00_OVERVIEW.md) para arquitectura completa y fases de desarrollo.
