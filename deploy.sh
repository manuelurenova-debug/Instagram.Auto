#!/bin/bash
# Ejecutar en la VM: ./deploy.sh
set -e

cd /home/ubuntu/instagram-auto

echo "📥 Actualizando código..."
git pull origin master

echo "📦 Actualizando dependencias..."
source venv/bin/activate
pip install -r requirements.txt --quiet

echo "🔄 Reiniciando servicio..."
sudo systemctl restart instagram-auto.service

echo "✅ Deploy completo - $(date)"
sudo systemctl status instagram-auto.service --no-pager -l
