import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, render_template, jsonify, send_file, abort, request

from config import BASE_DIR, VIDEOS_DIR
from database import obtener_programados, obtener_historial_dashboard, DatabaseError

MADRID_TZ = ZoneInfo("Europe/Madrid")
LOG_FILE = BASE_DIR / "instagram-auto.log"
THUMBNAILS_DIR = VIDEOS_DIR / ".thumbnails"
UMBRAL_ACTIVO_SEGUNDOS = 90

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

app = Flask(__name__)


def _parse_iso(valor: str) -> datetime:
    return datetime.fromisoformat(valor).astimezone(MADRID_TZ)


def _estado_bot() -> dict:
    if not LOG_FILE.exists():
        return {"activo": False, "ultima_actividad": None}
    mtime = LOG_FILE.stat().st_mtime
    activo = (time.time() - mtime) < UMBRAL_ACTIVO_SEGUNDOS
    ultima = datetime.fromtimestamp(mtime, tz=MADRID_TZ)
    return {"activo": activo, "ultima_actividad": ultima.strftime("%H:%M:%S")}


def _video_url(archivo_local: str | None) -> str | None:
    if not archivo_local:
        return None
    return "/video/" + Path(archivo_local).as_posix()


def _thumb_url(archivo_local: str | None) -> str | None:
    if not archivo_local:
        return None
    return "/thumbnail/" + Path(archivo_local).as_posix()


def _resolver_video(relpath: str) -> Path:
    destino = (BASE_DIR / relpath).resolve()
    if VIDEOS_DIR.resolve() not in destino.parents:
        abort(403)
    if not destino.exists() or not destino.is_file():
        abort(404)
    return destino


@app.route("/")
def dashboard():
    estado = _estado_bot()
    try:
        pendientes = obtener_programados()
        historial = obtener_historial_dashboard(50)
    except DatabaseError as e:
        return render_template(
            "dashboard.html", estado=estado, error=str(e), proxima=None, resumen=None
        )

    hoy = datetime.now(MADRID_TZ).date()
    pendientes_hoy = sum(
        1 for p in pendientes if _parse_iso(p["hora_programada"]).date() == hoy
    )
    publicados_hoy = sum(
        1
        for h in historial
        if h["estado"] == "publicado"
        and h.get("published_at")
        and _parse_iso(h["published_at"]).date() == hoy
    )
    errores_total = sum(1 for h in historial if h["estado"] == "error")

    resumen = {
        "pendientes_hoy": pendientes_hoy,
        "publicados_hoy": publicados_hoy,
        "errores_total": errores_total,
        "total_pendientes": len(pendientes),
    }

    proxima_fmt = None
    if pendientes:
        p = pendientes[0]
        proxima_fmt = {
            "cuenta": p["cuenta"],
            "hora": _parse_iso(p["hora_programada"]).strftime("%d/%m %H:%M"),
        }

    return render_template(
        "dashboard.html", estado=estado, error=None, proxima=proxima_fmt, resumen=resumen
    )


@app.route("/api/estado")
def api_estado():
    return jsonify(_estado_bot())


@app.route("/calendario")
def calendario():
    offset = request.args.get("offset", 0, type=int)
    hoy = datetime.now(MADRID_TZ).date()
    lunes = hoy - timedelta(days=hoy.weekday()) + timedelta(weeks=offset)
    dias = [lunes + timedelta(days=i) for i in range(7)]

    try:
        pendientes = obtener_programados()
    except DatabaseError as e:
        return render_template("calendario.html", error=str(e), semana=[], offset=offset, rango="")

    por_dia: dict = {d: [] for d in dias}
    for p in pendientes:
        fecha = _parse_iso(p["hora_programada"])
        if fecha.date() in por_dia:
            por_dia[fecha.date()].append({
                "id_corto": p["id"][:8],
                "cuenta": p["cuenta"],
                "hora": fecha.strftime("%H:%M"),
                "video_url": _video_url(p.get("archivo_local")),
            })

    semana = [
        {
            "fecha": d.strftime("%d/%m"),
            "nombre": DIAS_SEMANA[d.weekday()],
            "es_hoy": d == hoy,
            "videos": sorted(por_dia[d], key=lambda x: x["hora"]),
        }
        for d in dias
    ]

    return render_template(
        "calendario.html",
        error=None,
        semana=semana,
        offset=offset,
        rango=f"{dias[0].strftime('%d/%m')} – {dias[-1].strftime('%d/%m/%Y')}",
    )


@app.route("/historial")
def historial_view():
    try:
        historial = obtener_historial_dashboard(30)
    except DatabaseError as e:
        return render_template("historial.html", error=str(e), items=[])

    items = []
    for h in historial:
        fecha_ref = h.get("published_at") or h.get("created_at")
        fecha_fmt = _parse_iso(fecha_ref).strftime("%d/%m/%Y %H:%M") if fecha_ref else "—"
        archivo = h.get("archivo_local")
        items.append({
            "cuenta": h["cuenta"],
            "estado": h["estado"],
            "fecha": fecha_fmt,
            "error_msg": h.get("error_msg"),
            "video_url": _video_url(archivo),
            "thumb_url": _thumb_url(archivo),
        })

    return render_template("historial.html", error=None, items=items)


@app.route("/video/<path:relpath>")
def servir_video(relpath):
    destino = _resolver_video(relpath)
    return send_file(destino, mimetype="video/mp4", conditional=True)


@app.route("/thumbnail/<path:relpath>")
def servir_thumbnail(relpath):
    destino = _resolver_video(relpath)
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
    thumb_path = THUMBNAILS_DIR / (relpath.replace("/", "_") + ".jpg")

    if not thumb_path.exists() or thumb_path.stat().st_mtime < destino.stat().st_mtime:
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", "1", "-i", str(destino),
                 "-vframes", "1", "-q:v", "4", str(thumb_path)],
                capture_output=True, timeout=30, check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            abort(404)

    if not thumb_path.exists():
        abort(404)
    return send_file(thumb_path, mimetype="image/jpeg")


if __name__ == "__main__":
    print("Dashboard disponible en http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
