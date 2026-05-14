import os
import sys
import logging
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
VIDEOS_DIR = BASE_DIR / "videos"

def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"[ERROR] Variable de entorno requerida no encontrada: {name}")
        print("Copia .env.example a .env y rellena todos los valores.")
        sys.exit(1)
    return value

def _parse_expires(value: str, var_name: str) -> date:
    if not value:
        logging.warning("Variable %s no definida — aviso de caducidad desactivado.", var_name)
        return date(2099, 1, 1)
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        print(f"[ERROR] Formato inválido en {var_name}: '{value}'. Usa YYYY-MM-DD.")
        sys.exit(1)

TELEGRAM_TOKEN: str = _require("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID: int = int(_require("TELEGRAM_CHAT_ID"))

SUPABASE_URL: str = _require("SUPABASE_URL")
SUPABASE_KEY: str = _require("SUPABASE_KEY")
SUPABASE_BUCKET: str = os.getenv("SUPABASE_BUCKET", "videos-temp")

IG_ACCOUNTS: dict = {
    "cuenta_1": {
        "id": _require("IG_ACCOUNT_1_ID"),
        "token": _require("IG_ACCOUNT_1_TOKEN"),
        "expires": _parse_expires(os.getenv("IG_ACCOUNT_1_TOKEN_EXPIRES", ""), "IG_ACCOUNT_1_TOKEN_EXPIRES"),
    },
    "cuenta_2": {
        "id": _require("IG_ACCOUNT_2_ID"),
        "token": _require("IG_ACCOUNT_2_TOKEN"),
        "expires": _parse_expires(os.getenv("IG_ACCOUNT_2_TOKEN_EXPIRES", ""), "IG_ACCOUNT_2_TOKEN_EXPIRES"),
    },
    "cuenta_3": {
        "id": _require("IG_ACCOUNT_3_ID"),
        "token": _require("IG_ACCOUNT_3_TOKEN"),
        "expires": _parse_expires(os.getenv("IG_ACCOUNT_3_TOKEN_EXPIRES", ""), "IG_ACCOUNT_3_TOKEN_EXPIRES"),
    },
}

VALID_ACCOUNTS: list[str] = list(IG_ACCOUNTS.keys())
