import logging
from pathlib import Path

from database import get_client
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
