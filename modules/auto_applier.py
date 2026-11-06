import json
import os
import subprocess
import time

if "PLAYWRIGHT_NODEJS_PATH" not in os.environ and os.path.exists("/home/dhamit/.local/bin/pw_node_wrapper.sh"):
    os.environ["PLAYWRIGHT_NODEJS_PATH"] = "/home/dhamit/.local/bin/pw_node_wrapper.sh"
from datetime import datetime
from urllib.parse import quote

from database import (
    agregar_postulacion,
    buscar_respuesta_aprendida,
    esta_postulado,
    obtener_perfil,
    registrar_alerta_pendiente,
)
from modules.ai_matcher import resolver_pregunta_formulario
from modules.cv_dispatcher import obtener_cv_optimo

BRAVE_BIN = "/opt/brave.com/brave/brave"
SESSION_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "playwright_session")


def generar_mailto_postulacion(oferta: dict, perfil: dict) -> str:
    """Genera un enlace mailto: pre-redactado cuando la oferta publica correo directo del reclutador."""
    email_dest = (oferta.get("email_reclutador") or "").split(",")[0].strip()
    if not email_dest:
        return ""
    nombre = perfil.get("nombre", "Dhani Amit Elgueta Ríos")
    carrera = perfil.get("carrera", "Ingeniería en Infraestructura y Plataformas Tecnológicas")
    inst = perfil.get("institucion", "Duoc UC")
    tel = perfil.get("telefono", "+56 9 4850 8528")
    correo_mio = perfil.get("email", "dh.elgueta@duocuc.cl")
    cargo = oferta.get("titulo", "Práctica Profesional Infraestructura TI")
    empresa = oferta.get("empresa", "su organización")

    asunto = f"Postulación {cargo} — {nombre} ({carrera} · {inst})"
    cuerpo = (
        f"Estimado equipo de Selección de {empresa},\n\n"
        f"Junto con saludar, envío mi postulación para la vacante '{cargo}'.\n"
        f"Soy estudiante de último semestre de {carrera} en {inst} (Sede Antonio Varas, jornada vespertina), "
        f"con disponibilidad diurna inmediata para realizar mi Práctica Profesional de 360 horas cronológicas "
        f"respaldada por Seguro Escolar de Accidentes vigente de Duoc UC (Ley 16.744).\n\n"
        f"Cuento con experiencia práctica en administración de servidores Linux/Windows Server, Active Directory, "
        f"Cloud AWS con Terraform, Docker/Kubernetes, redes Cisco, monitoreo Zabbix/Grafana, ciberseguridad (Wazuh/Suricata/Zeek) "
        f"y soporte TI corporativo.\n\n"
        f"Adjunto mi CV actualizado en PDF.\n"
        f"Contacto directo: {tel} | {correo_mio}\n\n"
        f"Atentamente,\n{nombre}"
    )
    return f"mailto:{email_dest}?subject={quote(asunto)}&body={quote(cuerpo)}"


