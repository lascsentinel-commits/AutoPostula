#!/usr/bin/env python3
"""
AutoPostula v3.7 — Bucle Interactivo sobre Pantalla con Botón Flotante
Esquina Inferior Izquierda: Botón flotante para Pausar / Reanudar el Bot en vivo.
Filtro: Prácticas Técnicas en la Región Metropolitana (o Remoto/Híbrido).

Flujo Completo:
1. Navega a la oferta y enfoca Brave (wmctrl).
2. Inyecta el botón flotante en la esquina inferior izquierda (Pausar/Reanudar + Timer).
3. Presiona 'Postula fácil' (botón azul inicial).
4. Si aparece modal con 'Comenzar', lo presiona.
5. Rellena las preguntas con el perfil Duoc UC (smart_qa_solver).
6. Lee en voz alta CADA pregunta y su respuesta con Di.
7. Inicia los 30 segundos de pausa para revisión (el usuario puede pausar con el botón flotante).
8. Si transcurren los 30 segundos sin pausa ni clic manual, pulsa el segundo 'Postular'.
9. Verifica confirmación de éxito, actualiza autopostula.db y continúa en bucle.
"""

import argparse
import asyncio
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime

# Limpiar wrapper que causa conflicto con python3.13 en kali
from pathlib import Path
import shutil

os.environ.pop("PLAYWRIGHT_NODEJS_PATH", None)

from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import database
from modules.smart_qa_solver import (
    resolver_pregunta_reclutador,
    resolver_preguntas_con_gemini_en_lote,
    resolver_seleccion_dropdown,
    limpiar_texto_pregunta,
    obtener_perfil_activo,
)

DB_PATH = os.environ.get("AUTOPOSTULA_DB_PATH", str(BASE_DIR / "data" / "autopostula.db"))
CV_MASTER_PDF = os.environ.get("CV_MASTER_PDF", "/home/dhamit/Documentos/CV-2026-01/1_CV_Dhani_Amit_Elgueta_Ríos_U-26.pdf")
if not os.path.exists(CV_MASTER_PDF):
    local_cv = BASE_DIR / "cv.pdf"
    if local_cv.exists():
        CV_MASTER_PDF = str(local_cv)

# Comunas y referencias válidas para la Región Metropolitana
COMUNAS_RM = [
    "santiago", "metropolitana", "rm", "las condes", "condes", "providencia",
    "pudahuel", "cerrillos", "san bernardo", "independencia", "quilicura",
    "huechuraba", "renca", "maipú", "maipu", "la florida", "ñuñoa", "nunoa",
    "vitacura", "lo barnechea", "pedro aguirre cerda", "estación central",
    "estacion central", "centro", "recoleta", "ciudad empresarial", "san joaquín",
    "san joaquin", "macul", "peñalolén", "penalolen", "quinta normal", "conchalí",
    "conchali", "lo prado", "cerro navia", "colina", "lampa",
    "chicureo", "remoto", "remota", "híbrido", "hibrido", "teletrabajo", "region13"
]

# Regiones fuera de la RM que deben ser descartadas
REGIONES_EXCLUIDAS = [
    "talca", "valdivia", "concepción", "concepcion", "antofagasta", "la serena",
    "laserena", "coquimbo", "temuco", "puerto montt", "puerto varas", "rancagua",
    "iquique", "arica", "chillán", "chillan", "punta arenas", "quilpué", "quilpue",
    "valparaíso", "valparaiso", "viña del mar", "viña", "vina", "maule",
    "biobío", "biobio", "araucanía", "araucania", "los lagos", "los ríos",
    "los rios", "ohiggins", "o'higgins", "calama", "copiapó", "copiapo"
]


GLOBAL_CON_VOZ = True
GLOBAL_ENFOCAR = True

def hablar(texto: str, final: bool = False):
    """Ejecuta Di para narrar en tiempo real si está habilitado; soporta Linux y Windows 11 con Edge-TTS."""
    if not GLOBAL_CON_VOZ:
        return

    di_system = "/home/dhamit/.local/bin/Di"
    local_di_py = BASE_DIR / "bin" / "di.py"

    if os.path.exists(di_system):
        cmd = [di_system]
    elif local_di_py.exists():
        cmd = [sys.executable, str(local_di_py)]
    elif shutil.which("Di"):
        cmd = ["Di"]
    else:
        cmd = None

    if cmd:
        if final:
            cmd.append("--final")
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
            proc.communicate(input=texto)
            return
        except Exception as e:
            print(f"Error Di: {e}", file=sys.stderr)

    # Si estamos en Windows y no hay Di ejecutable, usar síntesis SAPI nativa
    if sys.platform == "win32":
        try:
            clean_txt = texto.replace('"', '').replace("'", "").replace("`", "")
            ps_cmd = f'Add-Type -AssemblyName System.Speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; $speak.Speak("{clean_txt}")'
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass

    # Fallback si no hay motor de voz activo
    print(f"📢 [VOZ]: {texto}")


def traer_brave_al_frente():
    """Enfoca la ventana del navegador en la pantalla (Linux X11 o Windows)."""
    if not GLOBAL_ENFOCAR:
        return
    if sys.platform != "win32":
        try:
            subprocess.run(
                ["wmctrl", "-a", "Brave"],
                env={"DISPLAY": os.environ.get("DISPLAY", ":0"), "XAUTHORITY": os.environ.get("XAUTHORITY", "/home/dhamit/.Xauthority")},
                check=False
            )
        except Exception:
            pass
    else:
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", "(New-Object -ComObject WScript.Shell).AppActivate('Brave')"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def es_region_metropolitana(ubicacion: str, titulo: str, descripcion: str = "") -> bool:
    """Verifica si la oferta pertenece estrictamente a la Región Metropolitana o es Remota."""
    texto_total = f"{ubicacion} {titulo} {descripcion}".lower()

    for reg in REGIONES_EXCLUIDAS:
        if reg in texto_total:
            if not any(rm in ubicacion.lower() for rm in ["santiago", "metropolitana", "rm", "region13"]):
                return False

    if any(rm in texto_total for rm in COMUNAS_RM):
        return True

    if "chile" in ubicacion.lower() and not any(reg in ubicacion.lower() for reg in REGIONES_EXCLUIDAS):
        return True

    return False


