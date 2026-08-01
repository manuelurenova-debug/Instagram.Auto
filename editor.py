import asyncio
import json
import logging
import random
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import VIDEOS_DIR

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)


class EditorError(Exception):
    pass


def get_duration(path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            capture_output=True, text=True, check=True,
        )
        return float(json.loads(result.stdout)["format"]["duration"])
    except (subprocess.CalledProcessError, KeyError, ValueError) as e:
        raise EditorError(f"No se pudo leer la duración del video: {e}") from e


def _edit_video_sync(input_path: Path, cuenta: str) -> Path:
    original_duration = get_duration(input_path)
    logger.info("Duración original: %.2fs — archivo: %s", original_duration, input_path.name)

    if original_duration < 2.3:
        raise EditorError("Video demasiado corto para editar (necesita ≥ 2.3s).")

    new_duration = original_duration - 1.3
    fade_duration = 0.5
    fade_out_start = new_duration - fade_duration

    # Anti-detección: zoom-in aleatorio (105%-108%) centrado, distinto en cada edición.
    # scale amplía el frame y crop lo recorta de vuelta al tamaño original desde el centro
    # (crop sin x/y = centrado por defecto), así nunca aparecen bordes negros.
    zoom = random.uniform(1.05, 1.08)

    output_dir = VIDEOS_DIR / cuenta
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{int(time.time())}_{cuenta}.mp4"

    filtros = (
        f"scale=trunc(iw*{zoom:.5f}/2)*2:trunc(ih*{zoom:.5f}/2)*2,"
        f"crop=trunc(iw/{zoom:.5f}/2)*2:trunc(ih/{zoom:.5f}/2)*2,"
        f"fade=t=in:st=0:d={fade_duration},"
        f"fade=t=out:st={fade_out_start:.3f}:d={fade_duration}"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-t", f"{new_duration:.3f}",
        "-vf", filtros,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]

    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("ffmpeg falló (stderr): %s", result.stderr[-500:])
        raise EditorError(f"ffmpeg falló: {result.stderr[:200]}")

    elapsed = time.time() - start
    logger.info(
        "Edición completada: %.2fs → %.2fs (-1.3s), zoom %.2f%%, fade %.1fs, tiempo=%.1fs, output=%s",
        original_duration, new_duration, zoom * 100, fade_duration, elapsed, output_path.name,
    )

    # Borrar temp solo si la edición fue exitosa
    try:
        input_path.unlink(missing_ok=True)
        logger.info("Borrado archivo temporal: %s", input_path.name)
    except OSError as e:
        logger.warning("No se pudo borrar el temporal %s: %s", input_path.name, e)

    return output_path


async def edit_video(input_path: Path, cuenta: str) -> Path:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, _edit_video_sync, input_path, cuenta)
