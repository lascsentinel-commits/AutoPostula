import json
import os
import subprocess
import time
from datetime import datetime

import streamlit as st

from daemon_scheduler import calcular_proximo_horario, ejecutar_ciclo_escaneo
from database import (
    PORTALES_SOPORTADOS,
    actualizar_estado_postulacion,
    agregar_postulacion,
    buscar_respuesta_aprendida,
    esta_postulado,
    get_conn,
    guardar_estado_scheduler,
    guardar_filtros,
    guardar_perfil,
    init_db,
    obtener_alertas_pendientes,
    obtener_catalogo_portales,
    obtener_estado_scheduler,
    obtener_filtros,
    obtener_logs_scheduler,
    obtener_perfil,
    obtener_postulaciones,
    obtener_respuestas_aprendidas,
    registrar_alerta_pendiente,
    resolver_alerta_y_aprender,
)
from modules.ai_matcher import (
    evaluar_oferta_inteligente,
    generar_respuesta_persuasiva_ia,
    resolver_pregunta_formulario,
    sanitizar_texto_seguro,
)
from modules.auto_applier import (
    abrir_sesion_persistente_portales,
    ejecutar_autopostulacion_lote,
    generar_bookmarklet_universal,
    generar_mailto_postulacion,
)
from modules.cv_parser import analizar_cv, extraer_texto_pdf
from modules.scrapers import buscar_todas_las_practicas

# Inicializar Base de Datos y Catálogo de 14 Portales
init_db()