def obtener_ofertas_validas_pendientes(limite: int = 100, solo_id: int = None):
    """Filtra y devuelve estrictamente ofertas de práctica técnica en la Región Metropolitana (priorizando las más recientes)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if solo_id:
        c.execute("SELECT * FROM postulaciones WHERE id = ?", (solo_id,))
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    query = """
    SELECT *
    FROM postulaciones
    WHERE (estado LIKE '%Cola%' OR estado LIKE '%Lista%')
      AND (
           LOWER(titulo) LIKE '%práctica%'
           OR LOWER(titulo) LIKE '%practica%'
           OR LOWER(titulo) LIKE '%practicante%'
           OR LOWER(titulo) LIKE '%alumno%'
           OR LOWER(titulo) LIKE '%trainee%'
      )
      AND NOT (
           LOWER(titulo) LIKE '%rrhh%'
           OR LOWER(titulo) LIKE '%bodega%'
           OR LOWER(titulo) LIKE '%abastecimiento%'
           OR LOWER(titulo) LIKE '%psicolog%'
           OR LOWER(titulo) LIKE '%enfermer%'
           OR LOWER(titulo) LIKE '%prevencion%'
           OR LOWER(titulo) LIKE '%comercial%'
           OR LOWER(titulo) LIKE '%marketing%'
           OR LOWER(titulo) LIKE '%social%'
           OR LOWER(titulo) LIKE '%redes sociales%'
           OR LOWER(titulo) LIKE '%quimic%'
           OR LOWER(titulo) LIKE '%geolog%'
           OR LOWER(titulo) LIKE '%administrativ%'
           OR LOWER(titulo) LIKE '%contadur%'
           OR LOWER(titulo) LIKE '%facility%'
           OR LOWER(titulo) LIKE '%seleccion%'
           OR LOWER(titulo) LIKE '%selección%'
           OR LOWER(titulo) LIKE '%contralor%'
           OR LOWER(titulo) LIKE '%s&op%'
           OR LOWER(titulo) LIKE '%industrial%'
           OR LOWER(titulo) LIKE '%negocios%'
           OR LOWER(titulo) LIKE '%administración pública%'
           OR LOWER(titulo) LIKE '%administracion publica%'
           OR LOWER(titulo) LIKE '%banco de talentos%'
           OR LOWER(titulo) LIKE '%mantenimiento industrial%'
           OR LOWER(titulo) LIKE '%desarrollo de producto%'
           OR LOWER(titulo) LIKE '%desarrollo organizacional%'
           OR LOWER(titulo) LIKE '%desarrollo de personas%'
           OR LOWER(titulo) LIKE '%desarrollo comercial%'
      )
    ORDER BY (CASE WHEN created_at >= date('now', '-5 days') THEN 1 ELSE 0 END) DESC, score_duoc DESC, id DESC;
    """
    c.execute(query)
    candidatas = [dict(r) for r in c.fetchall()]
    conn.close()

    pat_ti_estricto = re.compile(
        r'\b(ti|it|t\.i|infraestructura|redes|conectividad|telecomunicaciones|ciberseguridad|seguridad ti|seguridad de la información|soporte|sistemas|cloud|devops|servidores|linux|plataformas|mesa de servicio|informática|informatica|data engineering|qa|automatización|automatizacion|programación|programacion|software|continuidad operativa|continuidad operacional)\b',
        re.I
    )

    filtradas = []
    vistos_keys = set()
    for cand in candidatas:
        ubi = cand.get("ubicacion") or ""
        tit = cand.get("titulo") or ""
        emp = cand.get("empresa") or ""
        desc = cand.get("descripcion") or ""
        if not pat_ti_estricto.search(tit):
            continue
        if "redes sociales" in tit.lower():
            continue
        if not es_region_metropolitana(ubi, tit, desc):
            continue
        dedup_key = (emp.lower().strip(), tit.lower().strip())
        if dedup_key in vistos_keys:
            continue
        vistos_keys.add(dedup_key)
        filtradas.append(cand)

    return filtradas[:limite]


def es_url_catalogo(url: str, portal: str = "") -> bool:
    """Detecta si la URL actual es una página de catálogo, búsqueda o lista general de ofertas."""
    if not url:
        return False
    u = url.split("?")[0].rstrip("/").lower()
    
    # Rutas típicas de catálogo/búsqueda general
    if u.endswith(("/ofertas", "/trabajos", "/empleos", "/buscar", "/search", "/portal", "/postulaciones", "/concursos")):
        return True
    
    # FirstJob: Las ofertas individuales son https://firstjob.me/oferta/<id>/...
    if "firstjob.me" in u:
        if "/oferta/" not in u:
            return True
            
    # Computrabajo: Las ofertas individuales tienen /oferta-de-trabajo-de-
    if "computrabajo.cl" in u:
        if "/ofertas-de-trabajo" in u and "/oferta-de-trabajo-de-" not in u:
            return True
        if u.endswith("/empleos") or ("/trabajo-de-" in u and "/oferta-de-trabajo-de-" not in u):
            return True

    # Trabajando:
    if "trabajando.cl" in u:
        if u.endswith(("/trabajo", "/ofertas-empleo", "/buscar")):
            return True

    return False


FRASES_CERRADA = [
    "oferta finalizada", "oferta cerrada", "proceso finalizado", "ya no está disponible",
    "aviso finalizado", "404", "ha cerrado su proceso", "ya ha cerrado", "cerrado su proceso",
    "proceso de postulación cerrado", "este aviso ha expirado", "la publicación ha finalizado",
    "esta oferta ha expirado", "esta búsqueda ha finalizado", "convocatoria ha finalizado",
    "oferta pausada", "no se encuentra disponible", "lo sentimos! esta oferta",
    "lo sentimos, esta oferta", "esta oferta ya no", "no disponible actualmente"
]


async def inyectar_boton_flotante_control(page):
    """Inyecta el panel interactivo desplegable (ventanita de control) en la esquina inferior izquierda.
    Contiene:
    - Pastilla flotante siempre visible con estado y temporizador.
    - Ventanita modal desplegable al hacer clic, con:
      * Botón interactivo de Pausar / Reanudar.
      * Selector de tiempo para cambiar dinámicamente los segundos de revisión (15s, 30s, 60s, 2m).
      * Botón 'Enviar Postulación Ahora' para omitir la espera si ya se revisó.
      * Botón de cierre y detención total del bot.
    """
    js_inject = """
    (() => {
        window.__autopostula_paused = window.__autopostula_paused || false;
        window.__autopostula_stop = window.__autopostula_stop || false;
        window.__autopostula_skip_wait = false;
        window.__autopostula_timer_text = window.__autopostula_timer_text || "30s";
        window.__autopostula_segundos_revision = window.__autopostula_segundos_revision || 30;
        window.__autopostula_panel_open = window.__autopostula_panel_open !== undefined ? window.__autopostula_panel_open : false;

        function updateWidgetState() {
            const pill = document.getElementById('autopostula-floating-pill');
            const modal = document.getElementById('autopostula-floating-modal');
            if (!pill) return;

            const pillIcon = document.getElementById('autopostula-pill-icon');
            const pillLabel = document.getElementById('autopostula-pill-label');
            const pillTimer = document.getElementById('autopostula-pill-timer');

            const modalToggleBtn = document.getElementById('autopostula-modal-toggle');
            const modalTimer = document.getElementById('autopostula-modal-timer');

            if (window.__autopostula_stop) {
                pill.style.borderColor = '#ef4444';
                if (pillLabel) pillLabel.innerText = 'Cerrando bot...';
                if (pillTimer) { pillTimer.innerText = 'STOP'; pillTimer.style.background = '#dc2626'; }
                if (modal) modal.style.display = 'none';
                return;
            }

            if (window.__autopostula_paused) {
                pill.style.borderColor = '#f59e0b';
                pill.style.boxShadow = '0 0 25px rgba(245, 158, 11, 0.9)';
                if (pillIcon) pillIcon.innerText = '▶️';
                if (pillLabel) pillLabel.innerText = 'Pausado';
                if (pillTimer) { pillTimer.innerText = 'PAUSA'; pillTimer.style.background = '#d97706'; }

                if (modalToggleBtn) {
                    modalToggleBtn.innerText = '▶️ REANUDAR BOT';
                    modalToggleBtn.style.background = '#f59e0b';
                }
            } else {
                pill.style.borderColor = '#38bdf8';
                pill.style.boxShadow = '0 0 25px rgba(56, 189, 248, 0.85)';
                if (pillIcon) pillIcon.innerText = '⏸️';
                if (pillLabel) pillLabel.innerText = 'En Marcha';
                if (pillTimer) { pillTimer.innerText = window.__autopostula_timer_text || '30s'; pillTimer.style.background = '#0284c7'; }

                if (modalToggleBtn) {
                    modalToggleBtn.innerText = '⏸️ PAUSAR BOT';
                    modalToggleBtn.style.background = '#0284c7';
                }
            }

            if (modal) {
                modal.style.display = window.__autopostula_panel_open ? 'flex' : 'none';
            }
        }

        function createOrAttachWidget() {
            const targetParent = document.documentElement || document.body;
            if (!targetParent) return;

            let root = document.getElementById('autopostula-root-container');
            if (!root || root.parentElement !== targetParent) {
                if (root && root.remove) root.remove();

                root = document.createElement('div');
                root.id = 'autopostula-root-container';
                root.style.cssText = `
                    position: fixed !important;
                    bottom: 35px !important;
                    left: 35px !important;
                    z-index: 2147483647 !important;
                    display: flex !important;
                    flex-direction: column !important;
                    align-items: flex-start !important;
                    gap: 12px !important;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
                    user-select: none !important;
                `;

                // 1. VENTANITA MODAL FLOTANTE (ARRIBA DE LA PASTILLA)
                const modal = document.createElement('div');
                modal.id = 'autopostula-floating-modal';
                modal.style.cssText = `
                    display: ${window.__autopostula_panel_open ? 'flex' : 'none'} !important;
                    flex-direction: column !important;
                    gap: 12px !important;
                    width: 320px !important;
                    background: rgba(13, 17, 28, 0.98) !important;
                    border: 2px solid #38bdf8 !important;
                    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.9), 0 0 30px rgba(56, 189, 248, 0.4) !important;
                    border-radius: 16px !important;
                    padding: 16px !important;
                    color: #ffffff !important;
                    backdrop-filter: blur(20px) !important;
                `;

                modal.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid rgba(255,255,255,0.15); padding-bottom:8px;">
                        <div style="font-size:14px; font-weight:800; color:#38bdf8; display:flex; align-items:center; gap:6px;">
                            <span>⚙️ Panel AutoPostula</span>
                        </div>
                        <button id="autopostula-modal-close-window" style="background:transparent; border:none; color:#94a3b8; font-size:16px; font-weight:bold; cursor:pointer;">✕</button>
                    </div>

                    <div id="autopostula-modal-timer" style="font-size:13px; font-weight:700; color:#cbd5e1; text-align:center; padding:4px 0;">
                        ${window.__autopostula_timer_text} restantes
                    </div>

                    <!-- Botón Pausa / Reanudar -->
                    <button id="autopostula-modal-toggle" style="background:#0284c7; border:none; border-radius:10px; color:#ffffff; font-size:14px; font-weight:800; padding:10px; cursor:pointer; transition:all 0.15s ease;">
                        ${window.__autopostula_paused ? '▶️ REANUDAR BOT' : '⏸️ PAUSAR BOT'}
                    </button>

                    <!-- Selector de tiempo de espera -->
                    <div style="display:flex; flex-direction:column; gap:6px;">
                        <span style="font-size:12px; font-weight:700; color:#94a3b8;">⏱️ Tiempo de espera antes de enviar:</span>
                        <div style="display:flex; gap:6px; justify-content:space-between;">
                            <button class="autopostula-time-preset" data-seconds="15" style="flex:1; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.2); border-radius:8px; color:#fff; font-size:12px; font-weight:700; padding:5px 0; cursor:pointer;">15s</button>
                            <button class="autopostula-time-preset" data-seconds="30" style="flex:1; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.2); border-radius:8px; color:#fff; font-size:12px; font-weight:700; padding:5px 0; cursor:pointer;">30s</button>
                            <button class="autopostula-time-preset" data-seconds="60" style="flex:1; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.2); border-radius:8px; color:#fff; font-size:12px; font-weight:700; padding:5px 0; cursor:pointer;">60s</button>
                            <button class="autopostula-time-preset" data-seconds="120" style="flex:1; background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.2); border-radius:8px; color:#fff; font-size:12px; font-weight:700; padding:5px 0; cursor:pointer;">2m</button>
                        </div>
                    </div>

                    <!-- Botón Continuar / Enviar Ahora -->
                    <button id="autopostula-modal-skip" style="background:#10b981; border:none; border-radius:10px; color:#ffffff; font-size:13px; font-weight:800; padding:9px; cursor:pointer;">
                        🚀 Enviar Postulación Ahora
                    </button>

                    <!-- Botón Detener Bot -->
                    <button id="autopostula-modal-stop-bot" style="background:transparent; border:1px solid #ef4444; border-radius:10px; color:#ef4444; font-size:12px; font-weight:700; padding:7px; cursor:pointer;">
                        🛑 Detener Bot por Completo
                    </button>
                `;

                // 2. PASTILLA FLOTANTE PRINCIPAL
                const pill = document.createElement('div');
                pill.id = 'autopostula-floating-pill';
                pill.style.cssText = `
                    display: flex !important;
                    align-items: center !important;
                    gap: 10px !important;
                    background: rgba(13, 17, 28, 0.98) !important;
                    border: 3px solid #38bdf8 !important;
                    box-shadow: 0 0 25px rgba(56, 189, 248, 0.85), 0 8px 24px rgba(0, 0, 0, 0.8) !important;
                    border-radius: 9999px !important;
                    padding: 10px 18px !important;
                    color: #ffffff !important;
                    cursor: pointer !important;
                    font-size: 14px !important;
                    font-weight: 800 !important;
                    backdrop-filter: blur(16px) !important;
                    transition: transform 0.15s ease, box-shadow 0.2s ease !important;
                `;

                pill.innerHTML = `
                    <span id="autopostula-pill-icon" style="font-size:16px;">${window.__autopostula_paused ? '▶️' : '⏸️'}</span>
                    <span id="autopostula-pill-label">${window.__autopostula_paused ? 'Pausado' : 'Panel Bot'}</span>
                    <span id="autopostula-pill-timer" style="background:#0284c7; color:#fff; padding:2px 8px; border-radius:9999px; font-size:12px; font-weight:800;">${window.__autopostula_timer_text}</span>
                    <span style="font-size:14px; opacity:0.8; margin-left:4px;">⚙️</span>
                `;

                pill.addEventListener('click', (e) => {
                    e.stopPropagation();
                    window.__autopostula_panel_open = !window.__autopostula_panel_open;
                    updateWidgetState();
                });

                root.appendChild(modal);
                root.appendChild(pill);
                targetParent.appendChild(root);

                // Listeners de la ventanita modal
                const closeWindowBtn = modal.querySelector('#autopostula-modal-close-window');
                if (closeWindowBtn) {
                    closeWindowBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        window.__autopostula_panel_open = false;
                        updateWidgetState();
                    });
                }

                const toggleBtn = modal.querySelector('#autopostula-modal-toggle');
                if (toggleBtn) {
                    toggleBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        window.__autopostula_paused = !window.__autopostula_paused;
                        updateWidgetState();
                    });
                }

                const skipBtn = modal.querySelector('#autopostula-modal-skip');
                if (skipBtn) {
                    skipBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        window.__autopostula_skip_wait = true;
                        updateWidgetState();
                    });
                }

                const stopBtn = modal.querySelector('#autopostula-modal-stop-bot');
                if (stopBtn) {
                    stopBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        window.__autopostula_stop = true;
                        updateWidgetState();
                    });
                }

                modal.querySelectorAll('.autopostula-time-preset').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const s = parseInt(btn.getAttribute('data-seconds'), 10);
                        window.__autopostula_segundos_revision = s;
                        modal.querySelectorAll('.autopostula-time-preset').forEach(b => {
                            b.style.background = 'rgba(255,255,255,0.08)';
                            b.style.borderColor = 'rgba(255,255,255,0.2)';
                        });
                        btn.style.background = '#0284c7';
                        btn.style.borderColor = '#38bdf8';
                    });
                });
            }

            updateWidgetState();
        }

        window.__ensure_autopostula_widget = createOrAttachWidget;
        createOrAttachWidget();

        if (!window.__autopostula_interval) {
            window.__autopostula_interval = setInterval(createOrAttachWidget, 400);
        }
    })()
    """
    try:
        await page.add_init_script(js_inject)
    except Exception:
        pass
    try:
        await page.evaluate(js_inject)
    except Exception:
        pass


async def comprobar_pausa_y_parada(page) -> str:
    """Verifica si el usuario activó la pausa o la X roja de detención total."""
    estado = await page.evaluate('''() => {
        return {
            stop: window.__autopostula_stop || false,
            paused: window.__autopostula_paused || false
        };
    }''')
    if estado.get("stop"):
        return "stop"

    if estado.get("paused"):
        print("\n⏸️  BOT EN ESTADO PAUSADO por el usuario. Esperando reanudación...")
        hablar("Bot pausado. Esperando que presiones reanudar.")
        while True:
            await asyncio.sleep(0.3)
            st = await page.evaluate('''() => ({
                stop: window.__autopostula_stop || false,
                paused: window.__autopostula_paused || false
            })''')
            if st.get("stop"):
                return "stop"
            if not st.get("paused"):
                print("\n▶️  BOT REANUDADO por el usuario.")
                hablar("Bot reanudado.")
                break
    return "ok"


async def pulsar_primer_postula(page) -> bool:
    """Busca y hace clic en el botón inicial 'Postula fácil' / 'Postularme' / 'Postular'."""
    selectores = [
        "button.btn.primary-btn.blue.aim",
        "button:has-text('Postula fácil')",
        "button:has-text('Postularme')",
        "a:has-text('Postularme')",
        "button.primary-btn:has-text('Postular')",
        "button:has-text('Postular')",
        "a:has-text('Postular')",
        "a:has-text('Postula fácil')",
        "button:has-text('Solicitud sencilla')",
        "a:has-text('Solicitud sencilla')",
        "button.jobs-apply-button",
        "a#btnPostular",
        "#applyOfferSticky",
    ]
    for sel in selectores:
        locs = await page.locator(sel).all()
        for loc in locs:
            try:
                if await loc.is_visible():
                    await loc.scroll_into_view_if_needed()
                    await loc.click()
                    return True
            except Exception:
                pass

    return await page.evaluate('''() => {
        const btns = Array.from(document.querySelectorAll('button, a.btn, a')).filter(el => {
            const txt = (el.innerText || el.textContent || "").trim().toLowerCase();
            return (txt.includes('postula') || txt.includes('postular') || txt.includes('solicitud')) && el.offsetParent !== null;
        });
        if (btns.length > 0) {
            btns[0].scrollIntoView({ block: 'center' });
            btns[0].click();
            return true;
        }
        return false;
    }''')


async def pulsar_comenzar_si_existe(page):
    """Si aparece el modal de Trabajando.cl con 'Comenzar', lo pulsa."""
    await asyncio.sleep(1.2)
    comenzar_locs = await page.locator("button:has-text('Comenzar'), a:has-text('Comenzar')").all()
    for c in comenzar_locs:
        try:
            if await c.is_visible():
                await c.click()
                print("Botón 'Comenzar' pulsado con éxito.")
                await asyncio.sleep(1.0)
                break
        except Exception:
            pass


async def pulsar_segundo_postular(page) -> bool:
    """Pulsa el botón final de envío del formulario ('Postular' / 'Enviar' / 'Enviar mi CV')."""
    selectores_finales = [
        "button#postulation-questions",
        "#form-postulation-questions button[type='submit']",
        "button.submit.submit-auto-width",
        "button.primary-btn:has-text('Postular'):visible",
        "button.w-100.primary-btn",
        "form.formularioPreguntasOferta button:has-text('Postular')",
        ".modal.show button:has-text('Postular')",
        "button:has-text('Enviar postulación')",
        "button:has-text('Confirmar postulación')",
        "#btnKiller",
        "input[type='submit'][value*='Enviar']",
        "button:has-text('Enviar')",
        "button:has-text('Responder')",
        "button.primary-btn",
    ]
    for sel in selectores_finales:
        locs = await page.locator(sel).all()
        for loc in locs:
            try:
                if await loc.is_visible():
                    await loc.evaluate("el => { el.removeAttribute('disabled'); el.classList.remove('boton-deshabilitado'); }")
                    await loc.scroll_into_view_if_needed()
                    await loc.click()
                    return True
            except Exception:
                pass

    return await page.evaluate('''() => {
        const btns = Array.from(document.querySelectorAll('button, a.btn, input[type=\"submit\"]')).filter(b => {
            const t = (b.innerText || b.value || "").trim().toLowerCase();
            return (t === 'postular' || t.includes('postular') || t.includes('enviar') || t.includes('responder')) && b.offsetParent !== null;
        });
        if (btns.length > 0) {
            btns[0].removeAttribute('disabled');
            btns[0].classList.remove('boton-deshabilitado');
            btns[0].click();
            return true;
        }
        return false;
    }''')


async def procesar_oferta_interactiva(page, oferta: dict, segundos_revision: int = 30) -> tuple[str, str]:
    url = oferta.get("url_oferta", "")
    titulo = oferta.get("titulo", "Práctica")
    empresa = oferta.get("empresa", "Empresa")
    portal = oferta.get("portal", "Portal")
    ubicacion = oferta.get("ubicacion", "Santiago, RM")

    print(f"\n========================================================")
    print(f"🎯 [{portal}] {empresa} — {titulo}")
    print(f"📍 Ubicación: {ubicacion}")
    print(f"🔗 URL: {url}")
    print(f"========================================================")

    traer_brave_al_frente()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2.0)
    except Exception as e:
        return "error", f"Fallo al cargar URL: {str(e)[:60]}"

    # Inyectar botón flotante de Pausar/Reanudar y X roja en esquina inferior izquierda
    await inyectar_boton_flotante_control(page)

    # 1. Comprobar si redirigió a un catálogo general o página de búsqueda
    if es_url_catalogo(page.url, portal):
        print(f"⚠️  URL redirigió al catálogo general de ofertas ({page.url}). Oferta expirada.")
        return "cerrada", "La oferta expiró o redirigió al catálogo general de ofertas"

    # Verificar si el usuario pulsó Cerrar o Pausar de inmediato
    st = await comprobar_pausa_y_parada(page)
    if st == "stop":
        return "stop", "Bot detenido por el usuario con la X roja"

    # Comprobar si ya está postulado o cerrada
    body_text = (await page.inner_text("body") or "").lower()
    if any(w in body_text for w in ["ya te has postulado", "ya has postulado", "ya estás postulado", "ya postulaste", "postulación enviada"]):
        return "ya_postulado", "Ya estabas postulado previamente a esta oferta"

    if any(w in body_text for w in FRASES_CERRADA):
        print("⚠️  Detectado mensaje de oferta cerrada o finalizada en el portal.")
        return "cerrada", "Oferta cerrada o expirada en el portal"

    # PASO 1: Pulsar el primer botón 'Postula fácil' / 'Postularme'
    print("Paso 1: Buscando y pulsando botón inicial (Postula fácil)...")
    clic_inicial = await pulsar_primer_postula(page)
    print(f"Resultado clic inicial: {'Exitoso' if clic_inicial else 'No encontrado'}")
    await asyncio.sleep(2.0)

    # Comprobar si tras el clic inicial redirigió a un catálogo
    if es_url_catalogo(page.url, portal):
        print(f"⚠️  El clic inicial redirigió al catálogo general ({page.url}). Oferta cerrada.")
        return "cerrada", "El botón redirigió al catálogo general de ofertas"

    # Comprobar si tras el clic inicial el portal indica que ya estás postulado o cerrada
    body_tras_clic = (await page.inner_text("body") or "").lower()
    if any(w in body_tras_clic for w in ["ya te postulaste", "ya te has postulado", "ya has postulado", "ya estás postulado", "ya postulaste", "postulación enviada"]):
        return "ya_postulado", "Ya estabas postulado previamente a esta oferta (detectado tras clic inicial)"

    if any(w in body_tras_clic for w in FRASES_CERRADA):
        return "cerrada", "Oferta cerrada o expirada en el portal (detectado tras clic inicial)"

    # Verificar parada o pausa tras clic inicial
    st = await comprobar_pausa_y_parada(page)
    if st == "stop":
        return "stop", "Bot detenido por el usuario con la X roja"

    # PASO 2: Si aparece modal con 'Comenzar', pulsarlo
    await pulsar_comenzar_si_existe(page)

    # Si redirigió a KillerQuestions o formulario en Computrabajo
    if "candidate/kq" in page.url or "match" in page.url:
        print("Detectada página de KillerQuestions de Computrabajo.")
        await asyncio.sleep(1.5)

    # Asegurar que el botón flotante persista
    await inyectar_boton_flotante_control(page)

    # Verificar parada o pausa
    st = await comprobar_pausa_y_parada(page)
    if st == "stop":
        return "stop", "Bot detenido por el usuario con la X roja"

    # PASO 3: Detectar y rellenar las preguntas en pantalla con Gemini 3.5 Flash-Lite
    print("Paso 2: Detectando y respondiendo preguntas con Gemini 3.5 Flash-Lite y perfil Duoc UC...")
    
    # Buscar textareas e inputs de texto de preguntas (captura tanto textarea como input[type=text])
    loc_tas = []
    todos_candidatos = await page.locator("form#form-postulation-questions input[type='text']:visible, form#form-postulation-questions textarea:visible, form#formularioPreguntasOferta textarea, div.offcanvas textarea, textarea:visible, input[name*='filter_questions']:visible, input[name*='pregunta']:visible, .form-group input[type='text']:visible, textarea, input[type='text']:visible").all()
    
    seen_elements = set()
    for el in todos_candidatos:
        try:
            if not await el.is_visible():
                continue
            es_valido = await el.evaluate(r'''el => {
                if (el.type === 'search' || el.type === 'hidden' || el.type === 'submit' || el.type === 'radio' || el.type === 'checkbox') return false;
                if (el.closest('header') || el.closest('nav') || el.closest('#navbar') || el.closest('.search-box') || el.closest('#search') || el.closest('.filters') || el.closest('.sidebar') || el.closest('.banner')) return false;
                
                // Si está dentro de un formulario de postulación explícito o su name es filter_questions, ES VÁLIDO DE INMEDIATO
                if (el.closest('#form-postulation-questions') || el.closest('form#formularioPreguntasOferta') || el.closest('.modal') || el.closest('.offcanvas') || el.closest('#formPostular') || el.closest('.kq-container') || (el.name && el.name.startsWith('filter_questions'))) {
                    return true;
                }

                const name = (el.name || "").toLowerCase();
                const id = (el.id || "").toLowerCase();
                const placeholder = (el.placeholder || "").toLowerCase();
                const aria = (el.getAttribute('aria-label') || "").toLowerCase();
                const cls = (el.className || "").toLowerCase();

                // Excluir cualquier input de búsqueda o filtro fuera de postulación
                const blacklist = ['search', 'buscar', 'busqueda', 'filtro', 'title', 'keywords', 'keyword', 'query', 'cargo', 'location', 'ubicacion', 'selectized', 'form_co', 'form_category', 'form_client', 'email_suscribir', 'newsletter'];
                for (let b of blacklist) {
                    if (name === b || id === b || placeholder.includes(b) || aria.includes(b) || cls.includes(b)) {
                        return false;
                    }
                }
                return true;
            }''')
            if es_valido:
                handle_id = await el.evaluate('el => el.name || el.id || el.placeholder || Math.random()')
                if handle_id not in seen_elements:
                    seen_elements.add(handle_id)
                    loc_tas.append(el)
        except Exception:
            pass
    
    preguntas_para_llm = []
    elementos_info = []

    for idx, ta in enumerate(loc_tas):
        try:
            info_pregunta = await ta.evaluate(r'''el => {
                const group = el.closest('.input-style') || el.closest('div[id^="pregunta_"]') || el.closest('.form-group') || el.closest('.mb-3') || el.closest('.b_input') || el.closest('.b_textarea') || el.parentElement;
                let num = '';
                let txt = '';
                if (group) {
                    // 1. Trabajando.cl específico: label.type2
                    const l2 = group.querySelector('label.type2');
                    if (l2 && l2.innerText.trim()) {
                        txt = l2.innerText.trim();
                        const l1 = group.querySelector('label.type1');
                        if (l1) num = l1.innerText.trim();
                    }

                    // 2. FirstJob y otros portales: h6, h5, h4, h3, legend (descartando banners de premium)
                    if (!txt) {
                        const headings = Array.from(group.querySelectorAll('h6, h5, h4, h3, legend, label')).filter(h => {
                            const t = h.innerText.toLowerCase();
                            return !t.includes('premium') && !t.includes('caracteres') && !t.includes('automática') && !t.includes('currículum');
                        });
                        if (headings.length > 0) {
                            txt = headings[0].innerText.trim();
                        }
                    }

                    // 3. Fallback: líneas del contenedor
                    if (!txt) {
                        const lines = group.innerText.split(/\r?\n/).map(s => s.trim()).filter(s => {
                            const sl = s.toLowerCase();
                            return s && !sl.includes('caracteres') && !sl.includes('premium') && !sl.includes('obligatorio') && !sl.includes('automática');
                        });
                        if (lines.length > 0) txt = lines[0];
                    }
                }
                return { num: num, txt: txt };
            }''')

            q_num = info_pregunta.get("num") or f"Pregunta {idx + 1}"
            q_text = info_pregunta.get("txt") or f"Pregunta {idx + 1}"
            preguntas_para_llm.append({"id": idx, "num": q_num, "pregunta": q_text})
            elementos_info.append({"ta": ta, "num": q_num, "pregunta": q_text})
        except Exception as e:
            print(f"Aviso al extraer pregunta {idx}: {e}")

    # Llamar a Gemini 3.5 Flash-Lite para resolver todas las preguntas con razonamiento contextual
    respuestas_llm = {}
    if preguntas_para_llm:
        print(f"🤖 Consultando a Gemini 3.5 Flash-Lite para {len(preguntas_para_llm)} preguntas...")
        respuestas_llm = resolver_preguntas_con_gemini_en_lote(preguntas_para_llm, empresa=empresa, cargo=titulo)

    qa_list = []
    seen = set()

    for idx, item in enumerate(elementos_info):
        try:
            ta = item["ta"]
            q_num = item["num"]
            q_text = item["pregunta"]

            # Comprobar si el campo exige estrictamente números o tiene longitud corta
            info_campo = await ta.evaluate(r'''el => {
                const isNumType = el.type === 'number' || el.inputMode === 'numeric' || (el.getAttribute('pattern') && el.getAttribute('pattern').includes('[0-9]'));
                const group = el.closest('.input-style') || el.closest('div[id^="pregunta_"]') || el.closest('.form-group') || el.closest('.mb-3') || el.parentElement;
                const gText = ((group ? group.innerText : "") + " " + (el.getAttribute('placeholder') || "")).toLowerCase();
                const hasNumNotice = gText.includes('solo acepta números') || gText.includes('solo números') || gText.includes('numérico') || gText.includes('solo dígitos');
                const maxLen = parseInt(el.getAttribute('maxlength') || '9999', 10);
                return {
                    esNumero: isNumType || hasNumNotice || (maxLen <= 11),
                    maxLen: maxLen,
                    tagName: el.tagName.toLowerCase()
                };
            }''')

            es_numero = info_campo.get("esNumero", False)
            max_len = info_campo.get("maxLen", 9999)

            resp = respuestas_llm.get(idx) or resolver_pregunta_reclutador(q_text, empresa, tipo_input="number" if es_numero else "textarea")

            # 1. Regla de Oro: Prohibición absoluta de N/A en motivación o preguntas abiertas
            p_lower = q_text.lower()
            if any(m in p_lower for m in ["motiva", "interés", "interes", "por qué", "por que", "expectativa", "desafío", "desafio"]):
                if not resp or resp.strip().upper() in ["N/A", "NO APLICA", "NINGUNA", "NA", "NO", ""] or len(resp.strip()) < 15:
                    resp = f"Me motiva profundamente realizar mi práctica profesional en {empresa} para aportar con proactividad, disciplina y sólidos conocimientos técnicos en infraestructura, redes y continuidad operacional. Busco aprender de los desafíos reales del equipo, resolver incidentes y agregar valor tangible desde el primer día."

            # 1.5 Regla Administrativa Duoc UC: Consolidar convenio antes del 15 de noviembre (si pregunta inicio/disponibilidad)
            if not es_numero and any(k in p_lower for k in ["disponibilidad", "comenzar", "iniciar", "fecha", "diciembre", "enero", "cuándo", "cuando", "partir"]):
                if "meses" not in p_lower and "seguro" not in p_lower and "15 de noviembre" not in resp.lower():
                    nota_15_nov = " Por cierre administrativo en Duoc UC, requerimos consolidar e inscribir formalmente el convenio antes del 15 de noviembre, ya que después de esa fecha debo pagar un semestre extra adicional para validarla en horario de verano."
                    if (len(resp) + len(nota_15_nov)) <= max_len:
                        resp = resp.rstrip(".") + "." + nota_15_nov

            # 2. Manejo estricto de campos numéricos (ej. WOM Pregunta 2: "¿Cuántas horas de práctica debes realizar?")
            if es_numero:
                perf = obtener_perfil_activo()
                horas_default = str(perf.get("condiciones_practica", {}).get("horas_cronologicas_requeridas", "360")) if perf else "360"
                renta_default = str(perf.get("condiciones_legales_y_renta", {}).get("pretension_renta", "0")) if perf else "0"
                tel_default = re.sub(r'\D', '', perf.get("datos_personales", {}).get("telefono", "56948508528")) if perf else "56948508528"

                if "hora" in p_lower:
                    resp = horas_default
                elif any(k in p_lower for k in ["renta", "pretension", "pretensión", "sueldo", "remuneracion", "remuneración", "monto", "esperada"]):
                    resp = renta_default
                elif any(k in p_lower for k in ["telefono", "teléfono", "celular", "fono"]):
                    resp = tel_default
                else:
                    solo_digitos = re.sub(r'\D', '', resp)
                    resp = solo_digitos if solo_digitos else "0"

            # 3. Ajustar si el campo tiene límite estricto de caracteres (maxlength)
            if max_len and max_len < len(resp):
                resp = resp[:max_len]

            # Tipeo nativo de Playwright sobre el campo para que aparezca en pantalla de inmediato
            await ta.scroll_into_view_if_needed()
            await ta.click()
            await ta.fill(resp)
            await ta.evaluate('''el => {
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }''')

            if q_text not in seen:
                seen.add(q_text)
                qa_list.append({
                    "num": q_num,
                    "pregunta": q_text,
                    "respuesta": resp
                })
            await asyncio.sleep(0.15)
        except Exception as e:
            print(f"Aviso al llenar campo {idx}: {e}")

    # Marcar TODOS los grupos de radios de disponibilidad / seguro / preguntas Si-No
    await page.evaluate('''() => {
        // 1. Agrupar por input[type="radio"] name para responder CADA pregunta individualmente
        const radioNames = new Set();
        document.querySelectorAll('input[type="radio"]').forEach(r => {
            if (r.name) radioNames.add(r.name);
        });

        for (let name of radioNames) {
            const inputs = Array.from(document.querySelectorAll(`input[name="${name}"]`));
            let answered = inputs.some(inp => inp.checked);
            if (answered) continue;

            const container = inputs[0].closest('.form-group') || inputs[0].closest('div[class*="question"]') || inputs[0].closest('fieldset') || inputs[0].parentElement.parentElement;
            const containerText = container ? container.innerText.toLowerCase() : "";
            const isNoExpected = containerText.includes("inclusión") || containerText.includes("ajuste razonable") || containerText.includes("discapacidad");

            let targetInput = null;
            let targetLabel = null;

            for (let inp of inputs) {
                const lbl = inp.closest('label') || inp.parentElement;
                const txt = lbl ? lbl.innerText.trim().toUpperCase() : (inp.value || "").toUpperCase();
                if (isNoExpected) {
                    if (txt === "NO" || txt.startsWith("NO")) {
                        targetInput = inp;
                        targetLabel = lbl;
                        break;
                    }
                } else {
                    if (txt === "SI" || txt === "SÍ" || txt.startsWith("SI ") || txt.startsWith("SÍ ") || txt.includes("SÍ") || txt.includes("SI")) {
                        targetInput = inp;
                        targetLabel = lbl;
                        break;
                    }
                }
            }

            if (!targetInput && !isNoExpected && inputs.length > 0) {
                targetInput = inputs[0];
                targetLabel = targetInput.closest('label') || targetInput.parentElement;
            }

            if (targetInput) {
                targetInput.checked = true;
                if (targetLabel) targetLabel.click();
                targetInput.dispatchEvent(new Event('change', { bubbles: true }));
                targetInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }

        // 2. Para botones/chips y etiquetas personalizadas de FirstJob
        const allContainers = Array.from(document.querySelectorAll('.cb-container, label.radio, .radio-label, .btn-check')).filter(l => {
            const t = l.innerText.trim().toUpperCase();
            return t === 'SI' || t === 'SÍ';
        });
        for (let l of allContainers) {
            const inp = l.querySelector('input[type="radio"]');
            if (inp && !inp.checked) {
                const siblings = Array.from(document.querySelectorAll(`input[name="${inp.name}"]`));
                if (!siblings.some(s => s.checked)) {
                    inp.checked = true;
                    l.click();
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        }

        // 3. Resolver SELECT dropdowns (ej. "¿Posee seguro de práctica?", "¿Disponibilidad?", etc.)
        const selects = Array.from(document.querySelectorAll('form select, .input-style select, select:not([name*="search"])'));
        for (let sel of selects) {
            if (!sel.offsetParent) continue;
            if (sel.value && sel.value !== "") continue;

            const container = sel.closest('.input-style') || sel.closest('.form-group') || sel.parentElement;
            const txt = container ? container.innerText.toLowerCase() : "";
            const options = Array.from(sel.querySelectorAll('option'));

            const isNo = txt.includes("inclusión") || txt.includes("discapacidad") || txt.includes("ajuste razonable");
            let targetOption = null;

            for (let opt of options) {
                const oText = (opt.innerText || opt.textContent || "").trim().toUpperCase();
                if (opt.value === "") continue;

                if (isNo) {
                    if (oText === "NO" || oText.startsWith("NO")) {
                        targetOption = opt;
                        break;
                    }
                } else {
                    if (oText === "SÍ" || oText === "SI" || oText.startsWith("SÍ") || oText.startsWith("SI")) {
                        targetOption = opt;
                        break;
                    }
                }
            }

            if (!targetOption && options.length > 1) {
                for (let opt of options) {
                    if (opt.value && opt.value !== "") {
                        targetOption = opt;
                        break;
                    }
                }
            }

            if (targetOption) {
                sel.value = targetOption.value;
                sel.dispatchEvent(new Event('change', { bubbles: true }));
                sel.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
    }''')

    # Habilitar el segundo botón 'Postular'
    await page.evaluate('''() => {
        const btns = Array.from(document.querySelectorAll('button, input[type="submit"]')).filter(b => {
            const t = (b.innerText || b.value || "").toLowerCase();
            return t.includes('postular') || t.includes('enviar') || t.includes('responder') || t.includes('continuar');
        });
        for (let b of btns) {
            b.removeAttribute('disabled');
            b.classList.remove('boton-deshabilitado');
        }
    }''')

    # Instalar detector de clic manual del usuario
    await page.evaluate('''() => {
        window.__usuario_envio_postulacion = false;
        const btns = Array.from(document.querySelectorAll('button, a.btn, input[type="submit"]')).filter(b => {
            const t = (b.innerText || b.value || "").toLowerCase();
            return (t === 'postular' || t.includes('postular') || t.includes('enviar') || t.includes('responder') || t === 'enviar mi cv') && b.offsetParent !== null;
        });
        for (let b of btns) {
            b.addEventListener('click', () => {
                window.__usuario_envio_postulacion = true;
            });
        }
    }''')

    # Verificar parada o pausa antes de narrar
    st = await comprobar_pausa_y_parada(page)
    if st == "stop":
        return "stop", "Bot detenido por el usuario con la X roja"

    # PASO 4: LEER EN VOZ ALTA CADA PREGUNTA Y SU RESPUESTA CON DI
    traer_brave_al_frente()
    if qa_list:
        hablar(f"El reclutador de {empresa} solicita responder {len(qa_list)} preguntas.")
        for item in qa_list:
            # Comprobar si el usuario pausó o detuvo entre lecturas
            st = await comprobar_pausa_y_parada(page)
            if st == "stop":
                return "stop", "Bot detenido por el usuario con la X roja"

            q_clean = item['pregunta']
            r_full = item['respuesta']
            # Locución concisa y clara
            r_resumen = r_full.split('.')[0] if '.' in r_full else r_full[:80]
            print(f"📢 {item['num']}: {q_clean}")
            print(f"   ↳ {r_resumen}\n")
            hablar(f"{item['num']}: {q_clean}.")
            hablar(f"Respuesta: {r_resumen}.")
    else:
        hablar(f"Formulario sin preguntas adicionales para {empresa}.")

    # PASO 5: RECIÉN AQUÍ COMIENZAN LOS 30 SEGUNDOS DE PAUSA DE REVISIÓN
    msg_pausa = f"Respuestas listas en pantalla. Tienes {segundos_revision} segundos para revisar. Puedes pausar con el botón flotante inferior izquierdo o cerrarlo con la X roja."
    print(f"\n📢 {msg_pausa}")
    hablar(msg_pausa)

    print(f"⏳ Pausa de revisión activa ({segundos_revision}s). [Botón flotante en esquina inferior izquierda para Pausar / X roja para Cerrar]...")
    
    tiempo_transcurrido = 0.0
    esta_pausado_prev = False
    clic_manual = False

    while tiempo_transcurrido < segundos_revision:
        estado_control = await page.evaluate('''() => {
            return {
                stop: window.__autopostula_stop || false,
                paused: window.__autopostula_paused || false,
                skipWait: window.__autopostula_skip_wait || false,
                customSeconds: window.__autopostula_segundos_revision || null,
                clickedManual: window.__usuario_envio_postulacion || false,
                success: document.body.innerText.toLowerCase().includes('éxito') || document.body.innerText.toLowerCase().includes('postulado')
            };
        }''')

        if estado_control.get("stop"):
            print(f"\n🛑 ¡Detectado clic en la X roja! Detención total solicitada por el usuario.")
            return "stop", "Bot detenido por el usuario con la X roja"

        if estado_control.get("clickedManual") or estado_control.get("success"):
            clic_manual = True
            print(f"\n👆 ¡Detectado clic manual del usuario o confirmación anticipada!")
            break

        if estado_control.get("skipWait"):
            print(f"\n🚀 ¡Pulsado 'Enviar Postulación Ahora' desde la ventanita! Omitiendo espera restante...")
            break

        nuevo_seg = estado_control.get("customSeconds")
        if nuevo_seg and nuevo_seg != segundos_revision:
            segundos_revision = nuevo_seg
            print(f"\n⚙️  Tiempo de revisión actualizado dinámicamente a {segundos_revision}s.")

        if estado_control.get("paused"):
            if not esta_pausado_prev:
                print(f"\n⏸️  BOT PAUSADO por el usuario desde el botón flotante.")
                hablar("Bot pausado. Tómate el tiempo necesario para revisar o editar.")
                esta_pausado_prev = True
                await page.evaluate('''() => {
                    window.__autopostula_timer_text = 'PAUSA';
                    const pt = document.getElementById('autopostula-pill-timer');
                    if (pt) { pt.innerText = 'PAUSA'; pt.style.background = '#d97706'; }
                    const mt = document.getElementById('autopostula-modal-timer');
                    if (mt) { mt.innerText = 'PAUSA'; mt.style.background = '#d97706'; }
                }''')
            await asyncio.sleep(0.5)
            continue
        else:
            if esta_pausado_prev:
                print(f"\n▶️  BOT REANUDADO por el usuario.")
                hablar("Bot reanudado.")
                esta_pausado_prev = False
                await page.evaluate('''() => {
                    const pt = document.getElementById('autopostula-pill-timer');
                    if (pt) { pt.style.background = '#0284c7'; }
                    const mt = document.getElementById('autopostula-modal-timer');
                    if (mt) { mt.style.background = '#0284c7'; }
                }''')

            restante = max(0, int(segundos_revision - tiempo_transcurrido))
            # Actualizar timer en botón flotante y ventanita
            await page.evaluate(f'''() => {{
                window.__autopostula_timer_text = '{restante}s';
                const pt = document.getElementById('autopostula-pill-timer');
                if (pt) pt.innerText = '{restante}s';
                const mt = document.getElementById('autopostula-modal-timer');
                if (mt) mt.innerText = '{restante}s';
                const t = document.getElementById('autopostula-timer');
                if (t) t.innerText = '{restante}s';
            }}''')

            print(f"\r⏱️  Revisión: {restante:02d}s restantes | [⏸️ Pausar | ⚙️ Ventanita | ❌ Cerrar]...", end="", flush=True)
            await asyncio.sleep(0.5)
            tiempo_transcurrido += 0.5

    print("")

    # Comprobar parada final antes del envío
    st = await comprobar_pausa_y_parada(page)
    if st == "stop":
        return "stop", "Bot detenido por el usuario con la X roja"

    # PASO 6: Pulsar el SEGUNDO 'Postular' si no hubo clic manual
    if not clic_manual:
        print(f"⏰ Tiempo de revisión cumplido ({segundos_revision}s). Pulsando el segundo botón Postular...")
        hablar("Tiempo cumplido. Enviando postulación.")
        res_envio = await pulsar_segundo_postular(page)
        print(f"Resultado clic segundo Postular: {res_envio}")
        await asyncio.sleep(3.5)
    else:
        await asyncio.sleep(2.5)

    # PASO 7: Comprobar confirmación final de éxito con espera de AJAX y verificación visual
    es_exito = False
    motivo_exito = ""

    for intento in range(8):
        await asyncio.sleep(1.0)
        body_final = (await page.inner_text("body") or "").lower()
        url_final = page.url.lower()

        palabras_exito = [
            "éxito", "recibida", "postulado", "gracias", "felicitaciones",
            "postulación enviada", "tu candidatura", "inscrita", "ya te has postulado",
            "en proceso", "postular de nuevo", "ya has postulado", "ya estás postulado",
            "solicitud enviada", "postulación completada", "candidatura enviada",
            "ya postulaste", "has postulado", "tu postulación fue recibida", "enviada correctamente"
        ]

        if any(w in body_final for w in palabras_exito) or ("mis-postulaciones" in url_final) or ("match" in url_final):
            es_exito = True
            motivo_exito = "Texto explícito o URL de éxito detectada"
            break

        # En Laborum, el botón cambia de 'Postularme' a 'Ver estadísticas'
        try:
            ver_stats = await page.locator("button:has-text('Ver estadísticas'), a:has-text('Ver estadísticas')").count()
            if ver_stats > 0:
                es_exito = True
                motivo_exito = "Botón 'Ver estadísticas' activo en Laborum"
                break
        except Exception:
            pass

        # Si hubo formulario de preguntas (modal) y se cerró tras el clic de envío
        if qa_list:
            modal_abierto = await page.evaluate('''() => {
                const form = document.querySelector("form#formularioPreguntasOferta") || document.querySelector(".modal.show") || document.querySelector(".offcanvas.show");
                return form && form.offsetParent !== null;
            }''')
            if modal_abierto is False:
                es_exito = True
                motivo_exito = "Modal de preguntas completado y cerrado exitosamente"
                break

    if es_exito:
        print(f"\n========================================================")
        print(f"✅ ¡POSTULACIÓN CONFIRMADA VISIBLE EN PANTALLA!")
        print(f"🎯 Empresa: {empresa} | Portal: {portal}")
        print(f"📋 Validación: {motivo_exito}")
        print(f"👁️  Manteniendo pantalla visible 4 segundos para que verifiques el éxito...")
        print(f"========================================================\n")
        hablar(f"Postulación a {empresa} confirmada con éxito en pantalla.")
        await asyncio.sleep(4.0)
        return "ok", f"Postulación confirmada con éxito en {portal} ({motivo_exito} | {len(qa_list)} preguntas respondidas)"
    else:
        print(f"\n⚠️  Aviso: No se detectó confirmación explícita de postulación en {portal}. Se marcará para revisión.")
        return "revision", f"Revisar estado en {portal} (no se detectó confirmación explícita tras envío)"


async def ejecutar_bucle(segundos_revision: int = 30, max_ofertas: int = 100, solo_id: int = None):
    ofertas = obtener_ofertas_validas_pendientes(limite=max_ofertas, solo_id=solo_id)
    total = len(ofertas)

    if total == 0:
        print("✅ No hay ofertas de práctica técnica pendientes en la Región Metropolitana.")
        hablar("No hay más ofertas pendientes en la Región Metropolitana.", final=True)
        return

    print("==========================================================")
    print(f"🚀 INICIANDO BUCLE DE POSTULACIÓN EN PANTALLA (REGIÓN METROPOLITANA)")
    print(f"📋 Total ofertas técnicas RM en cola: {total}")
    print(f"⏱️  Pausa de revisión tras lectura: {segundos_revision} segundos")
    print(f"🔘 Botón flotante interactivo: Esquina inferior izquierda (Pausar/Reanudar)")
    print(f"🖥️  Navegador: Brave Browser en puerto 9222 (CDP)")
    print("==========================================================")

    hablar(f"Iniciando bucle para {total} ofertas de la Región Metropolitana. Dispones del botón flotante en la esquina inferior izquierda para pausar y reanudar.")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            ctx = browser.contexts[0]
        except Exception as e:
            print(f"❌ Error conectando a Brave: {e}")
            hablar("Error conectando con Brave en puerto 9222.", final=True)
            return

        exitosas = 0
        cerradas = 0

        for i, of in enumerate(ofertas, 1):
            of_id = of["id"]
            titulo = of["titulo"][:45]
            empresa = of["empresa"][:25]
            portal = of["portal"]

            print(f"\n>>> [{i}/{total}] Procesando oferta #{of_id}: {empresa} - {titulo} ({portal})")
            page = await ctx.new_page()

            try:
                res_tipo, msg = await procesar_oferta_interactiva(page, of, segundos_revision=segundos_revision)
            except Exception as e:
                res_tipo, msg = "error", f"Error en oferta: {str(e)[:60]}"

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            if res_tipo == "stop":
                print("\n🛑 Bucle detenido por completo por el usuario (X roja pulsada).")
                hablar("Bot detenido por completo a solicitud del usuario.", final=True)
                c.execute("UPDATE postulaciones SET notas = ? WHERE id = ?", (f"[Detenido por usuario] {msg}", of_id))
                conn.commit()
                conn.close()
                try:
                    await page.close()
                except Exception:
                    pass
                return

            if res_tipo in ["ok", "ya_postulado"]:
                nuevo_estado = "🟢 Postulado Confirmado"
                exitosas += 1
                c.execute(
                    "UPDATE postulaciones SET estado = ?, fecha_postulacion = ?, metodo_postulacion = 'brave_cdp_pantalla', notas = ? WHERE id = ?",
                    (nuevo_estado, now_str, f"[CV Maestro Duoc] {msg}", of_id)
                )
                conn.commit()
                hablar(f"Postulación a {empresa} confirmada con éxito visible en pantalla.")
                print(f"👁️ Manteniendo pantalla visible 5 segundos antes de avanzar...")
                await asyncio.sleep(5.0)
                try:
                    await page.close()
                except Exception:
                    pass
            elif res_tipo == "cerrada":
                nuevo_estado = "🔴 Oferta Cerrada / Expirada"
                cerradas += 1
                c.execute("UPDATE postulaciones SET estado = ?, notas = ? WHERE id = ?", (nuevo_estado, msg, of_id))
                conn.commit()
                hablar(f"La oferta de {empresa} está cerrada. Pasando a la siguiente.")
                try:
                    await page.close()
                except Exception:
                    pass
            else:
                c.execute("UPDATE postulaciones SET notas = ? WHERE id = ?", (f"[Revisión en pantalla] {msg}", of_id))
                conn.commit()
                print(f"⚠️  Oferta #{of_id} no confirmó envío automático. MANTENIENDO PESTAÑA ABIERTA PARA EL USUARIO.")
                hablar(f"Oferta de {empresa} en pantalla para revisión manual. No se cerrará la pestaña.")
                await asyncio.sleep(3.0)
                # NO cerrar la pestaña: se deja abierta para inspección del usuario

            conn.close()
            await asyncio.sleep(2.5)

    print("\n==========================================================")
    print(f"🎯 Bucle finalizado: {exitosas} confirmadas | {cerradas} cerradas de {total} procesadas.")
    print("==========================================================")
    hablar(f"Bucle de la Región Metropolitana finalizado. {exitosas} postulaciones confirmadas.", final=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutoPostula — Bucle Interactivo en Pantalla (RM)")
    parser.add_argument("--segundos", type=int, default=30, help="Segundos de revisión tras leer las respuestas (ej. 30 a 60, o 0 para envío inmediato)")
    parser.add_argument("--max", type=int, default=100, help="Máximo de ofertas a procesar en el bucle")
    parser.add_argument("--id", type=int, default=None, help="Procesar una sola oferta específica por su ID")
    parser.add_argument("--no-focus", action="store_true", help="No enfocar la ventana de Brave (modo silencioso / segundo plano)")
    parser.add_argument("--sin-voz", action="store_true", help="No narrar con Di por voz")
    args = parser.parse_args()

    if args.no_focus:
        GLOBAL_ENFOCAR = False
    if args.sin_voz:
        GLOBAL_CON_VOZ = False

    asyncio.run(ejecutar_bucle(segundos_revision=args.segundos, max_ofertas=args.max, solo_id=args.id))
