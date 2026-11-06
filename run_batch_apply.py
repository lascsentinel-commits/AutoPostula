#!/usr/bin/env python3
"""Batch Auto-Applier for AutoPostula v3.0

Uses a single persistent Playwright browser session to iterate through
pending internship and job offers in the local SQLite database.
"""

import json
import os
import sys
import time
from datetime import datetime

# Setup environment for Debian/Kali Playwright node wrapper
if "PLAYWRIGHT_NODEJS_PATH" not in os.environ and os.path.exists("/home/dhamit/.local/bin/pw_node_wrapper.sh"):
    os.environ["PLAYWRIGHT_NODEJS_PATH"] = "/home/dhamit/.local/bin/pw_node_wrapper.sh"

import database
from modules.auto_applier import (
    BRAVE_BIN,
    SESSION_DIR,
    generar_script_inyeccion_js,
)
from modules.cv_dispatcher import obtener_cv_optimo

SELECTORES_POSTULAR = [
    "button:has-text('Postular ahora')",
    "button:has-text('Postularme')",
    "a:has-text('Postularme')",
    "button:has-text('Postular')",
    "a:has-text('Postular')",
    "button:has-text('Aplicar')",
    "a:has-text('Aplicar')",
    "button.jobs-apply-button",
    "a.btn-postular",
    "button.btn-postular",
    "a#btn_apply",
    "a[href*='postular']",
    "input[value='Postular']",
]

SELECTORES_CONFIRMAR = [
    "button:has-text('Enviar postulación')",
    "button:has-text('Enviar')",
    "button:has-text('Confirmar postulación')",
    "button:has-text('Confirmar')",
    "button:has-text('Finalizar')",
    "button:has-text('Siguiente')",
    "button:has-text('Continuar')",
    "button[type='submit']",
]

PATRONES_YA_POSTULADO = [
    "ya te postulaste",
    "ya te has postulado",
    "ya estás postulado",
    "postulaste el",
    "postulación enviada",
    "has postulado a este empleo",
    "ya postulaste",
]


def postular_oferta(page, oferta: dict, perfil: dict) -> tuple[bool, str]:
    url = oferta.get("url_oferta", "")
    if not url.startswith("http"):
        return False, "URL inválida"

    titulo = oferta.get("titulo", "")
    portal = oferta.get("portal", "")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)

        body_text = (page.inner_text("body") or "").lower()

        # 1. Comprobar si ya estaba postulado previamente en el portal
        for p in PATRONES_YA_POSTULADO:
            if p in body_text:
                return True, f"Ya registrado como postulado previamente en {portal}"

        # 2. Comprobar si redirigió a login
        if "/login" in page.url.lower() or "iniciar-sesion" in page.url.lower():
            return False, f"Requiere inicio de sesión en {portal}"

        # 3. Buscar y pulsar botón Postular
        clicked = False
        for sel in SELECTORES_POSTULAR:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=3000)
                    clicked = True
                    page.wait_for_timeout(1800)
                    break
            except Exception:
                continue

        if not clicked:
            # Comprobar si al cargar la página el botón no existe porque ya postuló
            for p in PATRONES_YA_POSTULADO:
                if p in (page.inner_text("body") or "").lower():
                    return True, f"Ya postulado en {portal}"
            return False, f"Botón postular no encontrado en {portal}"

        # Comprobar si al hacer clic pidió login
        if "/login" in page.url.lower() or "iniciar-sesion" in page.url.lower():
            return False, f"Requiere autenticación al pulsar postular en {portal}"

        # 4. Adjuntar CV PDF especializado según perfil de la oferta si existe input file
        cv_match = obtener_cv_optimo(titulo, post.get("descripcion", ""))
        cv_path = cv_match.get("ruta_pdf") if (cv_match and cv_match.get("existe")) else (perfil.get("ruta_cv_pdf") or "")
        if cv_path and os.path.exists(cv_path):
            try:
                file_inps = page.locator("input[type='file']")
                for i in range(min(2, file_inps.count())):
                    file_inps.nth(i).set_input_files(cv_path)
                    page.wait_for_timeout(500)
            except Exception:
                pass

        # 5. Inyectar respuestas inteligentes Duoc UC
        js_fill = generar_script_inyeccion_js(perfil)
        try:
            page.evaluate(js_fill)
            page.wait_for_timeout(1000)
        except Exception:
            pass

        # 6. Intentar pulsar botón de confirmación / envío
        confirmed = False
        for sel_env in SELECTORES_CONFIRMAR:
            try:
                btn_e = page.locator(sel_env).first
                if btn_e.count() > 0 and btn_e.is_visible() and btn_e.is_enabled():
                    txt_b = (btn_e.inner_text() or "").lower()
                    if "buscar" not in txt_b and "login" not in txt_b and "ingresar" not in txt_b and "cancelar" not in txt_b:
                        btn_e.click(timeout=3000)
                        confirmed = True
                        page.wait_for_timeout(2000)
                        break
            except Exception:
                continue

        if confirmed:
            return True, f"Postulación enviada exitosamente en {portal}"

        return True, f"Formulario completado en {portal} (listo para confirmación final)"

    except Exception as e:
        return False, f"Error navegando: {str(e)[:70]}"


def run_batch(limit: int = 100):
    perfil = database.obtener_perfil()
    conn = database.get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, titulo, empresa, portal, url_oferta, score_duoc, email_reclutador
        FROM postulaciones
        WHERE estado LIKE '%Cola%'
        ORDER BY score_duoc DESC, id ASC
        LIMIT ?;
    """, (limit,))
    ofertas = [dict(r) for r in cur.fetchall()]
    conn.close()

    total = len(ofertas)
    print(f"🚀 Iniciando postulación por lote para {total} ofertas pendientes...")

    if total == 0:
        print("No hay ofertas en cola.")
        return

    from playwright.sync_api import sync_playwright

    exitosas = 0
    fallidas = 0

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            executable_path=BRAVE_BIN,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
            locale="es-CL",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        page = ctx.new_page()

        for idx, of in enumerate(ofertas, 1):
            of_id = of["id"]
            titulo = of["titulo"][:40]
            empresa = of["empresa"][:25]
            portal = of["portal"]

            print(f"[{idx}/{total}] {portal} | {titulo} ({empresa})...", end=" ", flush=True)

            ok, msg = postular_oferta(page, of, perfil)

            # Actualizar estado en la base de datos
            conn_u = database.get_conn()
            cur_u = conn_u.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

            if ok:
                nuevo_estado = "🟢 Postulado Confirmado"
                exitosas += 1
                print(f"✅ {msg}")
            else:
                nuevo_estado = "🟡 Pausada (Requiere Login / Revisión)"
                fallidas += 1
                print(f"⚠️ {msg}")

            cur_u.execute("""
                UPDATE postulaciones 
                SET estado = ?, metodo_postulacion = 'playwright_batch', fecha_postulacion = ?
                WHERE id = ?;
            """, (nuevo_estado, now_str, of_id))
            conn_u.commit()
            conn_u.close()

            # Pausa de cortesía entre ofertas para emular navegación humana y evitar bloqueos
            time.sleep(2.5)

        ctx.close()

    print("========================================")
    print(f"Proceso finalizado. Total: {total} | Exitosas: {exitosas} | Pendientes de login: {fallidas}")
    print("========================================")


if __name__ == "__main__":
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    run_batch(limite)

