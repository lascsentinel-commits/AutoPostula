#!/usr/bin/env python3
"""Automate application across open Brave tabs using X11 injection."""

import os
import subprocess
import time
import sys

def run_tabs_automation(num_tabs: int = 15):
    js_path = "/tmp/test_fill.js"
    if not os.path.exists(js_path):
        print("Script JS no encontrado.")
        return

    with open(js_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    # Copiar al portapapeles con xclip
    p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
    p.communicate(input=js_code.encode("utf-8"))

    # Activar la ventana de Brave
    print("Enfocando ventana de Brave...")
    subprocess.run(["wmctrl", "-a", "Brave"], check=False)
    time.sleep(1.0)

    print(f"Iniciando ciclo automático para {num_tabs} pestañas...")

    for i in range(1, num_tabs + 1):
        print(f"[{i}/{num_tabs}] Inyectando auto-postulación en pestaña actual...")

        # 1. Abrir consola de desarrollador
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+shift+j"], check=False)
        time.sleep(1.2)

        # 2. Pegar el código JS del portapapeles
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+v"], check=False)
        time.sleep(0.4)

        # 3. Ejecutar con Enter
        subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], check=False)
        time.sleep(0.8)

        # 4. Cerrar consola de desarrollador
        subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+shift+j"], check=False)
        time.sleep(2.5)

        # 5. Pasar a la siguiente pestaña con Ctrl+Tab
        if i < num_tabs:
            print("Pasando a la siguiente pestaña...")
            subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+Tab"], check=False)
            time.sleep(1.5)

    print("========================================")
    print("Ciclo completado con éxito en todas las pestañas.")
    print("========================================")

if __name__ == "__main__":
    tabs = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    run_tabs_automation(tabs)

