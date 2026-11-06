#!/usr/bin/env python3
"""
AutoPostula · Centro de Comando NOC & Multi-Buscador (14 Portales Reales Chile)
Puerto: 8087
Soporta tanto Prácticas Profesionales Duoc UC (Ingeniería en Infraestructura y Plataformas Tecnológicas · 360h)
como cualquier pega / empleo formal TI en Chile.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 8087
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database import (
    PORTALES_SOPORTADOS,
    actualizar_estado_postulacion,
    get_conn,
    guardar_estado_scheduler,
    guardar_filtros,
    init_db,
    obtener_alertas_pendientes,
    obtener_catalogo_portales,
    obtener_estado_scheduler,
    obtener_filtros,
    obtener_logs_scheduler,
    obtener_perfil,
    obtener_postulaciones,
)
from daemon_scheduler import calcular_proximo_horario
from modules.auto_applier import (
    abrir_sesion_persistente_portales,
    generar_bookmarklet_universal,
    generar_mailto_postulacion,
)

DAEMON_SCRIPT = os.path.join(BASE_DIR, "daemon_scheduler.py")
PYTHON_BIN = sys.executable or "/usr/bin/python3"


def is_daemon_running():
    try:
        out = subprocess.check_output(["pgrep", "-f", "AutoPostula/daemon_scheduler.py"]).decode().strip()
        pids = [int(p) for p in out.splitlines() if p.strip()]
        return (len(pids) > 0), (pids[0] if pids else None)
    except Exception:
        return False, None


def get_stats():
    init_db()
    active, pid = is_daemon_running()
    sched = obtener_estado_scheduler()
    filtros = obtener_filtros()
    perfil = obtener_perfil()
    alertas = obtener_alertas_pendientes()
    catalogo = obtener_catalogo_portales()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM postulaciones;")
    total = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM postulaciones WHERE estado LIKE '%Postulado%' OR estado LIKE '%Confirmado%' OR estado LIKE '%entrevista%' OR estado LIKE '%Oferta%';")
    enviadas_abiertas = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM postulaciones WHERE estado LIKE '%Cola%';")
    en_cola = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM postulaciones WHERE email_reclutador IS NOT NULL AND TRIM(email_reclutador) != '';")
    con_email = cur.fetchone()[0] or 0

    cur.execute("SELECT portal, COUNT(*) AS cnt FROM postulaciones GROUP BY portal ORDER BY cnt DESC;")
    por_portal = {r["portal"]: r["cnt"] for r in cur.fetchall()}
    conn.close()

    return {
        "daemon_active": active,
        "daemon_pid": pid,
        "scheduler_enabled": int(sched.get("activo") or 0) == 1,
        "proximo_horario": sched.get("proximo_escaneo") or "Pendiente",
        "ultimo_escaneo": sched.get("ultimo_escaneo") or "Reciente",
        "horarios_config": sched.get("horarios") or "01:00, 04:00, 06:30, 08:00, 12:00, 14:00, 17:00, 22:00",
        "total_postulaciones": total,
        "postuladas_activas": enviadas_abiertas,
        "en_cola_1clic": en_cola,
        "con_email_directo": con_email,
        "alertas_pendientes": len(alertas),
        "portales_integrados": len(catalogo),
        "modo_busqueda": filtros.get("modo_busqueda", "practica_duoc"),
        "termino_personalizado": filtros.get("termino_personalizado", "infraestructura plataformas soporte redes cloud"),
        "carrera": perfil.get("carrera", "Ingeniería en Infraestructura y Plataformas Tecnológicas"),
        "candidato": perfil.get("nombre", "Dhani Amit Elgueta Ríos"),
        "horas_duoc": perfil.get("horas_requeridas", 360),
        "conteo_postulaciones_portal": por_portal,
        "bookmarklet": generar_bookmarklet_universal(perfil),
    }


def serialize_postulaciones(filtro_estado="Todos", filtro_portal="Todos", search_q="", limit=200):
    init_db()
    perfil = obtener_perfil()
    rows = obtener_postulaciones(filtro_estado=filtro_estado, filtro_portal=filtro_portal)
    q = (search_q or "").strip().lower()
    out = []
    for r in rows:
        if q:
            blob = f"{r.get('titulo','')} {r.get('empresa','')} {r.get('portal','')} {r.get('ubicacion','')}".lower()
            if q not in blob:
                continue
        r_copy = dict(r)
        r_copy["mailto_url"] = generar_mailto_postulacion(r_copy, perfil) if r_copy.get("email_reclutador") else ""
        out.append(r_copy)
        if len(out) >= limit:
            break
    return out


HTML_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AutoPostula NOC · 14 Portales Chile · Duoc UC & Empleos TI</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #090D16;
            --bg-surface: #0F172A;
            --bg-elevated: #162033;
            --bg-row-sticky: #0F172A;
            --border-subtle: rgba(255, 255, 255, 0.09);
            --border-strong: rgba(56, 189, 248, 0.32);
            --text-main: #F8FAFC;
            --text-secondary: #CBD5E1;
            --text-muted: #94A3B8;
            --accent-emerald: #10B981;
            --accent-sky: #38BDF8;
            --accent-indigo: #6366F1;
            --accent-amber: #F59E0B;
            --accent-rose: #F43F5E;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background-color: var(--bg-base);
            background-image:
                radial-gradient(circle at 12% 10%, rgba(16, 185, 129, 0.09), transparent 40%),
                radial-gradient(circle at 88% 12%, rgba(56, 189, 248, 0.08), transparent 42%);
            color: var(--text-main);
            font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
            min-height: 100vh;
            padding: 20px 24px 48px;
            line-height: 1.45;
        }

        .shell {
            max-width: 1440px;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        header.topbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            padding: 18px 22px;
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid var(--border-subtle);
            border-radius: 16px;
            backdrop-filter: blur(12px);
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .logo-badge {
            width: 46px;
            height: 46px;
            border-radius: 12px;
            background: linear-gradient(135deg, var(--accent-emerald), #0284C7);
            display: grid;
            place-items: center;
            font-size: 22px;
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.28);
        }
        .brand h1 {
            font-size: 1.32rem;
            font-weight: 800;
            letter-spacing: -0.02em;
        }
        .brand p {
            font-size: 0.82rem;
            color: var(--text-muted);
        }

        .top-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
        }

        button, .btn-link {
            font-family: inherit;
            font-size: 0.82rem;
            font-weight: 700;
            border-radius: 10px;
            padding: 9px 14px;
            cursor: pointer;
            border: 1px solid var(--border-subtle);
            background: var(--bg-elevated);
            color: var(--text-main);
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 7px;
            transition: background 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
        }
        button:hover, .btn-link:hover {
            background: #1E293B;
            border-color: var(--border-strong);
            transform: translateY(-1px);
        }
        .btn-emerald {
            background: linear-gradient(135deg, #10B981, #059669);
            border-color: rgba(16, 185, 129, 0.5);
            color: #FFFFFF;
        }
        .btn-sky {
            background: linear-gradient(135deg, #0284C7, #2563EB);
            border-color: rgba(56, 189, 248, 0.5);
            color: #FFFFFF;
        }
        .btn-sm {
            padding: 5px 10px;
            font-size: 0.75rem;
            border-radius: 8px;
        }

        /* Bento KPI Strip */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(205px, 1fr));
            gap: 14px;
        }
        .kpi-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 14px;
            padding: 16px 18px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .kpi-label {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-muted);
        }
        .kpi-val {
            font-family: 'JetBrains Mono', monospace;
            font-variant-numeric: tabular-nums;
            font-size: 1.65rem;
            font-weight: 800;
            color: var(--text-main);
        }
        .kpi-sub {
            font-size: 0.78rem;
            color: var(--text-muted);
        }

        /* Duoc UC Compliance & Mode Control Bar */
        .control-grid {
            display: grid;
            grid-template-columns: 1.35fr 1fr;
            gap: 16px;
        }
        @media (max-width: 1024px) {
            .control-grid { grid-template-columns: 1fr; }
        }

        .panel {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 16px;
            padding: 18px 20px;
        }

        /* Optimization for complex multi-column layout regions (modern-web-guidance: interactions-in-complex-layouts) */
        .board-column {
            content-visibility: auto;
            contain-intrinsic-size: auto 340px auto 680px;
        }
        @supports not (content-visibility: auto) {
            .board-column {
                contain: layout style paint;
            }
        }

        .panel-title {
            font-size: 0.98rem;
            font-weight: 800;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1.3fr auto;
            gap: 10px;
            align-items: end;
        }
        @media (max-width: 780px) {
            .form-row { grid-template-columns: 1fr; }
        }
        label.field-label {
            display: block;
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-muted);
            margin-bottom: 5px;
        }
        select, input[type="text"], input[type="search"] {
            width: 100%;
            background: #090D16;
            color: var(--text-main);
            border: 1px solid var(--border-subtle);
            border-radius: 9px;
            padding: 9px 12px;
            font-family: inherit;
            font-size: 0.84rem;
        }
        select:focus, input:focus {
            outline: 2px solid var(--accent-sky);
            border-color: transparent;
        }

        .duoc-checklist {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 8px;
            margin-top: 8px;
        }
        .check-pill {
            background: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.25);
            border-radius: 10px;
            padding: 8px 11px;
            font-size: 0.78rem;
            color: #D1FAE5;
        }

        /* 14 Portals NOC Grid */
        .portals-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(235px, 1fr));
            gap: 10px;
        }
        .portal-card {
            background: #0B111E;
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 12px 14px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .portal-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
        }
        .portal-name {
            font-weight: 700;
            font-size: 0.86rem;
            color: #F1F5F9;
        }
        .dot-live {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent-emerald);
            box-shadow: 0 0 8px var(--accent-emerald);
            display: inline-block;
        }
        .portal-meta {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.71rem;
            color: var(--accent-sky);
        }
        .portal-notes {
            font-size: 0.74rem;
            color: var(--text-muted);
        }

        /* Responsive Sticky + Container-Queried Stacked Table (modern-web-guidance: responsive-table) */
        .table-toolbar {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        .table-filters {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
        }

        .table-wrapper {
            overflow: auto;
            max-inline-size: 100%;
            max-block-size: min(640px, 78vh);
            container-type: inline-size;
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            background: #0B111E;
        }
        .table-wrapper:focus-visible {
            outline: 2px solid var(--accent-sky);
        }

        table.offers-table {
            border-collapse: separate;
            border-spacing: 0;
            width: 100%;
            font-size: 0.83rem;
            --label-2: "Portal";
            --label-3: "Empresa y Ubicación";
            --label-4: "Afinidad Duoc";
            --label-5: "Estado";
            --label-6: "Acciones 1-Clic";
        }
        caption.sr-caption {
            text-align: left;
            padding: 10px 14px;
            font-size: 0.78rem;
            color: var(--text-muted);
            background: #090D16;
            border-bottom: 1px solid var(--border-subtle);
        }

        table.offers-table thead {
            position: sticky;
            inset-block-start: 0;
            z-index: 2;
        }
        table.offers-table thead th {
            background: #131C31;
            color: #94A3B8;
            font-size: 0.73rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 12px 14px;
            text-align: left;
            border-bottom: 1px solid var(--border-subtle);
            white-space: nowrap;
        }

        table.offers-table tbody th {
            position: sticky;
            inset-inline-start: 0;
            z-index: 1;
            background: var(--bg-row-sticky);
            color: #F8FAFC;
            font-weight: 700;
            text-align: left;
            padding: 12px 14px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            min-width: 230px;
            max-width: 330px;
        }
        table.offers-table tbody td {
            padding: 12px 14px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            color: var(--text-secondary);
            vertical-align: middle;
        }
        table.offers-table tbody tr:hover th,
        table.offers-table tbody tr:hover td {
            background: #162238;
        }

        @container (width < 600px) {
            table.offers-table,
            table.offers-table thead,
            table.offers-table tbody,
            table.offers-table tr,
            table.offers-table th,
            table.offers-table td {
                display: block;
            }
            table.offers-table thead {
                /* MANDATORY: Hide column header from layout and screen readers. */
                display: none;
            }
            table.offers-table tr {
                margin-block-end: 1.25rem;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 10px;
            }
            table.offers-table tbody th {
                position: sticky;
                inset-block-start: 0;
                z-index: 2;
                background: #1E293B;
                max-width: none;
            }
            table.offers-table td:nth-child(2)::before {
                content: var(--label-2) ": ";
                font-weight: 700;
                color: var(--text-muted);
            }
            table.offers-table td:nth-child(3)::before {
                content: var(--label-3) ": ";
                font-weight: 700;
                color: var(--text-muted);
            }
            table.offers-table td:nth-child(4)::before {
                content: var(--label-4) ": ";
                font-weight: 700;
                color: var(--text-muted);
            }
            table.offers-table td:nth-child(5)::before {
                content: var(--label-5) ": ";
                font-weight: 700;
                color: var(--text-muted);
            }
            table.offers-table td:nth-child(6)::before {
                content: var(--label-6) ": ";
                font-weight: 700;
                color: var(--text-muted);
            }
        }

        .badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 3px 9px;
            border-radius: 999px;
            font-size: 0.73rem;
            font-weight: 700;
            white-space: nowrap;
        }
        .badge-portal {
            background: rgba(56, 189, 248, 0.14);
            color: #7DD3FC;
            border: 1px solid rgba(56, 189, 248, 0.3);
        }
        .badge-score {
            font-family: 'JetBrains Mono', monospace;
            background: rgba(16, 185, 129, 0.15);
            color: #6EE7B7;
            border: 1px solid rgba(16, 185, 129, 0.35);
        }

        .actions-cell {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            align-items: center;
        }

        .logs-box {
            background: #070A12;
            border: 1px solid var(--border-subtle);
            border-radius: 12px;
            padding: 12px 14px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.77rem;
            max-height: 230px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        /* Light-dismiss Modal Dialogs (modern-web-guidance: light-dismiss-a-dialog) */
        dialog {
            margin: auto;
            width: min(680px, 92vw);
            background: #0F172A;
            color: var(--text-main);
            border: 1px solid var(--border-strong);
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.65);
        }
        dialog::backdrop {
            background-color: rgba(2, 6, 23, 0.72);
            backdrop-filter: blur(4px);
        }
        .qa-item {
            background: #090D16;
            border: 1px solid var(--border-subtle);
            border-radius: 10px;
            padding: 12px;
            margin-top: 10px;
        }
        .qa-q {
            font-size: 0.8rem;
            font-weight: 700;
            color: var(--accent-sky);
            margin-bottom: 5px;
        }
        .qa-a {
            font-size: 0.83rem;
            color: var(--text-secondary);
            white-space: pre-wrap;
        }

        #toast {
            position: fixed;
            bottom: 22px;
            right: 22px;
            background: #10B981;
            color: #042F2E;
            font-weight: 800;
            font-size: 0.84rem;
            padding: 12px 18px;
            border-radius: 12px;
            box-shadow: 0 12px 30px rgba(0,0,0,0.45);
            display: none;
            z-index: 50;
        }
    </style>
</head>
<body>
<div class="shell">
    <header class="topbar">
        <div class="brand">
            <div class="logo-badge">🎯</div>
            <div>
                <h1>AutoPostula NOC · 14 Portales Reales de Chile</h1>
                <p id="subtitle-carrera">Ingeniería en Infraestructura y Plataformas Tecnológicas · Duoc UC (360h) &amp; Empleos TI</p>
            </div>
        </div>
        <div class="top-actions">
            <button class="btn-emerald" onclick="startInteractiveLoop()" style="background: linear-gradient(135deg, #0284c7, #2563eb); border: none; font-weight:800;" title="Ejecuta el bucle de postulación sobre pantalla con Brave, lectura por voz y widget flotante de 30s">🤖 Bucle en Pantalla (30s)</button>
            <button class="btn-emerald" onclick="startHeadlessBatch()" style="background: linear-gradient(135deg, #059669, #10b981); border: none; font-weight:800;" title="Postula automáticamente a todas las ofertas válidas en segundo plano sin pausar">⚡ Postular Todas (Segundo Plano)</button>
            <button class="btn-danger" onclick="stopBotProcess()" style="background: #ef4444; color: white; border: none; font-weight:800; border-radius:8px; padding:6px 12px; cursor:pointer;" title="Detiene cualquier proceso activo del bot de pantalla">🛑 Detener Bot</button>
            <button class="btn-emerald" onclick="openNextBatch()">🚀 Abrir Lote 10 en Brave</button>
            <button class="btn-sky" onclick="triggerManualScan()">🌐 Escanear 14 Portales Ahora</button>
            <button onclick="openPersistentSession()">🔐 Sesión Persistente</button>
            <button onclick="openBookmarkletModal()">⚡ Bookmarklet</button>
            <a class="btn-link" href="http://localhost:8503" target="_blank" rel="noopener">📊 Streamlit (:8503)</a>
        </div>
    </header>

    <section class="kpi-grid">
        <div class="kpi-card">
            <span class="kpi-label">Portales Reales Activos</span>
            <span class="kpi-val" id="kpi-portales">14</span>
            <span class="kpi-sub">API JSON + SSR + Playwright Brave</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-label">Total Ofertas Procesadas IA</span>
            <span class="kpi-val" id="kpi-total">0</span>
            <span class="kpi-sub" id="kpi-email-sub">0 con correo directo reclutador</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-label">Abiertas / Confirmadas</span>
            <span class="kpi-val" id="kpi-activas" style="color:#34D399">0</span>
            <span class="kpi-sub">Listas o enviadas en navegador</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-label">En Cola 1-Clic (Respuestas IA)</span>
            <span class="kpi-val" id="kpi-cola" style="color:#38BDF8">0</span>
            <span class="kpi-sub">Usa «Abrir Lote 10» para despachar</span>
        </div>
        <div class="kpi-card">
            <span class="kpi-label">Piloto Automático 24/7</span>
            <span class="kpi-val" id="kpi-daemon" style="font-size:1.15rem">Verificando...</span>
            <span class="kpi-sub" id="kpi-proximo">Próximo: --</span>
        </div>
    </section>

    <section class="control-grid">
        <div class="panel board-column">
            <div class="panel-title">
                <span>⚙️ Modo Universal: Práctica Duoc UC o Cualquier Pega / Empleo</span>
                <button class="btn-sm" onclick="toggleScheduler()" id="btn-toggle-sched">⏱️ Alternar Piloto 24/7</button>
            </div>
            <div class="form-row">
                <div>
                    <label class="field-label" for="modo-select">Objetivo de Búsqueda y Postulación</label>
                    <select id="modo-select">
                        <option value="practica_duoc">🎓 Solo Práctica Profesional Duoc UC (Ing. Infraestructura · 360h)</option>
                        <option value="empleo_ti">💼 Cualquier Pega / Empleo TI Regular</option>
                        <option value="ambos">🌐 Ambos (Prácticas Profesionales + Empleos TI)</option>
                    </select>
                </div>
                <div>
                    <label class="field-label" for="termino-input">Especialidad / Cargo a Buscar en los 14 Portales</label>
                    <input type="text" id="termino-input" value="infraestructura plataformas soporte redes cloud" placeholder="Ej: infraestructura cloud redes linux devops soporte">
                </div>
                <div>
                    <button class="btn-emerald" onclick="saveFiltersAndScan()">💾 Guardar &amp; Escanear</button>
                </div>
            </div>
            <div class="duoc-checklist">
                <div class="check-pill">✅ <strong>Carrera:</strong> Ing. en Infraestructura y Plataformas Tecnológicas</div>
                <div class="check-pill">✅ <strong>Duración Oficial:</strong> 360 horas cronológicas mínimas</div>
                <div class="check-pill">✅ <strong>Cobertura:</strong> Seguro Escolar Duoc UC Ley 16.744</div>
                <div class="check-pill">✅ <strong>Horario:</strong> Diurno inmediato (estudio vespertino A. Varas)</div>
            </div>
        </div>

        <div class="panel board-column">
            <div class="panel-title">
                <span>📜 Registro en Vivo del Motor Multi-Portal</span>
                <span style="font-size:0.75rem; color:var(--text-muted)">8 ventanas horarias diarias</span>
            </div>
            <div class="logs-box" id="logs-container">
                <span>Cargando actividad del motor...</span>
            </div>
        </div>
    </section>

    <section class="panel board-column">
        <div class="panel-title">
            <span>📡 Radar Técnico de los 14 Portales Conectados en Chile</span>
            <span style="font-size:0.78rem; color:var(--text-muted)">Selectores DOM, APIs públicas y sesiones mapeadas</span>
        </div>
        <div class="portals-grid" id="portals-grid"></div>
    </section>

    <section class="panel board-column">
        <div class="table-toolbar">
            <div class="panel-title" style="margin-bottom:0">
                <span>📋 Cola Activa e Historial de Postulaciones</span>
            </div>
            <div class="table-filters">
                <input type="search" id="search-offers" placeholder="Buscar empresa, cargo, nube, redes..." oninput="loadPostulaciones()" style="width:230px">
                <select id="filter-portal" onchange="loadPostulaciones()" style="width:190px">
                    <option value="Todos">Todos los portales (14)</option>
                </select>
                <select id="filter-estado" onchange="loadPostulaciones()" style="width:220px">
                    <option value="Todos">Todos los estados</option>
                    <option value="🟡 Postulado (Abierta en Brave)">🟡 Abierta en Brave</option>
                    <option value="🟡 Lista con IA (En Cola 1-Clic)">🟡 En Cola 1-Clic (Lista con IA)</option>
                    <option value="🟢 Postulado Confirmado">🟢 Postulado Confirmado</option>
                    <option value="🟣 En entrevista">🟣 En entrevista</option>
                    <option value="🟢 Oferta recibida">🟢 Oferta recibida</option>
                    <option value="🔴 No aceptado">🔴 No aceptado</option>
                </select>
            </div>
        </div>

        <div tabindex="0" role="region" aria-labelledby="postulaciones-table-caption" class="table-wrapper">
            <table class="offers-table">
                <caption id="postulaciones-table-caption" class="sr-caption">
                    Ofertas reales filtradas para Ingeniería en Infraestructura y Plataformas Tecnológicas (Duoc UC) y Empleos TI
                </caption>
                <thead>
                    <tr>
                        <th scope="col">Cargo / Vacante</th>
                        <th scope="col">Portal</th>
                        <th scope="col">Empresa y Ubicación</th>
                        <th scope="col">Afinidad Duoc</th>
                        <th scope="col">Estado</th>
                        <th scope="col">Acciones 1-Clic</th>
                    </tr>
                </thead>
                <tbody id="postulaciones-body">
                    <tr><th scope="row">Cargando...</th><td colspan="5">Consultando base SQLite...</td></tr>
                </tbody>
            </table>
        </div>
    </section>
</div>

<!-- Modal Respuestas IA con Light-Dismiss declarativo (closedby="any") -->
<dialog id="respuestasDialog" closedby="any" aria-labelledby="dialogTitle">
    <form method="dialog">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:8px;">
            <h2 id="dialogTitle" style="font-size:1.05rem;">🤖 Respuestas IA Personalizadas</h2>
            <button type="submit" class="btn-sm">✕ Cerrar</button>
        </div>
        <p id="dialogSubtitle" style="font-size:0.82rem; color:var(--text-muted); margin-bottom:10px;"></p>
        <div id="dialogQuestionsBody"></div>
    </form>
</dialog>

<!-- Modal Bookmarklet Universal 14 Portales -->
<dialog id="bookmarkletDialog" closedby="any" aria-labelledby="bmDialogTitle">
    <form method="dialog">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom:10px;">
            <h2 id="bmDialogTitle" style="font-size:1.05rem;">⚡ Bookmarklet Universal 1-Clic (14 Portales)</h2>
            <button type="submit" class="btn-sm">✕ Cerrar</button>
        </div>
        <p style="font-size:0.83rem; color:var(--text-secondary); margin-bottom:12px;">
            Arrastra el botón verde a tu barra de marcadores de Brave o copia el código. Al abrir cualquier oferta en
            <strong>DuocLaboral, FirstJob, Trabajando.cl, Laborum, Computrabajo, LinkedIn, Get on Board, BNE o Buk/AIRA</strong>,
            haz 1 clic para rellenar automáticamente RUT, teléfono, correo Duoc, 360 horas, Seguro Escolar y respuestas técnicas de Infraestructura.
        </p>
        <div style="display:flex; gap:10px; align-items:center; margin-bottom:12px; flex-wrap:wrap;">
            <a id="bmDragLink" href="#" class="btn-link btn-emerald" onclick="event.preventDefault(); copyBookmarklet();">⚡ Rellenar Práctica Infra Duoc</a>
            <button type="button" class="btn-sky" onclick="copyBookmarklet()">📋 Copiar Código JS</button>
        </div>
        <textarea id="bmCodeArea" readonly style="width:100%; height:130px; background:#070A12; color:#7DD3FC; border:1px solid var(--border-subtle); border-radius:10px; padding:10px; font-family:'JetBrains Mono',monospace; font-size:0.74rem;"></textarea>
    </form>
</dialog>

<div id="toast"></div>

<script>
    let CACHED_POSTS = {};
    let BOOKMARKLET_RAW = "";

    // Fallback obligatorio para navegadores sin soporte nativo de closedby en <dialog>
    if (!('closedBy' in HTMLDialogElement.prototype)) {
        document.querySelectorAll('dialog').forEach((dialog) => {
            dialog.addEventListener('click', (event) => {
                if (event.target !== dialog) return;
                const rect = dialog.getBoundingClientRect();
                const isDialogContent = (
                    rect.top <= event.clientY &&
                    event.clientY <= rect.top + rect.height &&
                    rect.left <= event.clientX &&
                    event.clientX <= rect.left + rect.width
                );
                if (isDialogContent) return;
                dialog.close();
            });
        });
    }

    function escapeHtml(str) {
        return String(str ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function showToast(msg) {
        const t = document.getElementById("toast");
        t.textContent = msg;
        t.style.display = "block";
        clearTimeout(window.__toastTimer);
        window.__toastTimer = setTimeout(() => { t.style.display = "none"; }, 3800);
    }

    async function loadStats() {
        try {
            const res = await fetch("/api/stats");
            const d = await res.json();
            document.getElementById("kpi-portales").textContent = d.portales_integrados;
            document.getElementById("kpi-total").textContent = d.total_postulaciones;
            document.getElementById("kpi-email-sub").textContent = `${d.con_email_directo} con correo directo de reclutador`;
            document.getElementById("kpi-activas").textContent = d.postuladas_activas;
            document.getElementById("kpi-cola").textContent = d.en_cola_1clic;

            const kDaemon = document.getElementById("kpi-daemon");
            if (d.daemon_active && d.scheduler_enabled) {
                kDaemon.textContent = `🟢 ACTIVO (PID ${d.daemon_pid})`;
                kDaemon.style.color = "#34D399";
            } else if (d.daemon_active) {
                kDaemon.textContent = `🟡 EN ESPERA (PID ${d.daemon_pid})`;
                kDaemon.style.color = "#FBBF24";
            } else {
                kDaemon.textContent = "⚪ MODO MANUAL";
                kDaemon.style.color = "#94A3B8";
            }
            document.getElementById("kpi-proximo").textContent = `Próximo: ${d.proximo_horario}`;

            if (!window.__filtersInitialized) {
                document.getElementById("modo-select").value = d.modo_busqueda || "practica_duoc";
                document.getElementById("termino-input").value = d.termino_personalizado || "";
                window.__filtersInitialized = true;
            }
            if (d.bookmarklet) {
                BOOKMARKLET_RAW = d.bookmarklet;
                document.getElementById("bmCodeArea").value = d.bookmarklet;
                document.getElementById("bmDragLink").setAttribute("href", d.bookmarklet);
            }
            return d.conteo_postulaciones_portal || {};
        } catch (e) {
            return {};
        }
    }

    async function loadPortales(conteoPorPortal) {
        try {
            const res = await fetch("/api/portales");
            const portales = await res.json();
            const sel = document.getElementById("filter-portal");
            if (sel.options.length <= 1) {
                portales.forEach(p => {
                    const opt = document.createElement("option");
                    opt.value = p.nombre;
                    opt.textContent = p.nombre;
                    sel.appendChild(opt);
                });
            }
            const grid = document.getElementById("portals-grid");
            grid.innerHTML = portales.map(p => {
                const enBd = (conteoPorPortal && conteoPorPortal[p.nombre]) ? conteoPorPortal[p.nombre] : 0;
                const tags = [
                    p.soporta_practicas ? "Prácticas" : null,
                    p.soporta_empleos ? "Empleos" : null
                ].filter(Boolean).join(" · ");
                return `
                    <div class="portal-card">
                        <div class="portal-head">
                            <span class="portal-name"><span class="dot-live"></span> ${escapeHtml(p.nombre)}</span>
                            <span class="badge badge-score">${enBd} en cola/BD</span>
                        </div>
                        <div class="portal-meta">${escapeHtml(p.tipo_extraccion)}</div>
                        <div class="portal-notes">${escapeHtml(tags)} — ${escapeHtml((p.notas_tecnicas || "").slice(0, 92))}</div>
                    </div>
                `;
            }).join("");
        } catch (e) {}
    }

    async function loadPostulaciones() {
        const tbody = document.getElementById("postulaciones-body");
        const portal = document.getElementById("filter-portal").value;
        const estado = document.getElementById("filter-estado").value;
        const q = document.getElementById("search-offers").value;
        try {
            const params = new URLSearchParams({ portal, estado, q });
            const res = await fetch("/api/postulaciones?" + params.toString());
            const items = await res.json();
            CACHED_POSTS = {};
            if (!items.length) {
                tbody.innerHTML = `<tr><th scope="row">Sin resultados</th><td colspan="5">No hay ofertas que coincidan con el filtro seleccionado.</td></tr>`;
                return;
            }
            const estadosOpts = [
                "🟡 Lista con IA (En Cola 1-Clic)",
                "🟡 Postulado (Abierta en Brave)",
                "🟢 Postulado Confirmado",
                "🟣 En entrevista",
                "🟢 Oferta recibida",
                "🔴 No aceptado"
            ];
            tbody.innerHTML = items.map(p => {
                CACHED_POSTS[p.id] = p;
                const emailBtn = p.mailto_url
                    ? `<a class="btn-link btn-sm btn-emerald" href="${escapeHtml(p.mailto_url)}" title="Enviar correo pre-redactado a ${escapeHtml(p.email_reclutador)}">✉️ Email Directo</a>`
                    : "";
                const optsHtml = estadosOpts.map(st =>
                    `<option value="${escapeHtml(st)}" ${p.estado === st ? "selected" : ""}>${escapeHtml(st)}</option>`
                ).join("");

                return `
                    <tr>
                        <th scope="row">
                            <div style="font-size:0.86rem; line-height:1.3;">${escapeHtml(p.titulo)}</div>
                            <div style="font-size:0.72rem; color:var(--text-muted); font-weight:500; margin-top:3px;">
                                📅 ${escapeHtml(p.fecha_oferta || p.fecha_postulacion || "Reciente")} · ${escapeHtml(p.asignacion_dinero || "Asignación")}
                            </div>
                        </th>
                        <td><span class="badge badge-portal">${escapeHtml(p.portal)}</span></td>
                        <td>
                            <div style="font-weight:700; color:#F1F5F9;">${escapeHtml(p.empresa)}</div>
                            <div style="font-size:0.74rem; color:var(--text-muted);">📍 ${escapeHtml(p.ubicacion || "Santiago, RM")}</div>
                        </td>
                        <td><span class="badge badge-score">${Number(p.score_duoc || 90)}% Duoc</span></td>
                        <td>
                            <select onchange="updateOfferStatus(${p.id}, this.value)" style="padding:5px 8px; font-size:0.75rem; min-width:175px;">
                                ${optsHtml}
                            </select>
                        </td>
                        <td>
                            <div class="actions-cell">
                                <a class="btn-link btn-sm btn-sky" href="${escapeHtml(p.url_oferta || '#')}" target="_blank" rel="noopener">🌐 Abrir Portal</a>
                                <button type="button" class="btn-sm" onclick="showAnswersModal(${p.id})">📝 Respuestas IA</button>
                                ${emailBtn}
                            </div>
                        </td>
                    </tr>
                `;
            }).join("");
        } catch (e) {
            tbody.innerHTML = `<tr><th scope="row">Error</th><td colspan="5">No se pudo cargar la tabla de postulaciones.</td></tr>`;
        }
    }

    async function loadLogs() {
        const box = document.getElementById("logs-container");
        try {
            const res = await fetch("/api/logs");
            const logs = await res.json();
            if (!logs.length) {
                box.innerHTML = `<span style="color:var(--text-muted)">Sin ejecuciones previas registradas.</span>`;
                return;
            }
            box.innerHTML = logs.map(l => `
                <div>
                    <span style="color:#64748B">[${escapeHtml(l.fecha_hora)}]</span>
                    <span style="color:#34D399; font-weight:700;"> +${Number(l.ofertas_postuladas || 0)} procesadas</span>
                    <span style="color:#CBD5E1"> — ${escapeHtml(l.detalle || "")}</span>
                </div>
            `).join("");
        } catch (e) {}
    }

    function showAnswersModal(id) {
        const p = CACHED_POSTS[id];
        if (!p) return;
        const dlg = document.getElementById("respuestasDialog");
        document.getElementById("dialogTitle").textContent = `🤖 Respuestas IA · ${p.empresa}`;
        document.getElementById("dialogSubtitle").textContent = `${p.titulo} (${p.portal})` + (p.email_reclutador ? ` · ✉️ Contacto directo: ${p.email_reclutador}` : "");
        const body = document.getElementById("dialogQuestionsBody");
        let parsed = {};
        try { parsed = JSON.parse(p.respuestas_formulario || "{}"); } catch (e) {}
        const entries = Object.entries(parsed);
        if (!entries.length) {
            body.innerHTML = `<p style="color:var(--text-muted)">Sin preguntas específicas registradas.</p>`;
        } else {
            body.innerHTML = entries.map(([q, a]) => `
                <div class="qa-item">
                    <div class="qa-q">❓ ${escapeHtml(q)}</div>
                    <div class="qa-a">${escapeHtml(a)}</div>
                </div>
            `).join("");
        }
        dlg.showModal();
    }

    function openBookmarkletModal() {
        document.getElementById("bookmarkletDialog").showModal();
    }

    async function copyBookmarklet() {
        if (!BOOKMARKLET_RAW) return;
        try {
            await navigator.clipboard.writeText(BOOKMARKLET_RAW);
            showToast("⚡ Bookmarklet copiado al portapapeles");
        } catch (e) {
            document.getElementById("bmCodeArea").select();
            document.execCommand("copy");
            showToast("⚡ Bookmarklet copiado");
        }
    }

    async function updateOfferStatus(id, estado) {
        await fetch("/api/update-status", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id, estado })
        });
        showToast("✅ Estado actualizado");
        loadStats();
    }

    async function saveFiltersAndScan() {
        const modo_busqueda = document.getElementById("modo-select").value;
        const termino_personalizado = document.getElementById("termino-input").value;
        await fetch("/api/save-filters", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ modo_busqueda, termino_personalizado })
        });
        await triggerManualScan();
    }

    async function triggerManualScan() {
        showToast("🌐 Escaneando los 14 portales en segundo plano...");
        await fetch("/api/run-scan", { method: "POST" });
        setTimeout(refreshAll, 4500);
    }

    async function startInteractiveLoop() {
        showToast("🚀 Iniciando bucle interactivo sobre pantalla en Brave (30s)...");
        const res = await fetch("/api/start-interactive-loop", { method: "POST" });
        const d = await res.json();
        if (d.ok) {
            showToast("✅ Bucle interactivo iniciado en pantalla.");
        } else {
            showToast("❌ Error al iniciar: " + (d.error || "Desconocido"));
        }
        setTimeout(refreshAll, 3000);
    }

    async function startHeadlessBatch() {
        if (!confirm("¿Deseas iniciar la postulación continua en segundo plano para todas las ofertas válidas de la RM?")) return;
        showToast("⚡ Iniciando postulación en segundo plano...");
        const res = await fetch("/api/start-headless-batch", { method: "POST" });
        const d = await res.json();
        if (d.ok) {
            showToast("✅ Postulación en segundo plano ejecutándose.");
        } else {
            showToast("❌ Error al iniciar: " + (d.error || "Desconocido"));
        }
        setTimeout(refreshAll, 3000);
    }

    async function stopBotProcess() {
        showToast("🛑 Deteniendo procesos del bot...");
        const res = await fetch("/api/stop-bot", { method: "POST" });
        const d = await res.json();
        showToast(d.ok ? "🛑 Procesos del bot detenidos." : "No había procesos activos.");
        setTimeout(refreshAll, 2000);
    }

    async function openNextBatch() {
        const res = await fetch("/api/open-next-batch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ cantidad: 10 })
        });
        const d = await res.json();
        showToast(`🚀 Abiertas ${d.abiertas || 0} ofertas prioritarias en Brave`);
        refreshAll();
    }

    async function openPersistentSession() {
        const res = await fetch("/api/open-session", { method: "POST" });
        const d = await res.json();
        if (d.ok) {
            showToast("🔐 Ventana Brave Persistente abierta para loguearse 1 sola vez");
        } else {
            showToast("⚠️ No se pudo abrir la ventana persistente");
        }
    }

    async function toggleScheduler() {
        const res = await fetch("/api/toggle-scheduler", { method: "POST" });
        const d = await res.json();
        showToast(d.activo ? "🟢 Piloto 24/7 activado" : "⏸️ Piloto 24/7 en pausa");
        refreshAll();
    }

    async function refreshAll() {
        const conteo = await loadStats();
        await Promise.all([
            loadPortales(conteo),
            loadPostulaciones(),
            loadLogs()
        ]);
    }

    refreshAll();
    setInterval(refreshAll, 15000);
</script>
</body>
</html>
"""


class AutoPostulaHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path in ("/", "/index.html"):
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif parsed.path == "/api/stats":
            self._send_json(get_stats())
        elif parsed.path == "/api/portales":
            init_db()
            self._send_json(obtener_catalogo_portales())
        elif parsed.path == "/api/postulaciones":
            estado = (qs.get("estado") or ["Todos"])[0]
            portal = (qs.get("portal") or ["Todos"])[0]
            q = (qs.get("q") or [""])[0]
            self._send_json(serialize_postulaciones(estado, portal, q, limit=200))
        elif parsed.path == "/api/logs":
            init_db()
            self._send_json(obtener_logs_scheduler(limit=30))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/start-interactive-loop":
            try:
                env = os.environ.copy()
                env["DISPLAY"] = ":0"
                env["XAUTHORITY"] = "/home/dhamit/.Xauthority"
                subprocess.Popen(
                    ["/home/dhamit/Documentos/MYCreIAtedAPPs/AutoPostula/bot_pantalla.sh", "--segundos", "30"],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self._send_json({"ok": True, "modo": "interactivo"})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)

        elif parsed.path == "/api/start-headless-batch":
            try:
                env = os.environ.copy()
                env["DISPLAY"] = ":0"
                env["XAUTHORITY"] = "/home/dhamit/.Xauthority"
                subprocess.Popen(
                    ["/home/dhamit/Documentos/MYCreIAtedAPPs/AutoPostula/bot_pantalla.sh", "--segundos", "0", "--no-focus"],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self._send_json({"ok": True, "modo": "segundo_plano"})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)

        elif parsed.path == "/api/stop-bot":
            try:
                subprocess.run(["pkill", "-f", "bucle_pantalla_interactivo.py"], check=False)
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)

        elif parsed.path == "/api/run-scan":
            try:
                subprocess.Popen(
                    [PYTHON_BIN, DAEMON_SCRIPT, "--once"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, status=500)

        elif parsed.path == "/api/save-filters":
            data = self._read_json()
            guardar_filtros({
                "modo_busqueda": data.get("modo_busqueda", "practica_duoc"),
                "termino_personalizado": data.get("termino_personalizado", "infraestructura plataformas soporte redes cloud"),
            })
            self._send_json({"ok": True})

        elif parsed.path == "/api/update-status":
            data = self._read_json()
            if data.get("id") and data.get("estado"):
                actualizar_estado_postulacion(int(data["id"]), str(data["estado"]))
            self._send_json({"ok": True})

        elif parsed.path == "/api/open-next-batch":
            data = self._read_json()
            cantidad = max(1, min(20, int(data.get("cantidad") or 10)))
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                SELECT id, url_oferta FROM postulaciones
                WHERE estado LIKE '%Cola%'
                ORDER BY score_duoc DESC, id ASC
                LIMIT ?;
            """, (cantidad,))
            rows = cur.fetchall()
            abiertas = 0
            for r in rows:
                u = r["url_oferta"] or ""
                if u.startswith("http"):
                    try:
                        subprocess.Popen(["brave-browser", u], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        cur.execute("UPDATE postulaciones SET estado = '🟡 Postulado (Abierta en Brave)', metodo_postulacion = 'abierta_en_brave' WHERE id = ?;", (r["id"],))
                        abiertas += 1
                        time.sleep(0.35)
                    except Exception:
                        pass
            conn.commit()
            conn.close()
            self._send_json({"ok": True, "abiertas": abiertas})

        elif parsed.path == "/api/open-session":
            res = abrir_sesion_persistente_portales()
            self._send_json(res)

        elif parsed.path == "/api/toggle-scheduler":
            actual = obtener_estado_scheduler()
            nuevo = 0 if int(actual.get("activo") or 0) == 1 else 1
            prox = calcular_proximo_horario(actual.get("horarios", "01:00, 04:00, 06:30, 08:00, 12:00, 14:00, 17:00, 22:00"))
            guardar_estado_scheduler(activo=nuevo, proximo_escaneo=prox)
            self._send_json({"ok": True, "activo": nuevo, "proximo_escaneo": prox})

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        return


def run():
    init_db()
    HTTPServer.allow_reuse_address = True
    server = HTTPServer(("0.0.0.0", PORT), AutoPostulaHandler)
    print("=" * 64)
    print(f"🎯 AutoPostula NOC Dashboard (14 Portales) activo en:")
    print(f"   👉 http://localhost:{PORT}")
    print("=" * 64)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    run()
