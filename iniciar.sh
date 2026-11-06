#!/usr/bin/env bash
# Iniciar AutoPostula en el puerto 8503
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8503

echo "=========================================="
echo "🎯 Iniciando AutoPostula - Prácticas Duoc"
echo "🌐 Puerto: http://localhost:$PORT"
echo "=========================================="

python3.13 -m streamlit run "$DIR/app.py" \
    --server.port=$PORT \
    --server.address=0.0.0.0 \
    --server.headless=true