def generar_bookmarklet_universal(perfil: dict = None) -> str:
    """
    Bookmarklet 1-Clic compatible con los 14 portales (DuocLaboral, FirstJob, Trabajando.cl,
    Laborum, Computrabajo, ChileTrabajos, LinkedIn, Get on Board, BNE, Prácticas Chile,
    Reqlut, Buk, AIRA, Teamtailor, Greenhouse, Lever).
    """
    if not perfil:
        perfil = obtener_perfil()
    nombre = perfil.get("nombre", "Dhani Amit Elgueta Ríos")
    rut = perfil.get("rut", "20.338.608-7")
    email = perfil.get("email", "dh.elgueta@duocuc.cl")
    tel = perfil.get("telefono", "+56948508528")
    carrera = perfil.get("carrera", "Ingeniería en Infraestructura y Plataformas Tecnológicas")
    comuna = perfil.get("comuna", "Las Condes")
    renta_prac = str(perfil.get("renta_esperada") or 0)
    horas = str(perfil.get("horas_requeridas") or 360)

    code = (
        "javascript:(function(){"
        f"const P={{nombre:{json.dumps(nombre)},rut:{json.dumps(rut)},email:{json.dumps(email)},tel:{json.dumps(tel)},"
        f"carrera:{json.dumps(carrera)},inst:'Duoc UC (Sede Antonio Varas)',comuna:{json.dumps(comuna + ', Región Metropolitana')},"
        f"renta:{json.dumps(renta_prac)},horas:'{horas} horas cronológicas según malla oficial Duoc UC',"
        "disp:'Disponibilidad diurna inmediata (estudio en horario vespertino en Duoc UC)',"
        "seguro:'Sí, cuento con Seguro Escolar de Accidentes vigente otorgado por Duoc UC (Ley 16.744).',"
        "lic:'Sí, cuento con Licencia de Conducir Clase B al día.',"
        "acad:'Último semestre de Ingeniería en Infraestructura y Plataformas Tecnológicas en Duoc UC Sede Antonio Varas (vespertino); solo restan 360h de práctica y 3 ramos para titularme.',"
        "infra:'Experiencia práctica administrando Linux (RHEL/Oracle/Ubuntu/Debian), Windows Server, Active Directory, M365, Cloud AWS con Terraform, Docker/Kubernetes, redes Cisco, monitoreo Zabbix/Grafana, ciberseguridad Wazuh/Zeek y soporte hardware/microsoldadura.'};"
        "let c=0;"
        "document.querySelectorAll(\"textarea,input[type='text'],input[type='email'],input[type='tel'],input[type='number']\").forEach(e=>{"
        "if(e.offsetParent===null||e.readOnly||e.disabled)return;"
        "const ctx=((e.placeholder||'')+' '+(e.name||'')+' '+(e.id||'')+' '+(e.closest('label,.form-group,.mb-3,.field,div')?e.closest('label,.form-group,.mb-3,.field,div').innerText.slice(0,220):'')).toLowerCase();"
        "let v='';"
        "if(e.type==='email'||ctx.includes('correo')||ctx.includes('email'))v=P.email;"
        "else if(e.type==='tel'||ctx.includes('teléfono')||ctx.includes('telefono')||ctx.includes('celular')||ctx.includes('phone'))v=P.tel;"
        "else if(ctx.includes('rut')||ctx.includes('run')||ctx.includes('documento'))v=P.rut;"
        "else if(ctx.includes('nombre completo')||(ctx.includes('nombre')&&!ctx.includes('empresa')))v=P.nombre;"
        "else if(ctx.includes('renta')||ctx.includes('sueldo')||ctx.includes('asignac')||ctx.includes('pretens')||ctx.includes('salary'))v=e.type==='number'?P.renta:(P.renta==='0'?'Acorde a asignación de práctica ($0 / movilización)':'$'+P.renta);"
        "else if(ctx.includes('hora')||ctx.includes('durac'))v=P.horas;"
        "else if(ctx.includes('seguro'))v=P.seguro;"
        "else if(ctx.includes('licencia')||ctx.includes('conducir'))v=P.lic;"
        "else if(ctx.includes('disponib')||ctx.includes('inicio')||ctx.includes('cuándo')||ctx.includes('horario'))v=P.disp;"
        "else if(ctx.includes('carrera')||ctx.includes('título')||ctx.includes('especialidad'))v=P.carrera;"
        "else if(ctx.includes('instituc')||ctx.includes('universidad')||ctx.includes('casa de estudio'))v=P.inst;"
        "else if(ctx.includes('comuna')||ctx.includes('ciudad')||ctx.includes('residencia')||ctx.includes('ubicación'))v=P.comuna;"
        "else if(ctx.includes('ramo')||ctx.includes('malla')||ctx.includes('avance')||ctx.includes('semestre')||ctx.includes('académic'))v=P.acad;"
        "else if(e.tagName==='TEXTAREA')v=P.infra;"
        "if(v){const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value')?.set||Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value')?.set;"
        "if(setter&&e.tagName!=='TEXTAREA')setter.call(e,v);else e.value=v;"
        "e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));c++;}"
        "});"
        "document.querySelectorAll(\"input[type='checkbox']\").forEach(cb=>{const l=(cb.closest('label,div')?.innerText||'').toLowerCase();"
        "if(!cb.checked&&(l.includes('término')||l.includes('termino')||l.includes('privacidad')||l.includes('acepto')||l.includes('seguro'))){cb.click();}});"
        "alert('⚡ AutoPostula 14-Portales: '+c+' campos rellenados para Ing. en Infraestructura y Plataformas Tecnológicas (Duoc UC). Revisa y pulsa Enviar.');"
        "})();"
    )
    return code


def generar_script_inyeccion_js(perfil: dict) -> str:
    """Devuelve script JS inyectable para Playwright y consola."""
    bm = generar_bookmarklet_universal(perfil)
    return bm.replace("javascript:", "", 1).replace("alert(", "console.log(")


