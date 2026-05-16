#!/bin/bash
# Ejecutado por cron todos los lunes a las 03:00
LOGS_DIR="/home/ubuntu/instagram-auto/logs"
VIDEOS_DIR="/home/ubuntu/instagram-auto/videos"

# Borrar videos de cuentas publicados hace más de 30 días
find "$VIDEOS_DIR"/cuenta_*/ -name "*.mp4" -mtime +30 -delete 2>/dev/null

# Borrar temporales de más de 1 día (limpieza de seguridad, downloader ya los borra)
find "$VIDEOS_DIR/temp/" -name "*.mp4" -mtime +1 -delete 2>/dev/null

echo "$(date '+%Y-%m-%d %H:%M:%S') - Cleanup ejecutado" >> "$LOGS_DIR/cleanup.log"
