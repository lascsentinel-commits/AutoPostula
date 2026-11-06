#!/usr/bin/env python3
"""
Copiloto Interactivo de Postulación por Voz — AutoPostula v3.0
Navega a la oferta en Brave vía CDP, lee cada pregunta y respuesta en voz alta usando `Di`,
rellena el formulario, pulsa Postular y avisa al usuario para que confirme en pantalla y chat.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

# Setup environment for Debian/Kali Playwright node wrapper
if "PLAYWRIGHT_NODEJS_PATH" not in os.environ and os.path.exists("/home/dhamit/.local/bin/pw_node_wrapper.sh"):
    os.environ["PLAYWRIGHT_NODEJS_PATH"] = "/home/dhamit/.local/bin/pw_node_wrapper.sh"

import database
from modules.smart_qa_solver import resolver_pregunta_reclutador, resolver_seleccion_dropdown, limpiar_texto_pregunta

CV_MASTER_PDF = "/home/dhamit/Documentos/CV-2026-01/1_CV_Dhani_Amit_Elgueta_Ríos_U-26.pdf"

SELECTORES_POSTULAR = [
    "button:has-text('Solicitud sencilla')",
    "a:has-text('Solicitud sencilla')",
    "button.primary-btn:has-text('Postular')",
    "button:has-text('Postular')",
    "a:has-text('Postular')",
    "a:has-text('Postúlate Ahora')",
    "button:has-text('Postúlate Ahora')",
    "a:has-text('Aplicar')",
    "button:has-text('Aplicar')",
    "a:has-text('APLICAR A ESTE PROCESO')",
    "button:has-text('APLICAR A ESTE PROCESO')",
    "a:has-text('Solicitar')",
    "button:has-text('Solicitar')",
    "button.jobs-apply-button",
    "a#btnPostular",
    "button#btnPostular",
]

SELECTORES_CONFIRMAR = [
    "button.primary-btn:has-text('Postular')",
    "button:has-text('Enviar postulación')",
    "button:has-text('Confirmar postulación')",
    "button:has-text('Enviar')",
    "button:has-text('Confirmar')",
    "button[type='submit']",
    "button:has-text('Siguiente')",
    "button:has-text('Revisar')",
]

PATRONES_YA_POSTULADO = [
    "ya postulaste",
    "ya te postulaste",
    "ya te has postulado",
    "ya estás postulado",
    "postulaste el",
    "postulación enviada",
    "has postulado a este empleo",
    "postulado con éxito",
    "candidatura enviada",
]

PATRONES_CERRADA = [
    "postulaciones cerradas",
    "esta oferta no acepta nuevas postulaciones",
    "oferta finalizada",
    "aviso finalizado",
    "empleo finalizado",
    "esta oferta ya no está disponible",
    "the page you were looking for doesn't exist",
    "404 not found",
]


def hablar(texto: str, final: bool = False):
    """Ejecuta Di para narrar en tiempo real."""
    cmd = ["/home/dhamit/.local/bin/Di"]
    if final:
        cmd.append("--final")
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
        proc.communicate(input=texto)
    except Exception as e:
        print(f"Error ejecutando Di: {e}", file=sys.stderr)


def descartar_banners_cookies(page):
    """Cierra banners de cookies y avisos flotantes."""
    for sel_c in [
        "button:has-text('Aceptar y cerrar')",
        "button:has-text('Aceptar cookies')",
        "button:has-text('Aceptar todo')",
        "button:has-text('Aceptar')",
        "button:has-text('Accept all')",
        "button:has-text('Entendido')",
    ]:
        for btn in page.locator(sel_c).all():
            try:
                if btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(300)
                    break
            except Exception:
                pass


def interactuar_oferta(oferta: dict, perfil: dict) -> dict:
    from playwright.sync_api import sync_playwright

    of_id = oferta["id"]
    titulo = oferta["titulo"]
    empresa = oferta["empresa"]
    portal = oferta["portal"]
    url = oferta["url_oferta"]

    res_data = {
        "id": of_id,
        "titulo": titulo,
        "empresa": empresa,
        "portal": portal,
        "url": url,
        "preguntas": [],
        "estado": "pendiente",
        "mensaje": "",
    }

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            ctx = browser.contexts[0]
        except Exception as e:
            msg = f"No se pudo conectar a Brave por CDP: {e}"
            hablar(f"Error de conexión con el navegador Brave. {msg}")
            res_data["estado"] = "error"
            res_data["mensaje"] = msg
            return res_data

        page = ctx.new_page()
        target_page = page

        try:
            # Anuncio de apertura de oferta
            hablar(f"Abriendo oferta de {empresa}: {titulo} en el portal {portal}.")
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)

            # Verificar si está cerrada
            body_text = (page.inner_text("body") or "").lower()
            for pat in PATRONES_CERRADA:
                if pat in body_text or "404" in page.title().lower():
                    msg = f"La oferta de {empresa} figura como cerrada o expirada."
                    hablar(msg)
                    res_data["estado"] = "cerrada"
                    res_data["mensaje"] = msg
                    return res_data

            # Verificar si ya estaba postulado
            for pat in PATRONES_YA_POSTULADO:
                if pat in body_text:
                    msg = f"Ya te encuentras postulado a esta oferta en {portal}."
                    hablar(msg)
                    res_data["estado"] = "ya_postulado"
                    res_data["mensaje"] = msg
                    return res_data

            descartar_banners_cookies(page)

            # Pulsar botón de inicio de postulación
            clicked_postular = False
            new_popup = None

            for sel in SELECTORES_POSTULAR:
                for loc in page.locator(sel).all():
                    try:
                        if loc.is_visible():
                            try:
                                with ctx.expect_page(timeout=3000) as p_info:
                                    loc.click(timeout=3000)
                                new_popup = p_info.value
                                clicked_postular = True
                                break
                            except Exception:
                                loc.click(timeout=3000)
                                clicked_postular = True
                                page.wait_for_timeout(1800)
                                break
                    except Exception:
                        continue
                if clicked_postular:
                    break

            if new_popup:
                target_page = new_popup
                target_page.wait_for_timeout(2000)
                descartar_banners_cookies(target_page)

            # Si hay botón Comenzar en el modal
            for b_com in target_page.locator("button:has-text('Comenzar')").all():
                if b_com.is_visible():
                    b_com.click()
                    target_page.wait_for_timeout(1500)
                    break

            descartar_banners_cookies(target_page)

            # Detectar y recopilar preguntas
            blocks = target_page.locator("div[id^='pregunta_'], .form-group, .mb-3, fieldset, .jobs-easy-apply-form-section__grouping").all()
            qa_list = []

            for bl in blocks:
                try:
                    lbl = bl.locator("label.type2, label, h4, p, strong, span.fb-form-element-label").first
                    q_text = ""
                    if lbl.count() > 0:
                        q_text = lbl.inner_text().strip()
                    if not q_text or len(q_text) < 5:
                        q_text = bl.inner_text().strip()

                    q_limpia = limpiar_texto_pregunta(q_text)
                    if not q_limpia:
                        continue

                    # Textarea
                    ta = bl.locator("textarea").first
                    if ta.count() > 0 and ta.is_visible():
                        resp = resolver_pregunta_reclutador(q_limpia, empresa, tipo_input="textarea")
                        qa_list.append({"tipo": "textarea", "pregunta": q_limpia, "respuesta": resp, "elem": ta})
                        continue

                    # Radios
                    radios = bl.locator("input[type='radio']").all()
                    if radios:
                        resp = resolver_pregunta_reclutador(q_limpia, empresa, tipo_input="radio_boolean")
                        qa_list.append({"tipo": "radio", "pregunta": q_limpia, "respuesta": resp, "elem": radios})
                        continue

                    # Selects
                    sel_el = bl.locator("select").first
                    if sel_el.count() > 0 and sel_el.is_visible():
                        opts = [o.inner_text().strip() for o in sel_el.locator("option").all() if o.inner_text().strip()]
                        resp = resolver_seleccion_dropdown(opts, q_limpia)
                        qa_list.append({"tipo": "select", "pregunta": q_limpia, "respuesta": resp, "elem": sel_el, "opciones": opts})
                        continue

                    # Text/number input
                    inp = bl.locator("input[type='text'], input[type='number'], input[type='tel'], input:not([type='hidden']):not([type='checkbox']):not([type='file']):not([type='radio'])").first
                    if inp.count() > 0 and inp.is_visible():
                        t_inp = (inp.get_attribute("type") or "text").lower()
                        resp = resolver_pregunta_reclutador(q_limpia, empresa, tipo_input=t_inp)
                        qa_list.append({"tipo": "input", "pregunta": q_limpia, "respuesta": resp, "elem": inp})
                        continue

                except Exception:
                    continue

            # NARRACIÓN POR VOZ DE CADA PREGUNTA Y RESPUESTA
            if qa_list:
                hablar(f"El reclutador de {empresa} solicita responder {len(qa_list)} preguntas.")
                for i, qa in enumerate(qa_list, 1):
                    p_txt = qa["pregunta"]
                    r_txt = qa["respuesta"]
                    # Narración concisa y natural
                    locucion = f"Pregunta {i}: {p_txt}. Respuesta: {r_txt}."
                    hablar(locucion)
                    res_data["preguntas"].append({"pregunta": p_txt, "respuesta": r_txt})
            else:
                hablar(f"Formulario estándar de {empresa} sin preguntas adicionales personalizadas.")

            # RELLENAR LOS CAMPOS EN LA PÁGINA
            for qa in qa_list:
                tipo = qa["tipo"]
                resp = qa["respuesta"]
                try:
                    if tipo == "textarea":
                        qa["elem"].evaluate("""(el, val) => {
                            el.value = val;
                            el.dispatchEvent(new Event("input", { bubbles: true }));
                            el.dispatchEvent(new Event("change", { bubbles: true }));
                        }""", resp)
                    elif tipo == "input":
                        qa["elem"].evaluate("""(el, val) => {
                            el.value = val;
                            el.dispatchEvent(new Event("input", { bubbles: true }));
                            el.dispatchEvent(new Event("change", { bubbles: true }));
                        }""", resp)
                    elif tipo == "radio":
                        for r in qa["elem"]:
                            l_r = r.evaluate("el => el.nextElementSibling ? el.nextElementSibling.innerText : el.parentElement.innerText").lower()
                            if (resp == "si" and any(w in l_r for w in ["sí", "si"])) or (resp == "no" and "no" in l_r):
                                if not r.is_checked():
                                    r.click()
                                    target_page.wait_for_timeout(100)
                                break
                    elif tipo == "select":
                        qa["elem"].select_option(label=resp)
                        qa["elem"].dispatch_event("change")
                except Exception as ex:
                    print(f"Error rellenando campo: {ex}", file=sys.stderr)

            # Adjuntar CV Maestro PDF si hay selector de archivo
            if os.path.exists(CV_MASTER_PDF):
                try:
                    file_inps = target_page.locator("input[type='file']")
                    for i in range(min(2, file_inps.count())):
                        file_inps.nth(i).set_input_files(CV_MASTER_PDF)
                        target_page.wait_for_timeout(400)
                except Exception:
                    pass

            target_page.wait_for_timeout(1000)

            # PULSAR EL BOTÓN POSTULAR / ENVIAR
            clicked_submit = False
            for sel_btn in SELECTORES_CONFIRMAR:
                for btn_s in target_page.locator(sel_btn).all():
                    try:
                        if btn_s.is_visible():
                            txt_btn = (btn_s.inner_text() or "").lower()
                            if any(w in txt_btn for w in ["buscar", "login", "ingresar", "cancelar", "guardar"]):
                                continue
                            # Scroll into view y click
                            btn_s.scroll_into_view_if_needed()
                            btn_s.click(timeout=4000)
                            clicked_submit = True
                            target_page.wait_for_timeout(2500)
                            break
                    except Exception:
                        continue
                if clicked_submit:
                    break

            # AVISO DE VOZ AL USUARIO
            hablar(f"Apreté postular para {empresa}. Mira en tu pantalla si se confirmó la postulación y avísame en el chat para continuar.")

            res_data["estado"] = "postulado_esperando_confirmacion"
            res_data["mensaje"] = "Botón postular presionado. Ventana abierta en Brave para confirmación visual."

        except Exception as e:
            res_data["estado"] = "error"
            res_data["mensaje"] = f"Excepción durante la postulación: {str(e)[:100]}"
            hablar(f"Hubo un inconveniente al postular a {empresa}. Revisa el chat para ver los detalles.")

    return res_data


def main():
    parser = argparse.ArgumentParser(description="Copiloto Interactivo de Postulación por Voz")
    parser.add_argument("--id", type=int, help="ID específico de la oferta en autopostula.db")
    args = parser.parse_args()

    perfil = database.obtener_perfil()
    conn = database.get_conn()
    cur = conn.cursor()

    if args.id:
        cur.execute("SELECT id, titulo, empresa, portal, url_oferta, estado FROM postulaciones WHERE id = ?", (args.id,))
    else:
        # Tomar la siguiente pendiente o pausada
        cur.execute("""
            SELECT id, titulo, empresa, portal, url_oferta, estado 
            FROM postulaciones 
            WHERE estado NOT LIKE '%postulado%' AND estado NOT LIKE '%confirmado%' AND estado NOT LIKE '%cerrada%'
            ORDER BY id ASC LIMIT 1
        """)
    row = cur.fetchone()
    conn.close()

    if not row:
        print(json.dumps({"error": "No hay ofertas pendientes disponibles."}))
        hablar("No hay más ofertas pendientes en la cola.", final=True)
        return

    oferta = dict(row)
    res = interactuar_oferta(oferta, perfil)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