st.set_page_config(
    page_title="AutoPostula · 14 Portales Chile · Duoc UC & Empleos TI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-title { font-size: 2.2rem; font-weight: 800; color: #38bdf8; margin-bottom: 2px; letter-spacing: -0.5px; }
    .sub-title { font-size: 0.98rem; color: #94a3b8; margin-bottom: 18px; }
    .card-job {
        background: rgba(15, 23, 42, 0.82);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 14px;
        box-shadow: 0 8px 24px -4px rgba(0, 0, 0, 0.32);
    }
    .badge-portal {
        background: linear-gradient(135deg, #0284c7, #0369a1);
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.76rem;
        font-weight: 700;
        display: inline-block;
    }
    .badge-modalidad {
        background: #334155;
        color: #e2e8f0;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.76rem;
        margin-left: 6px;
        display: inline-block;
    }
    .badge-money {
        background: linear-gradient(135deg, #16a34a, #15803d);
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.76rem;
        font-weight: 600;
        margin-left: 6px;
        display: inline-block;
    }
    .badge-score {
        background: rgba(16, 185, 129, 0.18);
        color: #6ee7b7;
        border: 1px solid rgba(16, 185, 129, 0.4);
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.76rem;
        font-weight: 700;
        margin-left: 6px;
        display: inline-block;
    }
    .badge-alert {
        background: #e11d48;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

perfil = obtener_perfil()
filtros = obtener_filtros()
alertas = obtener_alertas_pendientes()
catalogo_portales = obtener_catalogo_portales()
bookmarklet_universal = generar_bookmarklet_universal(perfil)

col_head_left, col_head_right = st.columns([5, 2])
with col_head_left:
    st.markdown("<h1 class='main-title'>🎯 AutoPostula · 14 Portales Reales Chile</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='sub-title'>Prácticas Profesionales Duoc UC (<b>Ingeniería en Infraestructura y Plataformas Tecnológicas · 360h</b>) "
        "y postulación universal a <b>cualquier pega o empleo TI</b></p>",
        unsafe_allow_html=True,
    )

with col_head_right:
    with st.popover("⚡ Asistente IA & Bookmarklet 14 Portales", use_container_width=True):
        st.markdown("#### 🛡️ Rellenador IA Anti-Prompt-Injection")
        st.caption("Pega cualquier pregunta de filtro de un portal. La IA la responde alineada a tu perfil de Infraestructura Duoc UC o Empleo TI.")

        pregunta_externa = st.text_area(
            "Pregunta del portal:",
            placeholder="Ej: ¿Cuántas horas dura tu práctica y tienes seguro escolar? / ¿Experiencia en AWS, redes y Linux?",
            height=80,
            key="popover_preg_input",
        )
        modo_actual_pop = filtros.get("modo_busqueda", "practica_duoc")

        if st.button("✨ Generar Respuesta IA", type="primary", use_container_width=True, key="popover_btn_gen"):
            if pregunta_externa.strip():
                p_segura = sanitizar_texto_seguro(pregunta_externa)
                resp_aprendida = buscar_respuesta_aprendida(p_segura)
                if resp_aprendida:
                    st.success("🧠 Encontrada en tu memoria aprendida:")
                    st.text_area("Respuesta:", value=resp_aprendida, height=110)
                else:
                    ok, resp_ia, _ = resolver_pregunta_formulario(
                        p_segura, perfil, buscar_respuesta_aprendida, modo=modo_actual_pop
                    )
                    if not ok:
                        resp_ia = generar_respuesta_persuasiva_ia(p_segura, perfil)
                    st.success("🤖 Respuesta generada:")
                    st.text_area("Copia tu respuesta:", value=resp_ia, height=130)
                    if st.button("💾 Guardar en memoria", key="btn_save_popover_mem"):
                        resolver_alerta_y_aprender(99999, p_segura, resp_ia, categoria="asistente_ia")
                        st.success("✅ Guardada para futuras postulaciones.")

        st.markdown("---")
        with st.expander("⚡ Bookmarklet Universal 1-Clic (14 Portales)"):
            st.caption("Guárdalo como marcador en Brave. Rellena automáticamente DuocLaboral, FirstJob, Trabajando.cl, Laborum, Computrabajo, LinkedIn, Get on Board, BNE y Buk/AIRA.")
            st.code(bookmarklet_universal, language="javascript")

        if st.button("🔐 Abrir Sesión Persistente en Brave (Loguearse 1 vez)", use_container_width=True):
            res_s = abrir_sesion_persistente_portales()
            if res_s.get("ok"):
                st.success("✅ Ventana Brave con sesión persistente abierta.")
            else:
                st.error(res_s.get("error", "Error abriendo sesión"))

# Sidebar
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Logo_Duoc_UC.svg/512px-Logo_Duoc_UC.svg.png", width=155)
    st.markdown(f"**Candidato:** {perfil.get('nombre') or 'Dhani Amit Elgueta Ríos'}")
    st.markdown(f"**RUT:** `{perfil.get('rut') or '20.338.608-7'}`")
    st.markdown(f"**Carrera:** {perfil.get('carrera') or 'Ingeniería en Infraestructura y Plataformas Tecnológicas'}")
    st.markdown(f"**Sede:** {perfil.get('institucion') or 'Duoc UC'} · {perfil.get('sede') or 'Sede Antonio Varas'} ({perfil.get('jornada_estudios') or 'Vespertino'})")

    h_req = int(perfil.get("horas_requeridas") or 360)
    r_esp_val = int(perfil.get("renta_esperada") or 0)
    r_emp_val = int(perfil.get("renta_empleo") or 950000)

    st.markdown(f"**Requisito Duoc UC:** {h_req} hrs cronológicas + Seguro Ley 16.744")
    st.markdown(f"**Asignación Práctica:** {'$0 / Convenio locomoción' if r_esp_val == 0 else f'${r_esp_val:,}'.replace(',', '.')}")
    st.markdown(f"**Renta Empleo TI:** ${r_emp_val:,}".replace(",", "."))
    st.markdown(f"**Portales Conectados:** **{len(PORTALES_SOPORTADOS)} portales en vivo**")
    st.link_button("⚡ Abrir Panel NOC Rápido (:8087)", "http://localhost:8087", use_container_width=True)

    st.markdown("---")
    estado_sched = obtener_estado_scheduler()
    if estado_sched.get("activo") == 1:
        st.success(f"🟢 **Piloto 24/7 ACTIVO**\nPróximo: {estado_sched.get('proximo_escaneo', 'Pronto')}")
    else:
        st.info("🔴 **Piloto 24/7:** En pausa")

    if len(alertas) > 0:
        st.warning(f"⚠️ **{len(alertas)}** pregunta(s) pendiente(s).")
    else:
        st.success("✅ Sin preguntas pendientes.")

tab_tablero, tab_buscar, tab_portales, tab_scheduler, tab_alertas, tab_perfil, tab_filtros, tab_memoria = st.tabs([
    "📊 Mis Postulaciones & Cola",
    "🚀 Multi-Buscador (14 Portales)",
    f"📡 Catálogo 14 Portales ({len(catalogo_portales)})",
    f"⏱️ Piloto 24/7 ({'🟢 ACTIVO' if estado_sched.get('activo') == 1 else '🔴 PAUSA'})",
    f"🔔 Alertas ({len(alertas)})",
    "📄 Mi CV & Perfil Duoc UC",
    "⚙️ Modo Práctica / Cualquier Pega",
    "🧠 Memoria IA",
])

# ============================================================================
# PESTAÑA 1: TABLERO DE POSTULACIONES Y COLA 1-CLIC
# ============================================================================
with tab_tablero:
    st.subheader("📋 Cola Activa e Historial de Postulaciones")

    todas_post = obtener_postulaciones("Todos", "Todos")
    en_cola_list = [x for x in todas_post if "Cola" in (x.get("estado") or "")]
    abiertas_list = [x for x in todas_post if "Brave" in (x.get("estado") or "") or "Confirmado" in (x.get("estado") or "")]
    con_correo_list = [x for x in todas_post if (x.get("email_reclutador") or "").strip()]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Ofertas Procesadas", len(todas_post))
    m2.metric("Abiertas / Confirmadas", len(abiertas_list))
    m3.metric("En Cola 1-Clic (Listas con IA)", len(en_cola_list))
    m4.metric("Con Correo Directo Reclutador", len(con_correo_list))

    st.markdown("### 🤖 Centro de Control de Postulación Automática")
    c_bot1, c_bot2, c_bot3 = st.columns([1.5, 1.5, 1.0])
    with c_bot1:
        if st.button("🤖 Bucle en Pantalla (30s con Voz & Brave)", type="primary", use_container_width=True, help="Ejecuta la automatización sobre tu pantalla enfocando Brave, tipeando las respuestas, narrando con Di y mostrando el control flotante de 30s."):
            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            env["XAUTHORITY"] = "/home/dhamit/.Xauthority"
            subprocess.Popen(
                ["/home/dhamit/Documentos/MYCreIAtedAPPs/AutoPostula/bot_pantalla.sh", "--segundos", "30"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            st.success("🚀 Bucle interactivo iniciado en Brave. Revisa tu pantalla con el control flotante.")
            st.rerun()

    with c_bot2:
        if st.button("⚡ Postular a Todas las Válidas (Segundo Plano)", use_container_width=True, help="Postula a todas las ofertas válidas de la RM de forma automática y continua en segundo plano."):
            env = os.environ.copy()
            env["DISPLAY"] = ":0"
            env["XAUTHORITY"] = "/home/dhamit/.Xauthority"
            subprocess.Popen(
                ["/home/dhamit/Documentos/MYCreIAtedAPPs/AutoPostula/bot_pantalla.sh", "--segundos", "0", "--no-focus"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            st.success("⚡ Postulación en segundo plano iniciada para todas las ofertas válidas.")
            st.rerun()

    with c_bot3:
        if st.button("🛑 Detener Bot", use_container_width=True, help="Detiene cualquier proceso activo de bucle_pantalla_interactivo.py"):
            subprocess.run(["pkill", "-f", "bucle_pantalla_interactivo.py"], check=False)
            st.warning("🛑 Procesos del bot detenidos.")
            st.rerun()

    st.markdown("---")
    ca1, ca2, ca3 = st.columns([2, 2, 2])
    with ca1:
        filtro_estado = st.selectbox(
            "Filtrar por estado:",
            [
                "Todos",
                "🟡 Postulado (Abierta en Brave)",
                "🟡 Lista con IA (En Cola 1-Clic)",
                "🟢 Postulado Confirmado",
                "🟣 En entrevista",
                "🟢 Oferta recibida",
                "🔴 No aceptado",
            ],
            key="filtro_estado_tablero",
        )
    with ca2:
        filtro_portal = st.selectbox(
            "Filtrar por portal:",
            ["Todos"] + PORTALES_SOPORTADOS,
            key="filtro_portal_tablero",
        )
    with ca3:
        st.write("")
        if st.button(f"🚀 Abrir Siguiente Lote de 10 en Brave ({len(en_cola_list)} en cola)", type="primary", use_container_width=True, disabled=len(en_cola_list) == 0):
            conn = get_conn()
            cur = conn.cursor()
            abiertas_ahora = 0
            for item_c in en_cola_list[:10]:
                u = item_c.get("url_oferta") or ""
                if u.startswith("http"):
                    subprocess.Popen(["brave-browser", u], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    cur.execute("UPDATE postulaciones SET estado = '🟡 Postulado (Abierta en Brave)', metodo_postulacion = 'abierta_en_brave' WHERE id = ?;", (item_c["id"],))
                    abiertas_ahora += 1
                    time.sleep(0.35)
            conn.commit()
            conn.close()
            st.success(f"🚀 Se abrieron {abiertas_ahora} ofertas prioritarias en Brave listas para confirmar con 1 clic.")
            st.rerun()

    postulaciones = obtener_postulaciones(filtro_estado, filtro_portal)

    if not postulaciones:
        st.info("No hay postulaciones con este filtro.")
    else:
        st.caption(f"Mostrando **{min(len(postulaciones), 80)}** de **{len(postulaciones)}** ofertas registradas:")
        for p in postulaciones[:80]:
            score_d = p.get("score_duoc") or 90
            email_rec = (p.get("email_reclutador") or "").strip()
            mailto_u = generar_mailto_postulacion(p, perfil) if email_rec else ""

            st.markdown(f"""
            <div class='card-job'>
                <div style='display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;'>
                    <div>
                        <h3 style='margin: 0 0 5px 0; color: #f8fafc; font-size: 1.12rem;'>{p['titulo']}</h3>
                        <h4 style='margin: 0 0 8px 0; color: #38bdf8; font-weight: 600; font-size: 0.96rem;'>🏢 {p['empresa']} · 📍 {p.get('ubicacion') or 'Santiago, RM'}</h4>
                    </div>
                    <div>
                        <span class='badge-portal'>{p['portal']}</span>
                        <span class='badge-modalidad'>{p.get('modalidad') or 'Híbrido'}</span>
                        <span class='badge-money'>{p.get('asignacion_dinero') or 'Asignación'}</span>
                        <span class='badge-score'>🎯 {score_d}% Duoc Infra</span>
                    </div>
                </div>
                <p style='color: #cbd5e1; font-size: 0.88rem; margin-bottom: 8px;'>{(p.get('descripcion') or '')[:260]}...</p>
                <div style='display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.8rem; color: #94a3b8;'>
                    <span>📅 Aviso: {p.get('fecha_oferta') or 'Reciente'}</span>
                    <span>⚡ Procesado: {p.get('fecha_postulacion') or 'Hoy'}</span>
                    <span>📌 Estado actual: <b>{p.get('estado')}</b></span>
                    {f"<span style='color:#34d399;'>✉️ Contacto directo: <b>{email_rec}</b></span>" if email_rec else ""}
                </div>
            </div>
            """, unsafe_allow_html=True)

            c1, c2, c3, c4 = st.columns([2, 2.5, 1.3, 1.3])
            with c1:
                estados_opciones = [
                    "🟡 Lista con IA (En Cola 1-Clic)",
                    "🟡 Postulado (Abierta en Brave)",
                    "🟢 Postulado Confirmado",
                    "🟣 En entrevista",
                    "🟢 Oferta recibida",
                    "🔴 No aceptado",
                ]
                idx_est = estados_opciones.index(p["estado"]) if p["estado"] in estados_opciones else 0
                nuevo_est = st.selectbox("Estado:", estados_opciones, index=idx_est, key=f"estado_{p['id']}")
                if nuevo_est != p["estado"]:
                    actualizar_estado_postulacion(p["id"], nuevo_est)
                    st.rerun()
            with c2:
                notas_actuales = p.get("notas") or ""
                nuevas_notas = st.text_input("Notas:", value=notas_actuales, key=f"nota_{p['id']}")
                if nuevas_notas != notas_actuales:
                    actualizar_estado_postulacion(p["id"], p["estado"], nuevas_notas)
            with c3:
                st.link_button("🌐 Abrir Oferta", p.get("url_oferta") or "#", use_container_width=True)
                if mailto_u:
                    st.link_button("✉️ Enviar Correo", mailto_u, use_container_width=True)
            with c4:
                with st.popover("📝 Respuestas IA", use_container_width=True):
                    try:
                        respuestas_dict = json.loads(p.get("respuestas_formulario") or "{}")
                        for preg, resp in respuestas_dict.items():
                            st.markdown(f"**❓ {preg}**")
                            st.code(resp, language="text")
                    except Exception:
                        st.write("Sin detalle.")

# ============================================================================
# PESTAÑA 2: MULTI-BUSCADOR EN VIVO (14 PORTALES · PRÁCTICAS O CUALQUIER PEGA)
# ============================================================================
with tab_buscar:
    st.subheader("🔍 Multi-Buscador en Vivo en los 14 Portales de Chile")

    col_m1, col_m2, col_m3 = st.columns([2, 2.5, 1.5])
    with col_m1:
        mapa_modos = {
            "practica_duoc": "🎓 Solo Práctica Duoc UC (Ing. Infraestructura · 360h)",
            "empleo_ti": "💼 Cualquier Pega / Empleo TI Regular",
            "ambos": "🌐 Ambos (Prácticas + Empleos TI)",
        }
        modo_sel = st.selectbox(
            "Modo de búsqueda:",
            options=list(mapa_modos.keys()),
            format_func=lambda k: mapa_modos[k],
            index=list(mapa_modos.keys()).index(filtros.get("modo_busqueda", "practica_duoc"))
            if filtros.get("modo_busqueda", "practica_duoc") in mapa_modos else 0,
        )
    with col_m2:
        termino_sel = st.text_input(
            "Especialidad / Cargo a consultar:",
            value=filtros.get("termino_personalizado", "infraestructura plataformas soporte redes cloud"),
        )
    with col_m3:
        st.write("")
        btn_escanear = st.button("🌐 Escanear Portales Ahora", type="primary", use_container_width=True)

    portales_sel = st.multiselect(
        "Portales reales a consultar en paralelo (14 disponibles):",
        options=PORTALES_SOPORTADOS,
        default=filtros.get("portales_lista") or PORTALES_SOPORTADOS,
    )

    if btn_escanear:
        guardar_filtros({
            "modo_busqueda": modo_sel,
            "termino_personalizado": termino_sel,
            "portales_activos": portales_sel,
        })
        filtros = obtener_filtros()
        with st.spinner(f"Escaneando {len(portales_sel)} portales en tiempo real con HTTP + Playwright Headless Brave..."):
            st.session_state["ofertas_encontradas"] = buscar_todas_las_practicas(
                palabras_clave=termino_sel,
                portales=portales_sel,
                modo=modo_sel,
            )

    ofertas = st.session_state.get("ofertas_encontradas") or []

    if not ofertas:
        st.info("Pulsa **🌐 Escanear Portales Ahora** para consultar en vivo los 14 portales con el modo elegido, o revisa las 111+ ofertas ya cargadas en la pestaña **Mis Postulaciones & Cola**.")
    else:
        pendientes_validas = []
        ya_postuladas = []
        no_validas = []

        for of in ofertas:
            valida, motivo, score = evaluar_oferta_inteligente(of, filtros)
            of["score_duoc"] = score
            ya_esta = esta_postulado(url_oferta=of.get("url_oferta"), titulo=of.get("titulo"), empresa=of.get("empresa"))
            item = {"oferta": of, "valida": valida, "motivo": motivo, "score": score}
            if ya_esta:
                ya_postuladas.append(item)
            elif valida:
                pendientes_validas.append(item)
            else:
                no_validas.append(item)

        pendientes_validas.sort(key=lambda x: x["score"], reverse=True)

        st.markdown(f"### 🎯 Nuevas Vacantes Compatibles ({len(pendientes_validas)}) · Ya Procesadas ({len(ya_postuladas)}) · Descartadas ({len(no_validas)})")

        if pendientes_validas:
            if st.button(f"🚀 Preparar con IA y Abrir Top 10 en Brave ({len(pendientes_validas)} nuevas)", type="primary"):
                res = ejecutar_autopostulacion_lote(
                    [x["oferta"] for x in pendientes_validas],
                    perfil,
                    modo=modo_sel,
                    abrir_en_brave=True,
                    max_pestanas_brave=10,
                )
                st.success(f"🎉 Procesadas {res['postuladas']} ofertas ({res['pestanas_abiertas']} abiertas en Brave).")
                st.rerun()

            for idx, item in enumerate(pendientes_validas[:50]):
                of = item["oferta"]
                col_i, col_a = st.columns([4, 1.6])
                with col_i:
                    st.markdown(
                        f"**{of['titulo']}** — `{of['portal']}` · **{of['empresa']}** ({of.get('ubicacion', 'RM')})\n\n"
                        f"✅ *{item['motivo']}*"
                    )
                with col_a:
                    st.link_button("🌐 Ver Aviso", of.get("url_oferta", "#"), use_container_width=True)
                    if st.button("⚡ Postular con IA", key=f"post_live_{idx}", use_container_width=True):
                        ejecutar_autopostulacion_lote([of], perfil, modo=modo_sel, abrir_en_brave=True, max_pestanas_brave=1)
                        st.rerun()
                st.divider()

# ============================================================================
# PESTAÑA 3: CATÁLOGO TÉCNICO DE LOS 14 PORTALES
# ============================================================================
with tab_portales:
    st.subheader("📡 Arquitectura Técnica Recolectada de los 14 Portales Reales")
    st.markdown(
        "Información técnica levantada en vivo para soportar tanto **Prácticas Profesionales Duoc UC** "
        "como **cualquier pega / empleo formal en Chile**:"
    )
    for pt in catalogo_portales:
        st.markdown(f"""
        <div class='card-job' style='padding:14px;'>
            <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;'>
                <strong style='font-size:1.05rem; color:#f8fafc;'>🟢 {pt['nombre']} — <a href='{pt['url_base']}' target='_blank' style='color:#38bdf8;'>{pt['url_base']}</a></strong>
                <div>
                    <span class='badge-portal'>{pt['tipo_extraccion']}</span>
                    {"<span class='badge-score'>🎓 Prácticas</span>" if pt['soporta_practicas'] else ""}
                    {"<span class='badge-money'>💼 Empleos</span>" if pt['soporta_empleos'] else ""}
                </div>
            </div>
            <p style='margin:6px 0 4px 0; color:#cbd5e1; font-size:0.88rem;'>{pt['notas_tecnicas']}</p>
            <code style='font-size:0.78rem; color:#7dd3fc;'>Selectores DOM: {pt['selectores_dom']}</code>
        </div>
        """, unsafe_allow_html=True)

# ============================================================================
# PESTAÑA 4: PILOTO AUTOMÁTICO 24/7
# ============================================================================
with tab_scheduler:
    st.subheader("⏱️ Piloto Automático 24/7 en los 14 Portales")
    estado_actual = obtener_estado_scheduler()
    es_activo = estado_actual.get("activo") == 1

    c_s1, c_s2, c_s3 = st.columns(3)
    c_s1.metric("Estado del Demonio", "🟢 ACTIVO" if es_activo else "🔴 PAUSADO")
    c_s2.metric("Próximo Escaneo", estado_actual.get("proximo_escaneo") or "Pendiente")
    c_s3.metric("Total Procesadas Automáticamente", estado_actual.get("total_autopostuladas", 0))

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("🛑 ¡OBTUVE PRÁCTICA O PEGA! (Detener Robot)", type="primary", use_container_width=True):
            guardar_estado_scheduler(activo=0, motivo_detencion="🎉 Robot detenido porque obtuviste tu práctica / empleo.")
            st.balloons()
            st.rerun()
    with b2:
        if not es_activo:
            if st.button("🚀 Activar Monitoreo 24/7", use_container_width=True):
                prox = calcular_proximo_horario(estado_actual.get("horarios", "01:00, 04:00, 06:30, 08:00, 12:00, 14:00, 17:00, 22:00"))
                guardar_estado_scheduler(activo=1, proximo_escaneo=prox, motivo_detencion="")
                st.rerun()
        else:
            if st.button("⏸️ Pausar Monitoreo", use_container_width=True):
                guardar_estado_scheduler(activo=0, motivo_detencion="Pausado por el usuario.")
                st.rerun()
    with b3:
        if st.button("⚡ Ejecutar Ciclo Ahora", use_container_width=True):
            with st.spinner("Escaneando los 14 portales..."):
                ejecutar_ciclo_escaneo(abrir_en_brave=False)
                st.rerun()

    st.markdown("##### 📜 Últimas Ejecuciones:")
    for lg in obtener_logs_scheduler(limit=12):
        st.caption(f"🕒 **{lg['fecha_hora']}** — 🎯 {lg['ofertas_postuladas']} nuevas / {lg['ofertas_encontradas']} leídas — {lg['detalle']}")

# ============================================================================
# PESTAÑA 5: PREGUNTAS PENDIENTES
# ============================================================================
with tab_alertas:
    st.subheader("🔔 Preguntas Pendientes de Postulación")
    alertas_activas = obtener_alertas_pendientes()
    if not alertas_activas:
        st.success("🎉 ¡Cero preguntas pendientes! El motor IA cubre todos los formularios actuales.")
    else:
        for al in alertas_activas:
            st.markdown(f"**{al['cargo']}** en **{al['empresa']}** — ❓ *{al['pregunta']}*")
            sug_ia = generar_respuesta_persuasiva_ia(al["pregunta"], perfil, al.get("contexto_oferta", ""))
            resp_u = st.text_input("Respuesta:", value=sug_ia, key=f"al_{al['id']}")
            if st.button("💾 Guardar y Aprender", key=f"save_al_{al['id']}"):
                resolver_alerta_y_aprender(al["id"], al["pregunta"], resp_u)
                st.rerun()

# ============================================================================
# PESTAÑA 6: MI CV & PERFIL DUOC UC
# ============================================================================
with tab_perfil:
    st.subheader("📄 Currículum PDF y Perfil Maestro (Duoc UC & Empleo TI)")
    col_up, col_dat = st.columns([2.5, 4])

    with col_up:
        uploaded_pdf = st.file_uploader("Actualizar CV en PDF:", type=["pdf"])
        if uploaded_pdf is not None:
            uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
            os.makedirs(uploads_dir, exist_ok=True)
            pdf_path = os.path.join(uploads_dir, uploaded_pdf.name)
            with open(pdf_path, "wb") as f:
                f.write(uploaded_pdf.getbuffer())
            texto_cv = extraer_texto_pdf(pdf_path)
            datos_analizados = analizar_cv(texto_cv)
            datos_analizados["ruta_cv_pdf"] = pdf_path
            guardar_perfil(datos_analizados)
            st.success("✅ CV actualizado.")
            st.rerun()

        if perfil.get("ruta_cv_pdf"):
            st.info(f"📄 CV activo: **{os.path.basename(perfil['ruta_cv_pdf'])}**")

        st.markdown("""
        #### ✅ Requisitos Oficiales Duoc UC Verificados
        - **Carrera:** Ingeniería en Infraestructura y Plataformas Tecnológicas
        - **Horas mínimas:** 360 horas cronológicas
        - **Seguro Escolar:** Ley 16.744 vigente emitido por Duoc UC
        - **Inscripción oficial:** Portal `duoc.cl/practica` / Vivo Duoc (validar antes de iniciar horas)
        """)

    with col_dat:
        with st.form("form_perfil_maestro"):
            f_nom = st.text_input("Nombre completo:", value=perfil.get("nombre", ""))
            c_r1, c_r2 = st.columns(2)
            with c_r1:
                f_rut = st.text_input("RUT:", value=perfil.get("rut", "20.338.608-7"))
                f_cor = st.text_input("Correo institucional Duoc UC:", value=perfil.get("email", "dh.elgueta@duocuc.cl"))
            with c_r2:
                f_tel = st.text_input("Teléfono:", value=perfil.get("telefono", "+56 9 4850 8528"))
                f_cor2 = st.text_input("Correo secundario:", value=perfil.get("email_secundario", "correof1553@gmail.com"))

            c_i1, c_i2 = st.columns(2)
            with c_i1:
                f_ins = st.text_input("Institución:", value=perfil.get("institucion", "Duoc UC"))
                f_sed = st.text_input("Sede:", value=perfil.get("sede", "Sede Antonio Varas"))
            with c_i2:
                f_jor = st.text_input("Jornada de estudios:", value=perfil.get("jornada_estudios", "Vespertino"))
                f_lic = st.text_input("Licencia de conducir:", value=perfil.get("licencia_conducir", "Clase B"))

            f_car = st.text_input("Carrera exacta:", value=perfil.get("carrera", "Ingeniería en Infraestructura y Plataformas Tecnológicas"))

            c_p1, c_p2, c_p3 = st.columns(3)
            with c_p1:
                f_ren = st.number_input("Asignación Práctica ($):", min_value=0, max_value=1500000, value=int(perfil.get("renta_esperada") or 0), step=10000)
            with c_p2:
                f_ren_emp = st.number_input("Pretensión Renta Empleo TI ($):", min_value=400000, max_value=3500000, value=int(perfil.get("renta_empleo") or 950000), step=50000)
            with c_p3:
                f_hrs = st.number_input("Horas Práctica Duoc UC:", min_value=180, max_value=720, value=int(perfil.get("horas_requeridas") or 360), step=20)

            f_com = st.text_input("Comuna:", value=perfil.get("comuna", "Las Condes"))
            f_hab = st.text_area("Stack Técnico de Infraestructura y Plataformas:", value=perfil.get("habilidades_tech", ""), height=80)
            f_res = st.text_area("Resumen Profesional:", value=perfil.get("resumen_profesional", ""), height=80)

            if st.form_submit_button("💾 Guardar Perfil Maestro"):
                guardar_perfil({
                    "nombre": f_nom, "rut": f_rut, "email": f_cor, "email_secundario": f_cor2,
                    "telefono": f_tel, "institucion": f_ins, "sede": f_sed, "jornada_estudios": f_jor,
                    "licencia_conducir": f_lic, "carrera": f_car, "comuna": f_com,
                    "renta_esperada": f_ren, "renta_empleo": f_ren_emp, "horas_requeridas": f_hrs,
                    "habilidades_tech": f_hab, "resumen_profesional": f_res,
                })
                st.success("✅ Perfil actualizado.")
                st.rerun()

# ============================================================================
# PESTAÑA 7: FILTROS PARA PRÁCTICAS O CUALQUIER PEGA
# ============================================================================
with tab_filtros:
    st.subheader("⚙️ Configuración Dual: Práctica Duoc UC o Cualquier Pega")
    with st.form("form_filtros_practica"):
        f_modo = st.selectbox(
            "Modo activo global:",
            ["practica_duoc", "empleo_ti", "ambos"],
            format_func=lambda x: {
                "practica_duoc": "🎓 Solo Práctica Profesional Duoc UC (360h · Ing. Infraestructura y Plataformas)",
                "empleo_ti": "💼 Cualquier Pega / Empleo TI Formal",
                "ambos": "🌐 Ambos simultáneamente",
            }[x],
            index=["practica_duoc", "empleo_ti", "ambos"].index(filtros.get("modo_busqueda", "practica_duoc"))
            if filtros.get("modo_busqueda", "practica_duoc") in ("practica_duoc", "empleo_ti", "ambos") else 0,
        )
        f_term = st.text_input("Término de búsqueda libre (para empleos o prácticas):", value=filtros.get("termino_personalizado", "infraestructura plataformas soporte redes cloud"))
        f_com = st.text_area("Tecnologías y áreas clave de Infraestructura y Plataformas:", value=filtros.get("palabras_combinadas", ""), height=80)
        f_neg = st.text_area("Palabras de exclusión automática:", value=filtros.get("palabras_excluir", ""), height=65)
        f_rm = st.checkbox("Restringir a Región Metropolitana o 100% Remoto", value=bool(int(filtros.get("solo_rm_o_remoto", 1))))

        if st.form_submit_button("💾 Guardar Configuración Global"):
            guardar_filtros({
                "modo_busqueda": f_modo,
                "termino_personalizado": f_term,
                "palabras_combinadas": f_com,
                "palabras_excluir": f_neg,
                "solo_rm_o_remoto": 1 if f_rm else 0,
            })
            st.success("✅ Filtros actualizados.")
            st.rerun()

# ============================================================================
# PESTAÑA 8: MEMORIA APRENDIDA
# ============================================================================
with tab_memoria:
    st.subheader("🧠 Respuestas Aprendidas")
    respuestas = obtener_respuestas_aprendidas()
    if not respuestas:
        st.info("Aún no hay respuestas personalizadas manuales guardadas (el motor base ya resuelve automáticamente preguntas de Duoc UC, renta, horas, seguro, redes, Linux, cloud y ciberseguridad).")
    else:
        for r in respuestas:
            st.markdown(f"**❓ {r['pregunta_clave']}** *(usada {r['veces_usada']}x)* → {r['respuesta']}")