def abrir_sesion_persistente_portales(url_inicial: str = "https://firstjob.me/ofertas") -> dict:
    """
    Abre una ventana de Brave con perfil persistente exclusivo de AutoPostula para iniciar sesión
    una sola vez en DuocLaboral, FirstJob, Trabajando.cl, Laborum, Computrabajo, LinkedIn, etc.
    """
    os.makedirs(SESSION_DIR, exist_ok=True)
    try:
        subprocess.Popen(
            [
                BRAVE_BIN,
                f"--user-data-dir={SESSION_DIR}",
                "--new-window",
                "https://duoclaboral.cl/login",
                "https://firstjob.me/login",
                "https://www.trabajando.cl/",
                "https://www.laborum.cl/",
                "https://cl.computrabajo.com/",
                "https://www.linkedin.com/jobs/",
                "https://www.getonbrd.com/",
                url_inicial,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"ok": True, "session_dir": SESSION_DIR}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def intentar_postulacion_playwright_persistente(oferta: dict, perfil: dict) -> tuple[bool, str]:
    """
    Intenta auto-rellenar y postular usando la sesión persistente de Playwright si no está bloqueada por otro proceso.
    Si el portal pide login, deja el formulario preparado o informa para confirmar con 1 clic.
    """
    if not os.path.exists(BRAVE_BIN) or not os.path.exists(SESSION_DIR):
        return False, "Sesión persistente aún no inicializada"

    url = oferta.get("url_oferta") or ""
    if not url.startswith("http"):
        return False, "URL inválida"

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR,
                executable_path=BRAVE_BIN,
                headless=True,
                args=["--no-sandbox", "--disable-gpu"],
                locale="es-CL",
            )
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=14000)
            page.wait_for_timeout(1800)

            # Detectar si redirigió a pantalla de login
            if "/login" in page.url.lower() or "iniciar-sesion" in page.url.lower():
                ctx.close()
                return False, "Requiere login en sesión persistente"

            # Buscar botón de postulación según selectores recolectados de los 14 portales
            selectores_postular = [
                "button:has-text('Postular ahora')",
                "button:has-text('Postularme')",
                "a:has-text('Postularme')",
                "button:has-text('Postular')",
                "a:has-text('Postular')",
                "button.jobs-apply-button",
            ]
            clic_abierto = False
            for sel in selectores_postular:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=3000)
                    clic_abierto = True
                    page.wait_for_timeout(1500)
                    break

            if "/login" in page.url.lower():
                ctx.close()
                return False, "Portal solicitó autenticación al pulsar Postular"

            # Subir CV PDF especializado según perfil de la oferta si hay input[type='file']
            cv_match = obtener_cv_optimo(oferta.get("titulo", ""), oferta.get("descripcion", ""))
            cv_path = cv_match.get("ruta_pdf") if (cv_match and cv_match.get("existe")) else (perfil.get("ruta_cv_pdf") or "")
            if cv_path and os.path.exists(cv_path):
                file_inp = page.locator("input[type='file']").first
                if file_inp.count() > 0:
                    try:
                        file_inp.set_input_files(cv_path)
                    except Exception:
                        pass

            # Inyectar el rellenador inteligente multi-portal
            js_fill = generar_script_inyeccion_js(perfil)
            page.evaluate(js_fill)
            page.wait_for_timeout(800)

            # Buscar botón final de confirmación
            for sel_env in ["button:has-text('Enviar postulación')", "button:has-text('Enviar')", "button:has-text('Confirmar')", "button[type='submit']"]:
                btn_e = page.locator(sel_env).first
                if btn_e.count() > 0 and btn_e.is_visible() and btn_e.is_enabled():
                    txt_b = (btn_e.inner_text() or "").lower()
                    if "buscar" not in txt_b and "login" not in txt_b and "ingresar" not in txt_b:
                        btn_e.click(timeout=3000)
                        page.wait_for_timeout(1500)
                        ctx.close()
                        return True, "Postulación enviada vía Playwright Persistente"

            ctx.close()
            return False, "Formulario inspeccionado; requiere confirmación en navegador con sesión activa"
    except Exception as e:
        return False, f"Playwright aviso: {str(e)[:80]}"


