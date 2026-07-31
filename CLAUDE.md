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

### 1. Coste objetivo: [30 Jul 2026] REVISADO — ya no es 0€/mes estricto
- Decisión consciente del usuario: se despliega en **Railway** en vez de Oracle Cloud Always Free. Railway no tiene tier gratuito permanente para procesos 24/7 (solo un crédito de prueba limitado); a partir de ahí factura por uso (plan Hobby, unos pocos €/mes esperables). Usuario informado y confirmado antes de proceder.
- Sigue aplicando para el resto de servicios (Supabase, Telegram): deben mantenerse en su tier gratuito salvo aviso explícito.

### 2. Railway (servidor) — sustituye a Oracle Cloud
- Despliegue desde el repo de GitHub (público), build con Nixpacks.
- `nixpacks.toml` instala `ffmpeg` como paquete de sistema (Railway no lo trae por defecto).
- `railway.toml` define el comando de arranque (`python main.py`) y política de reinicio automático ante fallos — equivalente al `Restart=always` que tenía el `systemd` de Oracle.
- `cookies.txt` no viaja por git (está en `.gitignore`, son credenciales de sesión reales). En Railway se reconstruye en el arranque a partir de la variable de entorno `INSTAGRAM_COOKIES_B64` (el archivo local codificado en base64) — lógica añadida en `config.py`, no afecta al uso local en Windows (ahí el archivo ya existe en disco).
- Las variables de entorno se configuran en el dashboard de Railway (Raw Editor, pegando todo el bloque de una vez — soporta el valor multilínea de `IG_ACCOUNT_1_CAPTION` igual que `python-dotenv`).
- Los archivos `deploy.sh`, `cleanup.sh` e `instagram-auto.service` (preparados para Oracle) quedan sin usar mientras el despliegue sea en Railway — no se borran por si se retoma Oracle Cloud más adelante.

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
- [31 Jul 2026] `fix`: ajustados parámetros de edición a petición del usuario — fade in/out de 0.3s a 0.5s, zoom anti-detección de 105%-107% a 110%-112%. Resto del pipeline sin cambios (recorte 1.3s, thumb_offset 800ms, etc.). Reprobado con video real: duración y resolución correctas.
- [31 Jul 2026] `feat`: video ya no depende del disco local para publicar — arregla el fallo "archivo no encontrado en disco" en Railway (contenedor efímero). Nueva columna `video_url` en `publicaciones` (migración manual en Supabase SQL Editor, documentada en `sql/schema.sql`). `bot.py::cmd_add` sube el video a Supabase Storage inmediatamente tras editar (no al publicar) y borra el archivo local al momento; `video_url` se guarda en la DB junto con `archivo_local` (que se conserva solo como metadato). `publisher.py::publish_video_full` ya no sube nada — publica directo con la `video_url` ya existente y borra de Storage al terminar (éxito o error). `scheduler.py` lee `video_url` en vez de comprobar el archivo en disco; publicaciones antiguas sin `video_url` (creadas antes de esta migración) fallan con un mensaje claro pidiendo cancelar y reprogramar, en vez de intentar leer un archivo que ya no existe. `dashboard.py`: preview y miniaturas usan la URL pública de Storage cuando existe (ffmpeg lee el frame directo de la URL, sin descargar el archivo) con fallback al archivo local para registros antiguos. Efecto secundario aceptado: los videos publicados quedan sin ninguna copia (ni local ni en Storage, se borra tras publicar) — el Historial del dashboard ya no puede mostrar miniatura/preview de lo ya publicado, solo de lo pendiente. Probado end-to-end real: creación → Storage → publish → cleanup, y generación de miniatura leyendo directo de una URL de Storage.
- [30 Jul 2026] `fix`: miniatura de portada del Reel salía negra en Instagram (coincide con el fade de entrada de 0.3s desde negro de `editor.py`). Añadido `thumb_offset=800` (ms) a la llamada de creación del container en `publisher.py` — justo después de que termine el fade.
- [30 Jul 2026] `feat`: soporte de fecha explícita en `/add` — nuevo formato opcional `/add <URL> <cuenta> <YYYY-MM-DD> <HH:MM>` (4 argumentos) además del ya existente de 3 (`HH:MM` solo, hoy o mañana si ya pasó). `utils.py`: extraído `_parse_hhmm` como helper compartido, nueva `parse_date_time()` que valida formato de fecha y exige que el resultado sea futuro (a diferencia de `parse_time`, aquí una fecha/hora ya pasada es error, no auto-avanza). `bot.py::cmd_add` acepta 3 o 4 args; mensajes de error ahora muestran el texto específico de la excepción en vez de uno genérico. Confirmación de `/add` y listado de `/programados` muestran año en la fecha (antes solo `dd/mm`, ambiguo con fechas lejanas). Probado con 7 casos (hora futura hoy, hora pasada→mañana, fecha futura, fecha pasada, formato inválido, hora inválida, fecha de hoy con hora pasada).
- [30 Jul 2026] `fix`: build de Railway fallaba con "python: command not found" — al declarar `[phases.setup]` en `nixpacks.toml` con solo `ffmpeg`, se pisaba la detección automática de Python de Nixpacks en vez de sumarse a ella. Añadido `python3` explícitamente junto a `ffmpeg` en `nixPkgs`, y cambiado `startCommand` en `railway.toml` de `python main.py` a `python3 main.py` (más portable en estos entornos Nix).
- [30 Jul 2026] `feat`: preparado el despliegue en Railway — `nixpacks.toml` (instala ffmpeg como paquete de sistema), `railway.toml` (comando de arranque `python main.py` + reinicio automático ante fallos). `config.py` reconstruye `cookies.txt` en el arranque desde `INSTAGRAM_COOKIES_B64` si el archivo no existe ya en disco (Railway no tiene forma de subir un archivo suelto fuera de git); probado el round-trip byte a byte. No afecta al uso local (ahí el archivo ya existe).
- [30 Jul 2026] `fix`: primer publish real conseguido end-to-end — dos causas encontradas al depurar en vivo un fallo de publicación: (1) `publisher.py` usaba `graph.facebook.com`, pero el access token es del flujo nuevo "Instagram API with Instagram Login" (prefijo `IGAA...`), que solo funciona contra `graph.instagram.com` — cambiado `GRAPH_API_BASE`; de paso, `IG_ACCOUNT_1_ID` en `.env` tenía el ID antiguo (vinculado a Facebook Page), corregido al ID real que devuelve `/me` bajo este token. (2) El bucket `videos-temp` de Supabase Storage tenía `public=False` desde que se creó en mayo — nunca pudo servir los videos a Instagram. Corregido a `public=True` vía API. Con ambos arreglos, Reel publicado con éxito por primera vez (`ig_media_id` real confirmado).
- [30 Jul 2026] `fix`: quitado `EnvironmentFile=.env` de `instagram-auto.service` — el parser de systemd no soporta el valor multilínea de `IG_ACCOUNT_1_CAPTION` igual que `python-dotenv`, y `config.py` ya carga el `.env` por su cuenta con `load_dotenv()`. Encontrado al preparar el despliegue en Oracle Cloud.
- [30 Jul 2026] `fix`: ajustado el rango del zoom-in aleatorio anti-detección en `editor.py` de 102%-103% a 105%-107%. Reprobado end-to-end, sin bordes negros ni cambios en el resto del pipeline.
- [30 Jul 2026] `feat`: caption fijo por cuenta al publicar — nueva `IG_ACCOUNT_N_CAPTION` en `.env` (soporta valores multilínea entre comillas dobles, python-dotenv los parsea tal cual). `config.py` la carga en `IG_ACCOUNTS[cuenta]["caption"]` (vacía si no está definida). `publisher.py` ya no recibe `caption` como parámetro externo (nadie lo usaba, `scheduler.py` nunca lo pasaba) — `publish_reel`/`publish_video_full` la leen directamente de `IG_ACCOUNTS` según la cuenta destino. Verificado que el valor multilínea con emojis y hashtags se parsea íntegro.
- [30 Jul 2026] `feat`: modificaciones anti-detección en `editor.py` — recorte final ampliado de 1.0s a 1.3s (mínimo de duración de entrada subido de 2.0s a 2.3s para mantener el mismo margen de seguridad); nuevo zoom-in aleatorio centrado (102%-103%, distinto en cada video vía `random.uniform`) con `scale`+`crop` dentro de la misma cadena `-vf`, sin pasos extra de ffmpeg. Verificado: duración y resolución de salida correctas (diferencia de redondeo de solo 2px, sin bordes negros).
- [30 Jul 2026] `feat`: dashboard web local (`dashboard.py`, arranca aparte con `py dashboard.py`, Flask solo en `requirements-dashboard.txt` para no afectar el despliegue en Oracle). 4 secciones en español: Dashboard (estado del bot vía mtime del log, próxima publicación, resumen de hoy), Calendario semanal de la cola con preview de video, Historial con miniaturas generadas con ffmpeg (cacheadas en `videos/.thumbnails/`, gitignored). Solo bind a `127.0.0.1`, sin autenticación (uso local). `database.py` ampliado de forma aditiva: `obtener_programados()` ahora incluye `archivo_local`, nueva `obtener_historial_dashboard()`. No toca `main.py` ni el esquema de la tabla.
- [30 Jul 2026] `feat`: `config.py` ya no exige las 3 cuentas de Instagram al arrancar — `IG_ACCOUNTS` solo carga las que tengan ID+TOKEN rellenados en `.env` (permite probar con 1 o 2 cuentas activas; sigue fallando si no hay ninguna configurada).
- [30 Jul 2026] `fix`: pruebas end-to-end en local — Instagram bloquea descargas anónimas de yt-dlp (incluso contenido público) desde mediados de 2024. `--cookies-from-browser chrome` no es viable (Chrome moderno usa App-Bound Encryption, ver yt-dlp#10927). Solución: nueva variable `INSTAGRAM_COOKIES_FILE` (config.py) que apunta a un `cookies.txt` exportado manualmente del navegador; `downloader.py` lo usa vía `cookiefile` si existe, si no descarga sin autenticación. `cookies.txt` añadido a `.gitignore` (credencial de sesión real). De paso, corregido bug en `downloader.py`: releía `ydl_opts["outtmpl"]` después de que yt-dlp mutara ese dict internamente durante la descarga (`TypeError`), nunca se había detectado porque hasta ahora ninguna descarga llegaba a completarse. Descarga real verificada funcionando end-to-end.

**Historial Reciente:**
- [24 Jul 2026] `fix`: correcciones detectadas en auditoría — eliminada línea muerta en `parse_time` (utils.py) que causaba `ValueError` al programar en el último día del mes; eliminada dependencia no usada `ffmpeg-python` de requirements.txt; revertidos a placeholders vacíos los valores reales de `SUPABASE_URL`/`SUPABASE_KEY` en `.env.example`; añadido `sql/schema.sql` con el `CREATE TABLE` de `publicaciones` para poder recrear la DB desde cero.
- [16 May 2026] `feat`: Fase 6 — desplegado en Oracle Cloud Always Free (ARM Ampere A1 Ubuntu 22.04) con systemd autorestart + logrotate + cron de actualización yt-dlp semanal + cleanup de videos >30 días. Sistema operativo 24/7.
- [16 May 2026] `feat`: Fase 5 — publicación automática Graph API (REELS) + scheduler 1min + cleanup auto Storage post-publicación + alerta de tokens 7 días antes de caducar. Sistema funcional end-to-end en local.
- [16 May 2026] `feat`: Fase 4 — tabla `publicaciones` en Supabase + comandos /programados /historial /cancelar funcionales + ID corto (8 chars) para UX en Telegram.
- [16 May 2026] `feat`: Fase 3 — edición con ffmpeg (recorte 1s + fade in/out 0.3s) en H.264 CRF 20, audio sin recomprimir, faststart para IG.
- [16 May 2026] `feat`: Fase 2 — descarga real con yt-dlp + manejo de errores específicos (privado, geo, network) + cleanup automático de /temp >24h.
- [14 May 2026] `feat`: Fase 1 — setup proyecto + bot Telegram con 5 comandos validados (stubs para descarga/edición/publicación).

**Estado del Proyecto:**
- Sistema operativo 24/7 en Oracle Cloud.
- Coste real verificado: 0€/mes.
- Pendiente: monitorización post-launch, posibles mejoras (batch /add, etc.).
