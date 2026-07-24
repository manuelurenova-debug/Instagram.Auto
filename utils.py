import re
import logging
import functools
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from config import TELEGRAM_CHAT_ID

MADRID_TZ = ZoneInfo("Europe/Madrid")

def is_valid_instagram_url(url: str) -> bool:
    pattern = r"^https?://(www\.)?instagram\.com/(reel|p)/[\w-]+/?(\?.*)?$"
    return bool(re.match(pattern, url))

def parse_time(hhmm: str) -> datetime:
    try:
        h, m = hhmm.strip().split(":")
        h, m = int(h), int(m)
    except (ValueError, AttributeError):
        raise ValueError(f"Formato de hora inválido: '{hhmm}'. Usa HH:MM (ej: 14:30).")

    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Hora fuera de rango: '{hhmm}'. Usa HH:MM (ej: 14:30).")

    now = datetime.now(tz=MADRID_TZ)
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        # Usar timedelta para evitar problemas de fin de mes
        from datetime import timedelta
        target = target + timedelta(days=1)
    return target

def setup_logging() -> None:
    log_format = "[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    log_file = Path(__file__).parent / "instagram-auto.log"
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))

    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])

def only_owner(func):
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_chat.id != TELEGRAM_CHAT_ID:
            await update.message.reply_text("⛔ No autorizado.")
            logging.warning("Acceso no autorizado desde chat_id=%s", update.effective_chat.id)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
