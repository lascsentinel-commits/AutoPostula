#!/usr/bin/env python3
"""
Abre las ofertas que requieren inicio de sesión (ClaveÚnica / Estado en Prácticas Chile)
en Brave Browser con el widget flotante de 30s (Pausar/Reanudar) y locución Di.
"""

import asyncio
import os
import subprocess
import sys
from playwright.async_api import async_playwright

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from bucle_pantalla_interactivo import inyectar_boton_flotante_control, traer_brave_al_frente, hablar

OFERTAS_LOGIN = [
    {
        "id": 145,
        "entidad": "Servicio de Impuestos Internos (SII)",
        "cargo": "Práctica Profesional Arquitectura de Datos / TI",
        "url": "https://practicas2.serviciocivil.cl/concursos-spl/opencms/convocatorias/OP-31241"
    },
    {
        "id": 101,
        "entidad": "Dirección General de Concesiones (MOP)",
        "cargo": "Práctica Profesional Análisis Estratégico y TI",
        "url": "https://practicas2.serviciocivil.cl/concursos-spl/opencms/convocatorias/OP-31161"
    }
]


async def abrir_ofertas_login(segundos_espera: int = 30):
    print("==========================================================")
    print("🔐 ABRIENDO OFERTAS CON REQUISITO DE LOGIN (CLAVEÚNICA)")
    print(f"⏱️  Pausa para iniciar sesión: {segundos_espera}s (ampliable con botón Pausar)")
    print("🔘 Widget interactivo: Esquina inferior izquierda")
    print("==========================================================")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            ctx = browser.contexts[0]
        except Exception as e:
            print(f"❌ Error conectando a Brave CDP: {e}")
            hablar("Error conectando con Brave en puerto 9222.", final=True)
            return

        for idx, of in enumerate(OFERTAS_LOGIN, 1):
            of_id = of["id"]
            entidad = of["entidad"]
            cargo = of["cargo"]
            url = of["url"]

            print(f"\n>>> [{idx}/{len(OFERTAS_LOGIN)}] Abriendo oferta #{of_id}: {entidad} - {cargo}")
            hablar(f"Abriendo oferta de {entidad} para {cargo}. Tienes 30 segundos para ingresar con tu ClaveÚnica o pausar en la esquina inferior izquierda.")

            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2.0)
            except Exception as e:
                print(f"Aviso al cargar {url}: {e}")

            # Traer Brave al frente
            traer_brave_al_frente()

            # Inyectar widget flotante
            await inyectar_boton_flotante_control(page)

            # Buscar y pulsar el botón Postular / Iniciar sesión si existe en la página
            try:
                btns_post = await page.locator("a:has-text('Postular'), button:has-text('Postular'), a:has-text('Iniciar Sesión'), button:has-text('ClaveÚnica')").all()
                for b in btns_post:
                    if await b.is_visible():
                        print(f"Pulsando botón de postulación / login: {await b.inner_text()}")
                        await b.click()
                        await asyncio.sleep(2.0)
                        break
            except Exception as e:
                print(f"Aviso al buscar botón: {e}")

            await inyectar_boton_flotante_control(page)

            # Cuenta regresiva con pausa interactiva
            tiempo = 0.0
            esta_pausado = False

            while tiempo < segundos_espera:
                st = {}
                try:
                    st = await page.evaluate('''() => {
                        return {
                            stop: window.__autopostula_stop || false,
                            paused: window.__autopostula_paused || false,
                            url: window.location.href,
                            hasSession: !document.body.innerText.toLowerCase().includes('iniciar sesión') && !document.body.innerText.toLowerCase().includes('clave única')
                        };
                    }''')
                except Exception:
                    # Ocurre mientras navega entre páginas (ej. redirigiendo a ClaveÚnica)
                    await asyncio.sleep(0.5)
                    try:
                        await inyectar_boton_flotante_control(page)
                    except Exception:
                        pass
                    continue

                if st.get("stop"):
                    print("\n🛑 Proceso detenido por el usuario con la X roja.")
                    hablar("Proceso detenido por el usuario.")
                    return

                if st.get("paused"):
                    if not esta_pausado:
                        print(f"\n⏸️  PAUSADO por el usuario. Tómate el tiempo necesario para ingresar tu ClaveÚnica.")
                        hablar("Pausado. Ingresa tu ClaveÚnica con tranquilidad y presiona Reanudar.")
                        esta_pausado = True
                    await asyncio.sleep(0.5)
                    continue
                else:
                    if esta_pausado:
                        print(f"\n▶️  REANUDADO.")
                        hablar("Reanudado.")
                        esta_pausado = False

                    restante = int(segundos_espera - tiempo)
                    try:
                        await page.evaluate(f'''() => {{
                            window.__autopostula_timer_text = '{restante}s';
                            const t = document.getElementById('autopostula-timer');
                            if (t) t.innerText = '{restante}s';
                        }}''')
                    except Exception:
                        pass

                    print(f"\r⏱️  Tiempo restante para login: {restante:02d}s | [⏸️ Pausar | ❌ Cerrar en esquina inferior izquierda]...", end="", flush=True)
                    await asyncio.sleep(0.5)
                    tiempo += 0.5

            print("\n⏰ Tiempo de espera cumplido para esta oferta.")
            hablar(f"Tiempo cumplido para {entidad}.")
            await asyncio.sleep(2.0)

    print("\n✅ Proceso de apertura de ofertas con login completado.")
    hablar("Apertura de ofertas con login completada.", final=True)


if __name__ == "__main__":
    seg = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    asyncio.run(abrir_ofertas_login(segundos_espera=seg))