def ejecutar_autopostulacion_lote(
    ofertas_validas: list,
    perfil: dict,
    modo: str = "practica_duoc",
    abrir_en_brave: bool = True,
    max_pestanas_brave: int = 10,
    usar_playwright: bool = False,
) -> dict:
    """
    Procesa un lote de ofertas válidas:
    1. Genera respuestas IA adaptadas a Ingeniería en Infraestructura y Plataformas Tecnológicas (Duoc UC) o Empleo TI.
    2. Intenta envío automático si hay sesión persistente Playwright activa (opcional).
    3. Registra en SQLite con score Duoc UC, correo reclutador y respuestas listas.
    4. Abre hasta `max_pestanas_brave` ofertas prioritarias en Brave para confirmar con 1 clic usando la sesión del usuario.
    """
    postuladas_count = 0
    confirmadas_auto = 0
    pestanas_abiertas = 0
    errores = []

    for of in ofertas_validas:
        titulo = of.get("titulo", "")
        empresa = of.get("empresa", "Empresa TI")
        url_oferta = of.get("url_oferta", "")
        portal = of.get("portal", "Portal Chile")

        if esta_postulado(url_oferta=url_oferta, titulo=titulo, empresa=empresa):
            continue

        preguntas = of.get("preguntas") or [
            "¿Cuál es tu carrera, sede y situación académica actual en Duoc UC?",
            "¿Cuántas horas exige tu práctica profesional y cuentas con Seguro Escolar vigente?",
            "¿Cuál es tu pretensión de asignación / renta?",
            "¿Qué experiencia práctica tienes en infraestructura, redes, cloud, Linux/Windows y soporte?"
        ]

        respuestas_gen = {}
        faltaron = []

        for pr in preguntas:
            ok, r_text, req = resolver_pregunta_formulario(
                pr, perfil, buscar_respuesta_aprendida, of.get("descripcion", ""), modo=modo
            )
            if req:
                faltaron.append(pr)
                registrar_alerta_pendiente(empresa, titulo, pr, of.get("descripcion", ""))
            else:
                respuestas_gen[pr] = r_text

        enviada_pw = False
        detalle_metodo = "portal_asistido"
        if usar_playwright:
            enviada_pw, msg_pw = intentar_postulacion_playwright_persistente(of, perfil)
            if enviada_pw:
                confirmadas_auto += 1
                detalle_metodo = "playwright_confirmado"

        abrir_esta = abrir_en_brave and (not enviada_pw) and (pestanas_abiertas < max_pestanas_brave)
        if abrir_esta and url_oferta.startswith("http"):
            try:
                subprocess.Popen(["brave-browser", url_oferta], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                pestanas_abiertas += 1
                detalle_metodo = "abierta_en_brave"
                time.sleep(0.45)
            except Exception as e:
                errores.append(f"No se pudo abrir {url_oferta}: {e}")

        if enviada_pw:
            estado_final = "🟢 Postulado Confirmado"
        elif faltaron:
            estado_final = "🟡 Pausada (Falta dato)"
        elif abrir_esta:
            estado_final = "🟡 Postulado (Abierta en Brave)"
        else:
            estado_final = "🟡 Lista con IA (En Cola 1-Clic)"

        cv_match = obtener_cv_optimo(titulo, of.get("descripcion", ""))
        cv_nom = cv_match.get("archivo", "CV_Dhani_Elgueta.pdf")
        cv_esp = cv_match.get("nombre_especialidad", "Infraestructura")

        email_rec = of.get("email_reclutador") or ", ".join(of.get("emails_reclutador") or [])
        notas_auto = f"Score Duoc Infra: {of.get('score_duoc_infra', of.get('score_duoc', 90))}%. CV especializado: {cv_esp} ({cv_nom})."
        if email_rec:
            notas_auto += f" Correo reclutador detectado: {email_rec}"

        agregar_postulacion({
            "titulo": titulo,
            "empresa": empresa,
            "portal": portal,
            "url_oferta": url_oferta,
            "ubicacion": of.get("ubicacion", "Santiago, RM"),
            "modalidad": of.get("modalidad", "Híbrido / Presencial"),
            "asignacion_dinero": of.get("asignacion_dinero", "Asignación Práctica"),
            "descripcion": of.get("descripcion", ""),
            "fecha_oferta": of.get("fecha_publicacion") or of.get("fecha_oferta", datetime.now().strftime("%Y-%m-%d")),
            "fecha_postulacion": datetime.now().strftime("%Y-%m-%d"),
            "estado": estado_final,
            "respuestas_formulario": json.dumps(respuestas_gen, ensure_ascii=False),
            "notas": notas_auto,
            "score_duoc": int(of.get("score_duoc_infra") or of.get("score_duoc") or 90),
            "email_reclutador": email_rec,
            "modo_oferta": modo,
            "metodo_postulacion": detalle_metodo,
        })

        postuladas_count += 1

    return {
        "postuladas": postuladas_count,
        "confirmadas_playwright": confirmadas_auto,
        "pestanas_abiertas": pestanas_abiertas,
        "errores": errores,
    }
