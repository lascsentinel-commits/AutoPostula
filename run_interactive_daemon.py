#!/usr/bin/env python3
"""
Demostrador y Servidor Continuo de Copiloto Interactivo con Voz
AutoPostula v3.0

Detecta el clic del usuario en la oferta actual, confirma y avanza automáticamente a la siguiente.
"""

import asyncio
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.request
import websockets
from datetime import datetime

import database
from modules.smart_qa_solver import resolver_pregunta_reclutador, limpiar_texto_pregunta


def hablar(texto: str, final: bool = False):
    cmd = ["/home/dhamit/.local/bin/Di"]
    if final:
        cmd.append("--final")
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
        proc.communicate(input=texto)
    except Exception as e:
        print(f"Error ejecutando Di: {e}", file=sys.stderr)


def traer_brave():
    try:
        subprocess.run(["wmctrl", "-a", "Brave"], env={"DISPLAY": ":0", "XAUTHORITY": "/home/dhamit/.Xauthority"}, check=False)
    except Exception:
        pass


async def cdp_eval(ws, expression: str):
    req_id = int(time.time() * 100000) % 10000000
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
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            msg = json.loads(raw)
            if msg.get("id") == req_id:
                res = msg.get("result", {})
                if "exceptionDetails" in res:
                    return {"error": res["exceptionDetails"]}
                return res.get("result", {}).get("value")
        except asyncio.TimeoutError:
            return None


