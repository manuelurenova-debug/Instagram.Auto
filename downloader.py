import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yt_dlp
import yt_dlp.utils as yt_utils

from config import VIDEOS_DIR, INSTAGRAM_COOKIES_FILE

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)
_TEMP_DIR = VIDEOS_DIR / "temp"


class DownloadError(Exception):
    pass


def cleanup_old_temp_files(max_age_hours: int = 24) -> int:
    cutoff = time.time() - max_age_hours * 3600
    deleted = 0
    for f in _TEMP_DIR.iterdir():
        if f.is_file() and f.name != ".gitkeep" and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                logger.info("Limpieza temp: borrado %s", f.name)
                deleted += 1
            except OSError as e:
                logger.warning("No se pudo borrar %s: %s", f.name, e)
    if deleted:
        logger.info("Limpieza temp: %d archivo(s) borrado(s).", deleted)
    return deleted


def _classify_error(msg: str) -> str:
    m = msg.lower()
    if any(k in m for k in ("private", "login required", "log in", "authentication")):
        return "❌ El contenido es privado o requiere login."
    if any(k in m for k in ("not available in your country", "geo", "your region", "not available in your location")):
        return "❌ Video no disponible en tu región."
    if any(k in m for k in ("unable to download webpage", "connection", "timeout", "timed out", "network")):
        return "❌ Error de red al descargar. Vuelve a intentarlo."
    if any(k in m for k in ("no video", "unable to extract", "not found", "404", "doesn't exist")):
        return "❌ No se encontró ningún video en esa URL."
    return f"❌ Error descargando: {msg}"


def _download_video_sync(url: str) -> Path:
    cleanup_old_temp_files()

    _TEMP_DIR.mkdir(parents=True, exist_ok=True)

    outtmpl = str(_TEMP_DIR / "%(id)s_%(timestamp)s.%(ext)s")
    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
    }

    if INSTAGRAM_COOKIES_FILE.exists():
        ydl_opts["cookiefile"] = str(INSTAGRAM_COOKIES_FILE)
    else:
        logger.warning(
            "Archivo de cookies no encontrado (%s) — se descargará sin autenticación.",
            INSTAGRAM_COOKIES_FILE,
        )

    start = time.time()
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_utils.DownloadError as e:
        raise DownloadError(_classify_error(str(e))) from e
    except Exception as e:
        raise DownloadError(f"❌ Error inesperado en la descarga: {e}") from e

    if not info:
        raise DownloadError("❌ No se encontró ningún video en esa URL.")

    # Reconstruir la ruta final (el postprocessor cambia la ext a .mp4)
    expected = Path(outtmpl % {
        "id": info.get("id", "unknown"),
        "timestamp": info.get("timestamp") or int(time.time()),
        "ext": "mp4",
    })

    # Fallback: buscar el archivo más reciente en temp si el nombre calculado no existe
    if not expected.exists():
        candidates = sorted(_TEMP_DIR.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            raise DownloadError("❌ No se encontró ningún video en esa URL.")
        expected = candidates[0]

    duration = time.time() - start
    logger.info("Descarga completada: url=%s archivo=%s tiempo=%.1fs", url, expected.name, duration)
    return expected


async def download_video(url: str) -> Path:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _download_video_sync, url)
