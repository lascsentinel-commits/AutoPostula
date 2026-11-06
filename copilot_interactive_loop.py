#!/usr/bin/env python3
"""
Copiloto Interactivo de Detección de Postulación y Avance Automático
AutoPostula v3.0

1. Abre la oferta en la pestaña activa de Brave.
2. Trae Brave al frente de la pantalla (wmctrl).
3. Presiona 'Postula fácil' y 'Comenzar'.
4. Detecta y responde preguntas con `smart_qa_solver.py`.
5. Habilita el botón de envío.
6. Lee en ráfagas cortas de pocas palabras vía `Di`.
7. Avisa: "Puedes postular ya".
8. Detecta automáticamente en tiempo real cuando el usuario presiona el botón.
9. Narra confirmación y registra en `autopostula.db`.
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import websockets
from datetime import datetime

import database
from modules.smart_qa_solver import resolver_pregunta_reclutador, resolver_seleccion_dropdown, limpiar_texto_pregunta

CV_MASTER_PDF = "/home/dhamit/Documentos/CV-2026-01/1_CV_Dhani_Amit_Elgueta_Ríos_U-26.pdf"


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


def traer_brave_al_frente():
    """Trae la ventana de Brave al primer plano en X11."""
    try:
        subprocess.run(["wmctrl", "-a", "Brave"], env={"DISPLAY": ":0", "XAUTHORITY": "/home/dhamit/.Xauthority"}, check=False)
    except Exception:
        pass


async def cdp_eval(ws, expression: str):
    """Ejecuta expresión JS vía CDP y devuelve el valor evaluado."""
    req_id = int(time.time() * 1000) % 1000000
    payload = {
        "id": req_id,
        "method": "Runtime.evaluate",
        "params": {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True
        }
    }
    await ws.send(json.dumps(payload))
    while True:
        raw = await ws.recv()
        msg = json.loads(raw)
        if msg.get("id") == req_id:
            res = msg.get("result", {})
            if "exceptionDetails" in res:
                return {"error": res["exceptionDetails"]}
            return res.get("result", {}).get("value")


async def procesar_oferta(oferta: dict, perfil: dict, ws_url: str):
    of_id = oferta["id"]
    titulo = oferta["titulo"]
    empresa = oferta["empresa"]
    portal = oferta["portal"]
    url = oferta["url_oferta"]

    print(f"\n==========================================")
    print(f"Procesando oferta {of_id}: {empresa} | {titulo}")
    print(f"URL: {url}")
    print(f"==========================================")

    # 1. Anuncio inicial por voz en ráfagas cortas
    hablar(f"Abriendo oferta de {empresa}.")
    hablar(f"{titulo[:45]}.")

    async with websockets.connect(ws_url, ping_interval=None) as ws:
        # Navegar la pestaña activa a la URL si no está ya en ella
        curr_url = await cdp_eval(ws, "window.location.href") or ""
        if not (url in curr_url or of_id_match(curr_url, url)):
            await cdp_eval(ws, f"window.location.href = '{url}';")
            await asyncio.sleep(2.5)

        traer_brave_al_frente()

        # Descartar cookies / banners
        js_dismiss = """
        (() => {
            for (let b of document.querySelectorAll('button')) {
                if (/aceptar|entendido|cerrar/i.test(b.textContent) && b.offsetWidth > 0) {
                    b.click();
                    break;
                }
            }
        })()
        """
        await cdp_eval(ws, js_dismiss)
        await asyncio.sleep(0.5)

        # 2. Pulsar botón 'Postula fácil' / 'Postular' si el formulario aún no está abierto
        has_questions = await cdp_eval(ws, "document.querySelectorAll('div[id^=\"pregunta_\"]').length > 0")
        if not has_questions:
            js_click_postula = """
            (() => {
                const btn = document.querySelector('#applyOfferSticky') || 
                            Array.from(document.querySelectorAll('button, a')).find(b => 
                                /postula fácil|postular ahora|postularme|postular/i.test(b.textContent) && b.offsetWidth > 0
                            );
                if (btn) {
                    btn.scrollIntoView({ block: 'center' });
                    btn.click();
                    return 'Clicked: ' + btn.textContent.trim();
                }
                return 'No postular button';
            })()
            """
            res_btn = await cdp_eval(ws, js_click_postula)
            print("Pulsar Postular:", res_btn)
            await asyncio.sleep(1.2)

            # 3. Si aparece modal con botón 'Comenzar', pulsarlo
            js_click_comenzar = """
            (() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => 
                    b.textContent.trim().toLowerCase() === 'comenzar' && b.offsetWidth > 0
                );
                if (btn) {
                    btn.click();
                    return 'Clicked Comenzar';
                }
                return 'No comenzar button';
            })()
            """
            res_com = await cdp_eval(ws, js_click_comenzar)
            print("Pulsar Comenzar:", res_com)
            await asyncio.sleep(1.2)

        # Cerrar guía de respuestas automáticas si aparece
        js_close_guia = """
        (() => {
            const m = document.getElementById('guiarespuestasautomaticas');
            if (m && m.offsetWidth > 0) {
                const b = m.querySelector('button');
                if (b) b.click();
            }
        })()
        """
        await cdp_eval(ws, js_close_guia)
        await asyncio.sleep(0.3)

        # 4. Inspeccionar preguntas extrayendo textContent de forma exacta
        js_get_blocks = """
        (() => {
            const blocks = Array.from(document.querySelectorAll('div[id^="pregunta_"]')).filter(b => b.offsetWidth > 0);
            return blocks.map((b, idx) => {
                const lbl1 = b.querySelector('label.type1');
                const lbl2 = b.querySelector('label.type2');
                const num = lbl1 ? lbl1.textContent.trim().replace(/\\s+/g, ' ') : ('Pregunta ' + (idx + 1));
                const txt = lbl2 ? lbl2.textContent.trim().replace(/\\s+/g, ' ') : '';
                
                const ta = b.querySelector('textarea');
                const inp = b.querySelector('input:not([type="hidden"])');
                
                return {
                    id: (ta || inp) ? (ta || inp).id : b.id,
                    tag: ta ? 'textarea' : (inp ? 'input' : 'unknown'),
                    numero: num,
                    pregunta: txt
                };
            });
        })()
        """
        blocks = await cdp_eval(ws, js_get_blocks) or []
        print(f"Bloques de preguntas encontrados: {len(blocks)}")

        qa_pairs = []
        for idx, blk in enumerate(blocks, 1):
            num = blk.get("numero") or f"Pregunta {idx}"
            raw_q = blk.get("pregunta") or ""
            q_clean = limpiar_texto_pregunta(raw_q)
            if not q_clean or len(q_clean) < 4:
                q_clean = f"Pregunta {idx}"
            
            tipo = "textarea" if blk.get("tag") == "textarea" else "text"
            resp = resolver_pregunta_reclutador(q_clean, empresa, tipo_input=tipo)
            qa_pairs.append({
                "id": blk.get("id"),
                "tag": blk.get("tag"),
                "numero": num,
                "pregunta": q_clean,
                "respuesta": resp
            })

        # 5. Rellenar los campos en la página de forma segura (sin Illegal invocation)
        js_fill = f"""
        (() => {{
            const data = {json.dumps(qa_pairs)};
            for (let item of data) {{
                if (!item.id) continue;
                const el = document.getElementById(item.id);
                if (!el) continue;
                el.focus();
                if (el.tagName === 'TEXTAREA') {{
                    const taSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                    taSetter.call(el, item.respuesta);
                }} else if (el.tagName === 'INPUT') {{
                    const inSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    inSetter.call(el, item.respuesta);
                }}
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}

            // Habilitar botón de responder/postular
            const btn = Array.from(document.querySelectorAll('button')).find(b => 
                /responder|postular/i.test(b.textContent) && b.offsetWidth > 0
            );
            if (btn) {{
                btn.removeAttribute('disabled');
                btn.classList.remove('boton-deshabilitado');
            }}

            return 'Campos rellenados con éxito: ' + data.length;
        }})()
        """
        res_fill = await cdp_eval(ws, js_fill)
        print("Resultado relleno:", res_fill)

        # 6. Locución estricta y ordenada: Pregunta -> Respuesta
        if qa_pairs:
            hablar(f"El reclutador solicita responder {len(qa_pairs)} preguntas.")
            for i, qa in enumerate(qa_pairs, 1):
                p_text = qa['pregunta']
                r_text = qa['respuesta']
                
                # Leer la pregunta
                hablar(f"Pregunta {i}: {p_text}")
                
                # Leer la respuesta de forma concisa y clara
                hablar(f"Respuesta: {r_text}")
        else:
            hablar("Formulario estándar sin preguntas adicionales.")

        # 7. Avisar al usuario: Puedes postular ya
        hablar("Puedes postular ya.")
        hablar("Mira lo que escribí en tu pantalla y presiona Responder cuando gustes.")

        # 8. Instalar detector de clic en el botón de postular
        js_install_listener = """
        (() => {
            window.__postulacion_pulsada = false;
            const btn = Array.from(document.querySelectorAll('button')).find(b => 
                /responder|postular/i.test(b.textContent) && b.offsetWidth > 0
            );
            if (btn) {
                btn.addEventListener('click', () => {
                    window.__postulacion_pulsada = true;
                });
                return 'Listener instalado en botón: ' + btn.textContent.trim();
            }
            return 'No se encontró botón para escuchar';
        })()
        """
        listen_res = await cdp_eval(ws, js_install_listener)
        print("Listener:", listen_res)

        # 9. Monitorear clic del usuario en tiempo real
        print("👀 Esperando que el usuario presione el botón en su pantalla...")
        clicked_detected = False
        start_wait = time.time()

        while time.time() - start_wait < 180:  # Espera de hasta 3 minutos
            check_state = """
            (() => {
                if (window.__postulacion_pulsada) return 'clicked';
                const body = document.body.innerText.toLowerCase();
                if (body.includes('éxito') || body.includes('confirmacion-postulacion') || body.includes('sé premium por')) {
                    return 'success_page';
                }
                const btn = Array.from(document.querySelectorAll('button')).find(b => 
                    /responder|postular/i.test(b.textContent) && b.offsetWidth > 0
                );
                if (!btn) return 'btn_disappeared';
                return 'waiting';
            })()
            """
            st = await cdp_eval(ws, check_state)
            if st in ["clicked", "success_page", "btn_disappeared"]:
                clicked_detected = True
                print(f"✅ ¡Detección exitosa de postulación! Estado: {st}")
                break
            await asyncio.sleep(0.8)

        if clicked_detected:
            await asyncio.sleep(2.0)
            hablar("¡Postulación enviada y detectada con éxito!")
            hablar("Guardando en la base de datos.")

            # Guardar en base de datos
            conn = database.get_conn()
            cur = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            cur.execute("""
                UPDATE postulaciones 
                SET estado = '🟢 Postulado Confirmado', fecha_postulacion = ?
                WHERE id = ?
            """, (now_str, of_id))
            conn.commit()
            conn.close()
            return True
        else:
            hablar("Tiempo de espera agotado. Puedes confirmar manualmente en el chat.", final=True)
            return False


def of_id_match(curr_url: str, target_url: str) -> bool:
    m1 = re.search(r"/(\d+)-", curr_url)
    m2 = re.search(r"/(\d+)-", target_url)
    if m1 and m2 and m1.group(1) == m2.group(1):
        return True
    return False


async def main():
    parser = argparse.ArgumentParser(description="Copiloto Interactivo de Detección de Postulación")
    parser.add_argument("--id", type=int, help="ID de oferta específico")
    args = parser.parse_args()

    perfil = database.obtener_perfil()
    conn = database.get_conn()
    cur = conn.cursor()

    if args.id:
        cur.execute("SELECT id, titulo, empresa, portal, url_oferta, estado FROM postulaciones WHERE id = ?", (args.id,))
    else:
        cur.execute("""
            SELECT id, titulo, empresa, portal, url_oferta, estado 
            FROM postulaciones 
            WHERE estado NOT LIKE '%postulado%' AND estado NOT LIKE '%confirmado%' AND estado NOT LIKE '%cerrada%'
            ORDER BY id ASC LIMIT 1
        """)
    row = cur.fetchone()
    conn.close()

    if not row:
        print("No hay más ofertas pendientes.")
        hablar("No hay más ofertas pendientes.", final=True)
        return

    oferta = dict(row)

    # Buscar la pestaña activa en Brave
    tabs_res = urllib.request.urlopen("http://localhost:9222/json/list").read().decode("utf-8")
    tabs = json.loads(tabs_res)
    
    target_tab = None
    for t in tabs:
        if "trabajando" in t.get("url", ""):
            target_tab = t
            break
    if not target_tab and tabs:
        target_tab = tabs[0]

    ws_url = target_tab["webSocketDebuggerUrl"]
    print(f"Conectando a pestaña: {target_tab.get('title')[:40]} vía {ws_url}")

    success = await procesar_oferta(oferta, perfil, ws_url)
    print(json.dumps({"id": oferta["id"], "success": success}))


if __name__ == "__main__":
    asyncio.run(main())
