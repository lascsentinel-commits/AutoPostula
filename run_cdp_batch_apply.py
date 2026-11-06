#!/usr/bin/env python3
"""
Postulador Automático por Lote mediante CDP (Chrome DevTools Protocol) — AutoPostula v3.0
Manejo integral de:
1. Portales nativos (DuocLaboral, Trabajando.cl, Computrabajo, FirstJob, Laborum)
2. Redirecciones externas de LinkedIn (hacia Workday, PandaPe, Buk, etc.)
3. Lectura contextuada de preguntas (Textareas, Radios Sí/No, Selects, Inputs)
4. Adjunto automático del CV Maestro Unificado de 6 páginas
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
from modules.auto_applier import generar_script_inyeccion_js
from modules.smart_qa_solver import resolver_pregunta_reclutador, resolver_seleccion_dropdown

CV_MASTER_PDF = "/home/dhamit/Documentos/CV-2026-01/1_CV_Dhani_Amit_Elgueta_Ríos_U-26.pdf"

SELECTORES_POSTULAR = [
    "button:has-text('Solicitud sencilla')",
    "a:has-text('Solicitud sencilla')",
    "a:has-text('Postular ahora')",
    "button:has-text('Postular ahora')",
    "a:has-text('Postularme')",
    "button:has-text('Postularme')",
    "button.primary-btn:has-text('Postular')",
    "button:has-text('Postular')",
    "a:has-text('Postular')",
    "a:has-text('Postúlate Ahora')",
    "a:has-text('Postúlate ahora')",
    "button:has-text('Postúlate Ahora')",
    "a:has-text('Aplicar ahora')",
    "button:has-text('Aplicar ahora')",
    "a:has-text('Aplicar')",
    "button:has-text('Aplicar')",
    "a:has-text('APLICAR A ESTE PROCESO')",
    "button:has-text('APLICAR A ESTE PROCESO')",
    "a:has-text('Solicitar')",
    "button:has-text('Solicitar')",
    "button.jobs-apply-button",
    "a#btnPostular",
    "button#btnPostular",
    "a.btn-postular",
    "button.btn-postular",
    "input[value='Postular']",
    "a[href*='postular']",
    "a[href*='#apply']",
]

SELECTORES_CONFIRMAR = [
    "button.primary-btn:has-text('Postular')",
    "button:has-text('Completar postulación')",
    "button:has-text('Enviar postulación')",
    "button:has-text('Enviar mi postulación')",
    "button:has-text('Enviar candidatura')",
    "button:has-text('Enviar solicitud')",
    "button:has-text('Enviar')",
    "button:has-text('Confirmar postulación')",
    "button:has-text('Confirmar')",
    "button:has-text('Finalizar postulación')",
    "button:has-text('Finalizar')",
    "button:has-text('CONTINUAR')",
    "button:has-text('Continuar')",
    "button:has-text('Siguiente')",
    "button[type='submit']",
]

PATRONES_YA_POSTULADO = [
    "¡has postulado al empleo!",
    "has postulado al empleo",
    "ya postulaste a esta oferta",
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
                    page.wait_for_timeout(400)
                    break
            except Exception:
                pass


def resolver_preguntas_en_pagina(page, empresa: str) -> int:
    """Lee y responde inteligentemente todas las preguntas del reclutador en la página activa."""
    blocks = page.locator("div[id^='pregunta_'], .form-group, .mb-3, fieldset, .jobs-easy-apply-form-section__grouping").all()
    respondidas = 0

    for bl in blocks:
        try:
            lbl = bl.locator("label.type2, label, h4, p, strong, span.fb-form-element-label").first
            q_text = ""
            if lbl.count() > 0:
                q_text = lbl.inner_text().strip()
            if not q_text or len(q_text) < 5:
                q_text = bl.inner_text().strip()

            if not q_text:
                continue

            # 1. Textarea
            ta = bl.locator("textarea").first
            if ta.count() > 0 and ta.is_visible():
                resp = resolver_pregunta_reclutador(q_text, empresa, tipo_input="textarea")
                ta.evaluate("""(el, val) => {
                    el.value = val;
                    el.dispatchEvent(new Event("input", { bubbles: true }));
                    el.dispatchEvent(new Event("change", { bubbles: true }));
                }""", resp)
                respondidas += 1
                page.wait_for_timeout(100)

            # 2. Radio buttons (Sí / No)
            radios = bl.locator("input[type='radio']").all()
            if radios:
                desired = resolver_pregunta_reclutador(q_text, empresa, tipo_input="radio_boolean")
                for r in radios:
                    try:
                        l_r = r.evaluate("el => el.nextElementSibling ? el.nextElementSibling.innerText : el.parentElement.innerText").lower()
                        if (desired == "si" and any(w in l_r for w in ["sí", "si"])) or (desired == "no" and "no" in l_r):
                            if not r.is_checked():
                                r.click()
                                respondidas += 1
                                page.wait_for_timeout(100)
                            break
                    except Exception:
                        pass

            # 3. Dropdowns (<select>)
            selects = bl.locator("select").all()
            for sel_el in selects:
                try:
                    if sel_el.is_visible():
                        opts = [o.inner_text().strip() for o in sel_el.locator("option").all() if o.inner_text().strip()]
                        mejor_opcion = resolver_seleccion_dropdown(opts, q_text)
                        if mejor_opcion:
                            sel_el.select_option(label=mejor_opcion)
                            sel_el.dispatch_event("change")
                            respondidas += 1
                            page.wait_for_timeout(100)
                except Exception:
                    pass

            # 4. Inputs text o number
            inp = bl.locator("input[type='text'], input[type='number'], input[type='tel'], input[type='email'], input:not([type='hidden']):not([type='checkbox']):not([type='file']):not([type='radio'])").first
            if inp.count() > 0 and inp.is_visible():
                t_inp = (inp.get_attribute("type") or "text").lower()
                resp = resolver_pregunta_reclutador(q_text, empresa, tipo_input=t_inp)
                inp.evaluate("""(el, val) => {
                    el.value = val;
                    el.dispatchEvent(new Event("input", { bubbles: true }));
                    el.dispatchEvent(new Event("change", { bubbles: true }));
                }""", resp)
                respondidas += 1
                page.wait_for_timeout(100)

        except Exception:
            continue

    return respondidas


def postular_oferta_en_pestana(ctx, oferta: dict, perfil: dict) -> tuple[str, str]:
    url = oferta.get("url_oferta", "")
    empresa = oferta.get("empresa", "la empresa")
    portal = oferta.get("portal", "Portal")

    if not url.startswith("http"):
        return "error", "URL inválida"

    page = ctx.new_page()
    target_page = page

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(2200)

        # 1. Comprobar si la oferta fue cerrada
        body_text = (page.inner_text("body") or "").lower()
        for p in PATRONES_CERRADA:
            if p in body_text or "404" in page.title().lower():
                return "cerrada", f"Oferta cerrada/expirada en {portal}"

        # 2. Comprobar si ya estaba postulado previamente
        for p in PATRONES_YA_POSTULADO:
            if p in body_text:
                return "ok", f"Ya registrado como postulado en {portal}"

        descartar_banners_cookies(page)

        # 3. Buscar botón postular (manejando si abre una nueva pestaña / redirección externa)
        clicked = False
        new_popup = None

        for sel in SELECTORES_POSTULAR:
            for loc in page.locator(sel).all():
                try:
                    if loc.is_visible():
                        # Intentar capturar popup si abre nueva ventana (ej. LinkedIn a Workday o PandaPe)
                        try:
                            with ctx.expect_page(timeout=3500) as p_info:
                                loc.click(timeout=3000)
                            new_popup = p_info.value
                            clicked = True
                            break
                        except Exception:
                            # Clic normal sin popup
                            loc.click(timeout=3000)
                            clicked = True
                            page.wait_for_timeout(2000)
                            break
                except Exception:
                    continue
            if clicked:
                break

        # Si se abrió una página externa desde LinkedIn
        if new_popup:
            target_page = new_popup
            target_page.wait_for_timeout(2500)
            portal = f"{portal} -> {target_page.title()[:25]}"
            descartar_banners_cookies(target_page)

            # Si en la página externa hay un botón de postular (ej. PandaPe o Workday)
            for sel_ext in ["a:has-text('APLICAR A ESTE PROCESO')", "a:has-text('Postúlate Ahora')", "button:has-text('Postúlate Ahora')", "a:has-text('Computrabajo')", "button:has-text('Computrabajo')"]:
                for b_ext in target_page.locator(sel_ext).all():
                    try:
                        if b_ext.is_visible():
                            b_ext.click()
                            target_page.wait_for_timeout(2000)
                            break
                    except Exception:
                        pass

        # Si hay botón Comenzar en el modal
        for b_com in target_page.locator("button:has-text('Comenzar')").all():
            if b_com.is_visible():
                b_com.click()
                target_page.wait_for_timeout(1500)
                break

        descartar_banners_cookies(target_page)

        # 4. Resolver preguntas en la página destino
        respondidas = resolver_preguntas_en_pagina(target_page, empresa)

        # Inyectar script JS complementario
        js_fill = generar_script_inyeccion_js(perfil)
        try:
            target_page.evaluate(js_fill)
            target_page.wait_for_timeout(600)
        except Exception:
            pass

        # 5. Adjuntar CV Maestro PDF si existe input file
        cv_path = CV_MASTER_PDF if os.path.exists(CV_MASTER_PDF) else (perfil.get("ruta_cv_pdf") or "")
        if cv_path and os.path.exists(cv_path):
            try:
                file_inps = target_page.locator("input[type='file']")
                for i in range(min(2, file_inps.count())):
                    file_inps.nth(i).set_input_files(cv_path)
                    target_page.wait_for_timeout(500)
            except Exception:
                pass

        # 6. Intentar pulsar botón de confirmación / envío VISIBLE
        confirmed = False
        for sel_env in SELECTORES_CONFIRMAR:
            for btn_e in target_page.locator(sel_env).all():
                try:
                    if btn_e.is_visible() and btn_e.is_enabled():
                        txt_b = (btn_e.inner_text() or "").lower()
                        if "buscar" not in txt_b and "login" not in txt_b and "ingresar" not in txt_b and "cancelar" not in txt_b and "guardar empleo" not in txt_b:
                            btn_e.click(timeout=3500)
                            confirmed = True
                            target_page.wait_for_timeout(3000)
                            break
                except Exception:
                    continue
            if confirmed:
                break

        # 7. Verificación final de confirmación en la página
        body_final = (target_page.inner_text("body") or "").lower()
        for p in PATRONES_YA_POSTULADO:
            if p in body_final:
                return "ok", f"Postulación confirmada y enviada en {portal}"

        if confirmed:
            return "ok", f"Postulación enviada exitosamente en {portal}"

        if clicked:
            return "ok", f"Formulario y {respondidas} preguntas completadas en {portal}"

        return "revision", f"Revisar en {portal}"

    except Exception as e:
        return "error", f"Error navegando: {str(e)[:70]}"
    finally:
        # Cerrar las pestañas usadas para esta oferta
        try:
            if target_page and target_page != page:
                target_page.close()
            if page:
                page.close()
        except Exception:
            pass


def run_cdp_batch(limit: int = 150):
    perfil = database.obtener_perfil()
    conn = database.get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, titulo, empresa, portal, url_oferta, score_duoc, email_reclutador
        FROM postulaciones
        WHERE estado NOT LIKE '%Confirmado%' AND estado NOT LIKE '%Cerrada%'
        ORDER BY score_duoc DESC, id ASC
        LIMIT ?;
    """, (limit,))
    ofertas = [dict(r) for r in cur.fetchall()]
    conn.close()

    total = len(ofertas)
    print(f"🚀 Iniciando postulación gráfica multi-portal para {total} ofertas con sesiones reales de Brave...")

    if total == 0:
        print("No hay ofertas pendientes de postulación.")
        return

    from playwright.sync_api import sync_playwright

    exitosas = 0
    cerradas = 0
    pendientes = 0

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            ctx = browser.contexts[0]
        except Exception as e:
            print(f"❌ Error conectando a Brave por CDP en puerto 9222: {e}")
            return

        for idx, of in enumerate(ofertas, 1):
            of_id = of["id"]
            titulo = of["titulo"][:40]
            empresa = of["empresa"][:25]
            portal = of["portal"]

            print(f"[{idx}/{total}] {portal} | {titulo} ({empresa})...", end=" ", flush=True)

            try:
                res_tipo, msg = postular_oferta_en_pestana(ctx, of, perfil)
            except Exception as e:
                res_tipo, msg = "error", f"Error procesando oferta: {str(e)[:50]}"

            conn_u = database.get_conn()
            cur_u = conn_u.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

            if res_tipo == "ok":
                nuevo_estado = "🟢 Postulado Confirmado"
                exitosas += 1
                print(f"✅ {msg}")
            elif res_tipo == "cerrada":
                nuevo_estado = "⚪ Oferta Cerrada por la Empresa"
                cerradas += 1
                print(f"⚪ {msg}")
            else:
                nuevo_estado = "🟡 Pausada (Requiere Revisión)"
                pendientes += 1
                print(f"⚠️ {msg}")

            nota_actualizada = f"[CV: 1_CV_Dhani_Amit_Elgueta_Ríos_U-26.pdf] {msg}"
            cur_u.execute("""
                UPDATE postulaciones 
                SET estado = ?, metodo_postulacion = 'brave_cdp_real', fecha_postulacion = ?, notas = ?
                WHERE id = ?;
            """, (nuevo_estado, now_str, nota_actualizada, of_id))
            conn_u.commit()
            conn_u.close()

            time.sleep(2.0)

    print("==========================================================")
    print(f"🎯 Resumen CDP: Total: {total} | Exitosas: {exitosas} | Cerradas: {cerradas} | Pendientes: {pendientes}")
    print("==========================================================")


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    run_cdp_batch(lim)
