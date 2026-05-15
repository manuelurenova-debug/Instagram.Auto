# Contexto y Reglas del Proyecto (Instagram Auto)

Este archivo contiene el contexto crítico, las reglas de arquitectura y las instrucciones de comportamiento para Claude Code o cualquier asistente de IA que trabaje en este proyecto.
**LEE ESTE ARCHIVO AL INICIO DE CADA SESIÓN.**

## 🗣️ Reglas de Comunicación
1. **Idioma:** Háblame y explícame tus razonamientos siempre en **Español**.
2. **Transparencia:** Antes de modificar archivos, explícame brevemente: qué vas a hacer, por qué es la mejor solución y si vas a eliminar código antiguo.
3. **Resúmenes:** Cuando termines una tarea, dame un resumen claro de los archivos tocados.

## 🛠️ Flujo de Trabajo y Git
1. **Registro en CLAUDE.md (OBLIGATORIO):** ANTES de hacer cualquier commit, SIN EXCEPCIÓN, DEBES editar la sección "📝 Estado Actual y Últimos Cambios" al final de este archivo. Mueve el "Último Cambio" actual al "Historial Reciente" y escribe el cambio que acabas de realizar.
2. **Commits automáticos:** Una vez hayas guardado el cambio en `CLAUDE.md`, DEBES hacer `git add .`, `git commit` (con `feat/fix/perf:`) y `git push origin master`. No esperes a que yo te pida hacer el push.
3. **Checklist — pide confirmación antes de:**
   - Cambiar a un plan de pago en Oracle Cloud, Supabase o cualquier otro servicio.
   - Añadir una dependencia Python pesada (>50 MB) o que requiera compilación nativa compleja.
   - Modificar el esquema de la tabla `publicaciones` en Supabase (riesgo de romper datos existentes).
   - Cambiar la lógica de edición de video (recorte/fade) — el resultado visual es parte del producto.

## ⚠️ Infraestructura y Restricciones (¡CRÍTICO!)

### 1. Coste objetivo: 0€/mes — TODO TIENE QUE SER GRATIS
- Ninguna decisión técnica debe romper esta restricción sin avisar primero.
- Antes de proponer cualquier servicio nuevo, verifica que tenga tier gratuito suficiente para este caso de uso.

### 2. Oracle Cloud Always Free Tier (servidor)
- Corre en una VM **ARM Ampere A1** (arquitectura `aarch64`).
- Cualquier dependencia con binarios nativos debe tener wheel para `aarch64`. Si no lo tiene, hay que compilar o sustituir.
- El proceso se gestiona con `systemd` (`instagram-auto.service`). Si reinicias el servicio, dura ~2-5s.
- Recursos disponibles: hasta 4 OCPUs / 24 GB RAM / 200 GB disco. Sobra para este caso de uso.

### 3. Supabase (Free Tier)
- Base de datos: 500 MB → cabe sin problema, solo guardamos metadata de publicaciones.
- Storage: 1 GB → es el cuello de botella real. Los videos NO se quedan permanentemente en Storage; solo el tiempo justo para que la Graph API los lea desde una URL pública. **Tras publicación exitosa, el archivo se borra del bucket** (queda en disco local de la VM como copia).
- Bucket público: `videos-temp`.

### 4. Facebook Graph API (Instagram)
- Modelo de publicación: **siempre Reels** (`media_type=REELS`) para simplificar, independientemente de la duración del video.
- Access Tokens caducan: usar **Long-Lived Tokens** (60 días). El bot debe avisar por Telegram cuando un token esté a 7 días o menos de caducar.
- Endpoint base: `https://graph.facebook.com/v19.0/`.

### 5. yt-dlp
- Es la dependencia más frágil del stack (Instagram cambia HTML/API frecuentemente).
- Configurar **actualización automática semanal** vía `cron` en la VM: `pip install -U yt-dlp` cada domingo a las 04:00.

