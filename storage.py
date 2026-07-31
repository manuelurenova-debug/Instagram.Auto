import logging
from datetime import datetime, timezone
from pathlib import Path

from database import get_client, obtener_archivos_en_uso
from config import SUPABASE_BUCKET

logger = logging.getLogger(__name__)


class StorageError(Exception):
    pass


def upload_video(local_path: Path) -> str:
    """Sube el archivo al bucket público y devuelve su URL pública."""
    file_name = local_path.name
    try:
        with open(local_path, "rb") as f:
            get_client().storage.from_(SUPABASE_BUCKET).upload(
                path=file_name,
                file=f,
                file_options={"content-type": "video/mp4", "upsert": "true"},
            )
        public_url = get_client().storage.from_(SUPABASE_BUCKET).get_public_url(file_name)
        logger.info("Subido al bucket: %s → %s", file_name, public_url)
        return public_url
    except Exception as e:
        logger.error("Error subiendo %s al bucket: %s", file_name, e)
        raise StorageError(f"Error subiendo video al Storage: {e}") from e


def delete_video(file_name: str) -> None:
    """Borra el archivo del bucket para liberar espacio del 1GB free."""
    try:
        get_client().storage.from_(SUPABASE_BUCKET).remove([file_name])
        logger.info("Borrado del bucket: %s", file_name)
    except Exception as e:
        logger.warning("No se pudo borrar %s del bucket: %s", file_name, e)


def limpiar_huerfanos(edad_minima_horas: float = 1.0) -> list[str]:
    """Red de seguridad: borra del bucket cualquier archivo que no corresponda
    a una publicación pendiente/en proceso. El flujo normal ya limpia en
    /add (si falla tras subir), /cancelar y al publicar (éxito o error) —
    esto cubre lo que se escape (p.ej. un crash a media subida). Se exige
    una antigüedad mínima para no pisar una subida legítima en curso.
    Si no se puede confirmar qué está en uso, no borra nada (falla seguro)."""
    try:
        en_uso = obtener_archivos_en_uso()
    except Exception as e:
        logger.error("[limpieza Storage] No se pudo consultar archivos en uso, se aborta: %s", e)
        return []

    try:
        archivos = get_client().storage.from_(SUPABASE_BUCKET).list()
    except Exception as e:
        logger.error("[limpieza Storage] No se pudo listar el bucket: %s", e)
        return []

    ahora = datetime.now(timezone.utc)
    borrados: list[str] = []

    for archivo in archivos:
        nombre = archivo.get("name")
        if not nombre or nombre in en_uso:
            continue

        creado = archivo.get("created_at")
        if creado:
            try:
                fecha_creado = datetime.fromisoformat(creado.replace("Z", "+00:00"))
                antiguedad_horas = (ahora - fecha_creado).total_seconds() / 3600
                if antiguedad_horas < edad_minima_horas:
                    continue
            except ValueError:
                pass

        try:
            get_client().storage.from_(SUPABASE_BUCKET).remove([nombre])
            logger.info("[limpieza Storage] Huérfano borrado: %s", nombre)
            borrados.append(nombre)
        except Exception as e:
            logger.warning("[limpieza Storage] No se pudo borrar %s: %s", nombre, e)

    return borrados
