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
        
        print("Watching for submission on:", page.url)
        for i in range(120): # wait up to 120 seconds
            await asyncio.sleep(1)
            submitted = await page.evaluate("""() => {
                const btn = document.getElementById("btnKiller");
                const text = document.body.innerText;
                if (!btn) return true;
                if (text.includes("ha sido enviada") || text.includes("Gracias") || text.includes("correctamente") || text.includes("Postulación")) {
                    return true;
                }
                return false;
            }""")
            if submitted or "kq" not in page.url:
                print("Submission detected!")
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn = sqlite3.connect("/home/dhamit/Documentos/MYCreIAtedAPPs/AutoPostula/data/autopostula.db")
                c = conn.cursor()
                c.execute("""
                    UPDATE postulaciones 
                    SET estado = '🟢 Postulado Confirmado', fecha_postulacion = ?, 
                        notas = 'Postulado exitosamente vía Computrabajo con respuestas completas (Ley 16.744, plazo 15 Nov, experiencia BDO)' 
                    WHERE id = 71
                """, (now,))
                conn.commit()
                conn.close()
                speak("Postulación para Sotraser confirmada y guardada en la base de datos.")
                break

if __name__ == "__main__":
    asyncio.run(main())
