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

def _parse_hhmm(hhmm: str) -> tuple[int, int]:
    try:
        h, m = hhmm.strip().split(":")
        h, m = int(h), int(m)
    except (ValueError, AttributeError):
        raise ValueError(f"Formato de hora inválido: '{hhmm}'. Usa HH:MM (ej: 14:30).")

    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Hora fuera de rango: '{hhmm}'. Usa HH:MM (ej: 14:30).")

    return h, m

def parse_time(hhmm: str) -> datetime:
    """Hora de hoy si aún no ha pasado, si no de mañana (sin fecha explícita)."""
    h, m = _parse_hhmm(hhmm)

    now = datetime.now(tz=MADRID_TZ)
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        # Usar timedelta para evitar problemas de fin de mes
        from datetime import timedelta
        target = target + timedelta(days=1)
    return target

def parse_date_time(yyyy_mm_dd: str, hhmm: str) -> datetime:
    """Fecha y hora explícitas. Debe ser un momento futuro."""
    try:
        fecha = datetime.strptime(yyyy_mm_dd.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Formato de fecha inválido: '{yyyy_mm_dd}'. Usa YYYY-MM-DD (ej: 2026-08-15).")

    h, m = _parse_hhmm(hhmm)
    target = datetime(fecha.year, fecha.month, fecha.day, h, m, tzinfo=MADRID_TZ)

    if target <= datetime.now(tz=MADRID_TZ):
        raise ValueError(f"'{yyyy_mm_dd} {hhmm}' ya ha pasado. Usa una fecha y hora futuras.")

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