### 6. Python en Windows (desarrollo local)
- El usuario desarrolla en Windows y usa `py` (no `python`) en la línea de comandos.
- El despliegue es en Linux ARM (Oracle Cloud) → asegúrate de que el código sea cross-platform (paths con `pathlib`, no shell-specific).

## 🎯 Contexto de Producto y UX

1. **Propósito:** Sistema personal para automatizar la descarga, edición y publicación programada de videos en múltiples cuentas Business de Instagram. **Controlado 100% desde Telegram** — sin web UI.
2. **Flujo de Usuario:**
   - El usuario envía `/add [URL] [cuenta] [hora]` en Telegram.
   - El bot descarga el video (`yt-dlp`), lo edita (`ffmpeg`: recorte 1s final + fade in/out 0.3s), y lo programa en Supabase.
   - A la hora programada, el scheduler publica automáticamente vía Graph API y notifica al usuario.
3. **Cuentas destino:** 3 cuentas Business de Instagram (`cuenta_1`, `cuenta_2`, `cuenta_3`). El usuario añade más en `.env` si lo necesita.
4. **Lenguaje del bot:** Español. Mensajes claros y con emojis (`✅`, `❌`, `⏳`, `📅`).

## 🏗️ Arquitectura Actual y Módulos Principales

**Stack:** Python 3.11+, `python-telegram-bot`, `yt-dlp`, `ffmpeg-python`, `supabase-py`, `APScheduler`, `python-dotenv`, `requests`.

### Estructura de archivos
```
/instagram-auto
  /videos
    /temp/             # descargas temporales (yt-dlp output)
    /cuenta_1/         # videos editados pendientes/publicados de cuenta_1
    /cuenta_2/
    /cuenta_3/
  main.py              # punto de entrada — arranca bot + scheduler en paralelo
  bot.py               # handlers de Telegram (/add, /programados, /historial, /cancelar, /ayuda)
  downloader.py        # wrapper de yt-dlp
  editor.py            # wrapper de ffmpeg (recorte + fade)
  publisher.py         # Graph API (subir + publicar Reel)
  scheduler.py         # APScheduler que revisa Supabase cada minuto
  database.py          # cliente Supabase + funciones CRUD
  storage.py           # subir/borrar archivos a Supabase Storage
  config.py            # carga `.env` y valida vars críticas
  utils.py             # helpers: validar URL IG, parsear HH:MM, formatear logs
  .env                 # secrets (NUNCA commitear)
  .env.example         # template con nombres de variables (sí se commitea)
  .gitignore
  requirements.txt
  README.md
```

### Variables de entorno (`.env`)
```
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=             # solo este chat_id puede usar el bot (seguridad)
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_BUCKET=videos-temp
IG_ACCOUNT_1_ID=
IG_ACCOUNT_1_TOKEN=
IG_ACCOUNT_2_ID=
IG_ACCOUNT_2_TOKEN=
IG_ACCOUNT_3_ID=
IG_ACCOUNT_3_TOKEN=
```

## 📝 Estado Actual y Últimos Cambios

**Último Cambio:**
- [16 May 2026] `feat`: Fase 4 — tabla `publicaciones` en Supabase + comandos /programados /historial /cancelar funcionales + ID corto (8 chars) para UX en Telegram.

**Historial Reciente:**
- [16 May 2026] `feat`: Fase 3 — edición con ffmpeg (recorte 1s + fade in/out 0.3s) en H.264 CRF 20, audio sin recomprimir, faststart para IG.
- [16 May 2026] `feat`: Fase 2 — descarga real con yt-dlp + manejo de errores específicos (privado, geo, network) + cleanup automático de /temp >24h.
- [14 May 2026] `feat`: Fase 1 — setup proyecto + bot Telegram con 5 comandos validados (stubs para descarga/edición/publicación).

**Estado del Proyecto:**
- Fase 4 completada: CRUD Supabase completo, /programados /historial /cancelar operativos, horas en Europe/Madrid, DB calls async con asyncio.to_thread.
- Pendiente: Fase 5 (publicación Graph API + APScheduler).
