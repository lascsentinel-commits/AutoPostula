#!/usr/bin/env bash
# ==============================================================================
# AutoPostula - Bot de Postulación Automática sobre Pantalla (Brave CDP)
# Con pausa interactiva de 30-60s para revisión del usuario y bucle continuo
# ==============================================================================
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_EXEC="/home/dhamit/.local/bin/python3.13"

# Asegurar variables de entorno X11 para enfocar ventana
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-/home/dhamit/.Xauthority}"
unset PLAYWRIGHT_NODEJS_PATH

echo "=========================================================="
echo "🎯 AutoPostula: Lanzando Bot de Automatización en Pantalla"
echo "🖥️  Controlador: Brave Browser (CDP en puerto 9222)"
echo "⏱️  Pausa de revisión interactiva antes del envío"
echo "📄 CV Maestro: /home/dhamit/Documentos/CV-2026-01/1_CV_Dhani_Amit_Elgueta_Ríos_U-26.pdf"
echo "=========================================================="

# Traer Brave al frente
wmctrl -a Brave 2>/dev/null || true

# Ejecutar bucle interactivo sobre pantalla
$PYTHON_EXEC "$DIR/bucle_pantalla_interactivo.py" "$@"
