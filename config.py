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

# Archivo cookies.txt (formato Netscape) con una sesión de Instagram exportada.
# Necesario porque Instagram bloquea peticiones anónimas incluso a contenido público.
# --cookies-from-browser no es fiable con Chrome moderno (App-Bound Encryption).
INSTAGRAM_COOKIES_FILE: Path = BASE_DIR / os.getenv("INSTAGRAM_COOKIES_FILE", "cookies.txt")

# En Railway (u otro entorno sin el archivo ya presente en disco) se reconstruye
# cookies.txt a partir de INSTAGRAM_COOKIES_B64 (el archivo local codificado en
# base64, pegado como variable de entorno). En local no hace nada: el archivo
# ya existe y esta variable no está definida.
if not INSTAGRAM_COOKIES_FILE.exists():
    _cookies_b64 = os.getenv("INSTAGRAM_COOKIES_B64")
    if _cookies_b64:
        import base64
        INSTAGRAM_COOKIES_FILE.write_bytes(base64.b64decode(_cookies_b64))

def _load_ig_account(n: int) -> dict | None:
    """Carga la cuenta N solo si tiene ID y TOKEN rellenados en .env. Si no, se omite."""
    ig_id = os.getenv(f"IG_ACCOUNT_{n}_ID")
    token = os.getenv(f"IG_ACCOUNT_{n}_TOKEN")
    if not ig_id or not token:
        return None
    return {
        "id": ig_id,
        "token": token,
        "expires": _parse_expires(
            os.getenv(f"IG_ACCOUNT_{n}_TOKEN_EXPIRES", ""), f"IG_ACCOUNT_{n}_TOKEN_EXPIRES"
        ),
        "caption": os.getenv(f"IG_ACCOUNT_{n}_CAPTION", ""),
    }

IG_ACCOUNTS: dict = {}
for _n in (1, 2, 3):
    _account = _load_ig_account(_n)
    if _account:
        IG_ACCOUNTS[f"cuenta_{_n}"] = _account
    else:
        print(f"[AVISO] cuenta_{_n} no configurada (falta IG_ACCOUNT_{_n}_ID o IG_ACCOUNT_{_n}_TOKEN) — se omite.")

if not IG_ACCOUNTS:
    print("[ERROR] No hay ninguna cuenta de Instagram configurada en .env")
    sys.exit(1)

VALID_ACCOUNTS: list[str] = list(IG_ACCOUNTS.keys())
