#!/usr/bin/env python3
import asyncio
import os
import sqlite3
import subprocess
from datetime import datetime
from playwright.async_api import async_playwright

if "PLAYWRIGHT_NODEJS_PATH" not in os.environ and os.path.exists("/home/dhamit/.local/bin/pw_node_wrapper.sh"):
    os.environ["PLAYWRIGHT_NODEJS_PATH"] = "/home/dhamit/.local/bin/pw_node_wrapper.sh"

def speak(msg):
    subprocess.run(["/home/dhamit/.local/bin/Di"], input=msg.encode("utf-8"))

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]
        
        print("Watching Offer 72 on:", page.url)
        submitted = False
        for i in range(120): # up to 120s
            await asyncio.sleep(1)
            submitted = await page.evaluate("""() => {
                const text = document.body.innerText.toLowerCase();
                const btn = document.querySelector('input[type=submit][value*="Enviar"], button:has-text("Enviar")');
                if (text.includes("gracias") || text.includes("recibido") || text.includes("solicitud enviada") || text.includes("éxito") || text.includes("correctamente")) {
                    return true;
                }
                return false;
            }""")
            if submitted or "teamtailor.com/jobs" not in page.url:
                print("Submission detected for Offer 72!")
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn = sqlite3.connect("/home/dhamit/Documentos/MYCreIAtedAPPs/AutoPostula/data/autopostula.db")
                c = conn.cursor()
                c.execute("""
                    UPDATE postulaciones 
                    SET estado = '🟢 Postulado Confirmado', fecha_postulacion = ?, 
                        notas = 'Postulado exitosamente vía Teamtailor Olitel con CV adjunto y datos Duoc UC' 
                    WHERE id = 72
                """, (now,))
                conn.commit()
                conn.close()
                speak("Postulación para Olitel confirmada y guardada. Cargando ahora la siguiente oferta de Accenture.")
                
                # Navigate to Offer 73
                url_73 = "https://cl.linkedin.com/jobs/view/pr%C3%A1ctica-ing-conectividad-y-redes-changemakers-internship-program-at-accenture-chile-4480423670"
                await page.goto(url_73, timeout=30000)
                await page.wait_for_timeout(3000)
                break

if __name__ == "__main__":
    asyncio.run(main())