async def preparar_oferta_en_pantalla(ws, oferta: dict, perfil: dict):
    of_id = oferta["id"]
    titulo = oferta["titulo"]
    empresa = oferta["empresa"]
    url = oferta["url_oferta"]

    print(f"\n==========================================")
    print(f"Preparando oferta {of_id}: {empresa} | {titulo}")
    print(f"URL: {url}")
    print(f"==========================================")

    hablar(f"Abriendo oferta de {empresa}.")
    hablar(f"{titulo[:45]}.")

    # Navegar
    curr_url = await cdp_eval(ws, "window.location.href") or ""
    if url not in curr_url:
        await cdp_eval(ws, f"window.location.href = '{url}';")
        await asyncio.sleep(2.5)

    traer_brave()

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

    # Pulsar 'Postula fácil' / 'Postular'
    js_click_postula = """
    (() => {
        const btn = document.querySelector('#applyOfferSticky') || 
                    Array.from(document.querySelectorAll('button, a')).find(b => 
                        /postula fácil|postular ahora|postularme|postular/i.test(b.textContent) && b.offsetWidth > 0
                    );
        if (btn) {
            btn.scrollIntoView({ block: 'center' });
            btn.click();
            return 'Clicked postular';
        }
        return 'No postular';
    })()
    """
    await cdp_eval(ws, js_click_postula)
    await asyncio.sleep(1.2)

    # Pulsar 'Comenzar'
    js_click_comenzar = """
    (() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => 
            b.textContent.trim().toLowerCase() === 'comenzar' && b.offsetWidth > 0
        );
        if (btn) {
            btn.click();
            return 'Clicked Comenzar';
        }
        return 'No comenzar';
    })()
    """
    await cdp_eval(ws, js_click_comenzar)
    await asyncio.sleep(1.2)

    # Descartar guía respuestas automáticas
    await cdp_eval(ws, """
    (() => {
        const m = document.getElementById('guiarespuestasautomaticas');
        if (m && m.offsetWidth > 0) {
            const b = m.querySelector('button');
            if (b) b.click();
        }
    })()
    """)
    await asyncio.sleep(0.3)

    # Inspeccionar preguntas
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
        raw_q = blk.get("pregunta") or ""
        q_clean = limpiar_texto_pregunta(raw_q)
        if not q_clean or len(q_clean) < 4:
            q_clean = f"Pregunta {idx}"
        
        tipo = "textarea" if blk.get("tag") == "textarea" else "text"
        resp = resolver_pregunta_reclutador(q_clean, empresa, tipo_input=tipo)
        qa_pairs.append({
            "id": blk.get("id"),
            "tag": blk.get("tag"),
            "numero": blk.get("numero"),
            "pregunta": q_clean,
            "respuesta": resp
        })

    # Rellenar
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

        const btn = Array.from(document.querySelectorAll('button')).find(b => 
            /responder|postular/i.test(b.textContent) && b.offsetWidth > 0
        );
        if (btn) {{
            btn.removeAttribute('disabled');
            btn.classList.remove('boton-deshabilitado');
        }}

        return 'Rellenados: ' + data.length;
    }})()
    """
    await cdp_eval(ws, js_fill)

    # Locución ordenada
    if qa_pairs:
        hablar(f"El reclutador solicita responder {len(qa_pairs)} preguntas.")
        for i, qa in enumerate(qa_pairs, 1):
            hablar(f"Pregunta {i}: {qa['pregunta']}")
            hablar(f"Respuesta: {qa['respuesta']}")
    else:
        hablar("Formulario sin preguntas adicionales.")

    hablar("Puedes postular ya.")
    hablar("Mira lo que escribí en tu pantalla y presiona Responder cuando gustes.")


async def main():
    perfil = database.obtener_perfil()

    # Obtener websocket de pestaña de Trabajando.cl
    tabs_res = urllib.request.urlopen("http://localhost:9222/json/list").read().decode("utf-8")
    tabs = json.loads(tabs_res)
    target_tab = next((t for t in tabs if "trabajando" in t.get("url", "")), tabs[0])
    ws_url = target_tab["webSocketDebuggerUrl"]

    print(f"Iniciando Copiloto Continuo en: {target_tab.get('title')[:40]}")

    async with websockets.connect(ws_url, ping_interval=None) as ws:
        # Instalar listener de clic global para la oferta actual
        await cdp_eval(ws, """
        (() => {
            window.__user_clicked_action = false;
            window.addEventListener('click', (e) => {
                if (e.target && /responder|postular/i.test(e.target.textContent)) {
                    window.__user_clicked_action = true;
                }
            }, true);
        })()
        """)

        # Bucle continuo: esperar clic -> guardar -> abrir siguiente
        while True:
            # 1. Obtener oferta pendiente actual
            conn = database.get_conn()
            cur = conn.cursor()
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
                hablar("No quedan más ofertas pendientes por postular.", final=True)
                break

            oferta = dict(row)
            of_id = oferta["id"]

            # Comprobar si la oferta actual ya está abierta o si hay que prepararla
            curr_url = await cdp_eval(ws, "window.location.href") or ""
            is_same_offer = (str(of_id) in curr_url) or any(k in curr_url.lower() for k in oferta["empresa"].lower().split()[:2] if len(k) > 3)

            # Si no está en pantalla, prepararla
            has_questions = await cdp_eval(ws, "document.querySelectorAll('div[id^=\"pregunta_\"]').length > 0")
            if not is_same_offer or not has_questions:
                await preparar_oferta_en_pantalla(ws, oferta, perfil)

            # Esperar clic del usuario
            print(f"👀 Esperando clic del usuario para oferta {of_id} ({oferta['empresa']})...")
            await cdp_eval(ws, "window.__user_clicked_action = false;")

            clicked = False
            for _ in range(600):  # hasta 10 minutos por oferta
                await asyncio.sleep(0.8)
                check_state = """
                (() => {
                    if (window.__user_clicked_action) return 'clicked';
                    const body = document.body.innerText.toLowerCase();
                    if (body.includes('sé premium por') || body.includes('éxito') || body.includes('confirmacion-postulacion')) {
                        return 'success';
                    }
                    return 'waiting';
                })()
                """
                st = await cdp_eval(ws, check_state)
                if st in ["clicked", "success"]:
                    clicked = True
                    break

            if clicked:
                print(f"🎉 Clic detectado para oferta {of_id}!")
                await asyncio.sleep(2.0)
                hablar(f"¡Postulación a {oferta['empresa']} confirmada con éxito!")
                hablar("Guardando en la base de datos.")

                conn = database.get_conn()
                cur = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                cur.execute("UPDATE postulaciones SET estado = '🟢 Postulado Confirmado', fecha_postulacion = ? WHERE id = ?", (now_str, of_id))
                conn.commit()
                conn.close()

                hablar("Pasando a la siguiente oferta.")
                await asyncio.sleep(1.0)
            else:
                print("Tiempo de espera agotado para esta oferta.")
                break


if __name__ == "__main__":
    asyncio.run(main())

