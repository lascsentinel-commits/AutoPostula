import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "autopostula.db")

PORTALES_SOPORTADOS = [
    "DuocLaboral",
    "FirstJob",
    "Trabajando.cl",
    "LinkedIn Jobs",
    "Laborum Chile",
    "Computrabajo",
    "ChileTrabajos",
    "Get on Board",
    "Prácticas Chile (Estado)",
    "BNE (Gob.cl)",
    "Indeed Chile",
    "Reqlut Chile",
    "Talent.com (ATS Buk/AIRA)",
    "Empleos Públicos (Estado)",
]


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_alter(cur, sql):
    try:
        cur.execute(sql)
    except Exception:
        pass


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # 1. Perfil Maestro del postulante
    cur.execute("""
    CREATE TABLE IF NOT EXISTS perfil (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        nombre TEXT,
        rut TEXT DEFAULT '20.338.608-7',
        email TEXT,
        email_secundario TEXT DEFAULT 'correof1553@gmail.com',
        telefono TEXT,
        institucion TEXT DEFAULT 'Duoc UC',
        sede TEXT DEFAULT 'Sede Antonio Varas',
        jornada_estudios TEXT DEFAULT 'Vespertino',
        carrera TEXT DEFAULT 'Ingeniería en Infraestructura y Plataformas Tecnológicas',
        comuna TEXT DEFAULT 'Las Condes',
        region TEXT DEFAULT 'Región Metropolitana',
        disponibilidad TEXT DEFAULT 'Inmediata',
        renta_esperada INTEGER DEFAULT 0,
        renta_empleo INTEGER DEFAULT 950000,
        horas_requeridas INTEGER DEFAULT 360,
        nivel_ingles TEXT DEFAULT 'Intermedio B1',
        licencia_conducir TEXT DEFAULT 'Clase B',
        habilidades_tech TEXT,
        resumen_profesional TEXT,
        raw_cv_text TEXT,
        ruta_cv_pdf TEXT,
        updated_at TEXT
    );
    """)

    for col_def in [
        "ALTER TABLE perfil ADD COLUMN rut TEXT DEFAULT '20.338.608-7';",
        "ALTER TABLE perfil ADD COLUMN email_secundario TEXT DEFAULT 'correof1553@gmail.com';",
        "ALTER TABLE perfil ADD COLUMN sede TEXT DEFAULT 'Sede Antonio Varas';",
        "ALTER TABLE perfil ADD COLUMN jornada_estudios TEXT DEFAULT 'Vespertino';",
        "ALTER TABLE perfil ADD COLUMN renta_empleo INTEGER DEFAULT 950000;",
        "ALTER TABLE perfil ADD COLUMN licencia_conducir TEXT DEFAULT 'Clase B';",
    ]:
        _safe_alter(cur, col_def)

    # 2. Base de conocimientos / Respuestas aprendidas para formularios
    cur.execute("""
    CREATE TABLE IF NOT EXISTS respuestas_aprendidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pregunta_clave TEXT UNIQUE,
        respuesta TEXT,
        categoria TEXT DEFAULT 'general',
        veces_usada INTEGER DEFAULT 1,
        created_at TEXT
    );
    """)

    # 3. Historial de Postulaciones y Cola de Ofertas Reales
    cur.execute("""
    CREATE TABLE IF NOT EXISTS postulaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        empresa TEXT NOT NULL,
        portal TEXT NOT NULL,
        url_oferta TEXT,
        ubicacion TEXT,
        modalidad TEXT,
        asignacion_dinero TEXT,
        descripcion TEXT,
        fecha_oferta TEXT,
        fecha_postulacion TEXT,
        estado TEXT DEFAULT '🟡 Postulado',
        respuestas_formulario TEXT,
        notas TEXT,
        score_duoc INTEGER DEFAULT 85,
        email_reclutador TEXT DEFAULT '',
        modo_oferta TEXT DEFAULT 'practica_duoc',
        metodo_postulacion TEXT DEFAULT 'portal_asistido',
        created_at TEXT
    );
    """)

    for col_def in [
        "ALTER TABLE postulaciones ADD COLUMN score_duoc INTEGER DEFAULT 85;",
        "ALTER TABLE postulaciones ADD COLUMN email_reclutador TEXT DEFAULT '';",
        "ALTER TABLE postulaciones ADD COLUMN modo_oferta TEXT DEFAULT 'practica_duoc';",
        "ALTER TABLE postulaciones ADD COLUMN metodo_postulacion TEXT DEFAULT 'portal_asistido';",
    ]:
        _safe_alter(cur, col_def)

    # 4. Alertas pendientes (cuando falta un dato)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS alertas_pendientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        postulacion_id INTEGER,
        empresa TEXT,
        cargo TEXT,
        pregunta TEXT NOT NULL,
        contexto_oferta TEXT,
        estado TEXT DEFAULT 'pendiente',
        created_at TEXT
    );
    """)

    # 5. Configuración de filtros para prácticas y empleos ("cualquier pega o práctica")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS filtros_practica (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        modo_busqueda TEXT DEFAULT 'practica_duoc',
        termino_personalizado TEXT DEFAULT 'infraestructura plataformas soporte redes cloud',
        palabras_clave TEXT DEFAULT 'práctica, practicante, pasantía, alumno en práctica, internship, trainee',
        palabras_combinadas TEXT DEFAULT 'infraestructura, plataformas, redes, cisco, servidores, linux, windows server, active directory, cloud, aws, azure, terraform, docker, kubernetes, ciberseguridad, seguridad ti, soc, soporte ti, sysadmin, operaciones ti, continuidad operacional, telecomunicaciones, conectividad, virtualización, zabbix, hardware',
        palabras_excluir TEXT DEFAULT 'senior, semi-senior, ssr, jefe, gerente, subgerente, director, 3 años de experiencia, 5 años de experiencia, educación media',
        areas_seleccionadas TEXT DEFAULT 'Ingeniería en Infraestructura y Plataformas Tecnológicas, Cloud & DevOps, Redes y Telecomunicaciones, Ciberseguridad & SOC, Administración de Servidores Linux/Windows, Soporte TI Avanzado',
        portales_activos TEXT,
        modalidad_preferida TEXT DEFAULT 'Todas',
        solo_rm_o_remoto INTEGER DEFAULT 1,
        solo_remuneradas INTEGER DEFAULT 0,
        renta_minima INTEGER DEFAULT 0,
        updated_at TEXT
    );
    """)

    default_portales_json = json.dumps(PORTALES_SOPORTADOS, ensure_ascii=False)
    for col_def in [
        "ALTER TABLE filtros_practica ADD COLUMN palabras_combinadas TEXT DEFAULT 'infraestructura, plataformas, redes, cisco, servidores, linux, windows server, active directory, cloud, aws, azure, terraform, docker, kubernetes, ciberseguridad, seguridad ti, soc, soporte ti, sysadmin, operaciones ti, continuidad operacional, telecomunicaciones, conectividad, virtualización, zabbix, hardware';",
        "ALTER TABLE filtros_practica ADD COLUMN modo_busqueda TEXT DEFAULT 'practica_duoc';",
        "ALTER TABLE filtros_practica ADD COLUMN termino_personalizado TEXT DEFAULT 'infraestructura plataformas soporte redes cloud';",
        f"ALTER TABLE filtros_practica ADD COLUMN portales_activos TEXT DEFAULT '{default_portales_json}';",
        "ALTER TABLE filtros_practica ADD COLUMN solo_rm_o_remoto INTEGER DEFAULT 1;",
    ]:
        _safe_alter(cur, col_def)

    # 6. Catálogo técnico recolectado de cada portal (DOM selectors, endpoints, tipo de postulación)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS portales_catalogo (
        nombre TEXT PRIMARY KEY,
        url_base TEXT,
        tipo_extraccion TEXT,
        soporta_practicas INTEGER DEFAULT 1,
        soporta_empleos INTEGER DEFAULT 1,
        requiere_sesion_postular INTEGER DEFAULT 1,
        selectores_dom TEXT,
        notas_tecnicas TEXT,
        ultimo_conteo INTEGER DEFAULT 0,
        ultimo_estado TEXT DEFAULT 'OK',
        updated_at TEXT
    );
    """)

    # Crear o asegurar perfil base con la carrera exacta de Duoc UC
    cur.execute("SELECT id, carrera FROM perfil WHERE id = 1;")
    row_p = cur.fetchone()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not row_p:
        cur.execute("""
        INSERT INTO perfil (
            id, nombre, rut, email, email_secundario, telefono, institucion, sede, jornada_estudios,
            carrera, comuna, region, disponibilidad, renta_esperada, renta_empleo, horas_requeridas,
            nivel_ingles, licencia_conducir, habilidades_tech, resumen_profesional, updated_at
        ) VALUES (
            1, 'Dhani Amit Elgueta Ríos', '20.338.608-7', 'dh.elgueta@duocuc.cl', 'correof1553@gmail.com',
            '+56 9 4850 8528', 'Duoc UC', 'Sede Antonio Varas', 'Vespertino',
            'Ingeniería en Infraestructura y Plataformas Tecnológicas', 'Las Condes', 'Región Metropolitana',
            'Inmediata', 0, 950000, 360, 'Intermedio B1', 'Clase B',
            'Linux (RHEL, Oracle Linux, Ubuntu, Debian), Windows Server, Active Directory, Microsoft 365, Azure AD, AWS, Terraform, Ansible, Docker, Kubernetes, Redes Cisco, Firewalls, Zabbix, Prometheus, Grafana, Wazuh, Suricata, Zeek, SOAR LZOC, Python, Bash, PowerShell, PostgreSQL, Oracle 23ai, Soporte Hardware y Microsoldadura',
            'Estudiante de último semestre de Ingeniería en Infraestructura y Plataformas Tecnológicas en Duoc UC (Sede Antonio Varas, vespertino). Restan únicamente 360 horas de Práctica Profesional y 3 asignaturas vespertinas para titulación. Especialista en continuidad operacional, servidores Linux/Windows, cloud AWS con Terraform, observabilidad Zabbix/Grafana, ciberseguridad Wazuh/Zeek y soporte TI corporativo.',
            ?
        );
        """, (now,))
    else:
        cur.execute("""
        UPDATE perfil
        SET carrera = 'Ingeniería en Infraestructura y Plataformas Tecnológicas',
            institucion = COALESCE(NULLIF(institucion, ''), 'Duoc UC'),
            rut = COALESCE(NULLIF(rut, ''), '20.338.608-7'),
            email_secundario = COALESCE(NULLIF(email_secundario, ''), 'correof1553@gmail.com'),
            sede = COALESCE(NULLIF(sede, ''), 'Sede Antonio Varas'),
            jornada_estudios = COALESCE(NULLIF(jornada_estudios, ''), 'Vespertino'),
            licencia_conducir = COALESCE(NULLIF(licencia_conducir, ''), 'Clase B'),
            horas_requeridas = COALESCE(horas_requeridas, 360)
        WHERE id = 1;
        """)

    # Crear filtros base si no existen
    cur.execute("SELECT id, portales_activos FROM filtros_practica WHERE id = 1;")
    row_f = cur.fetchone()
    if not row_f:
        cur.execute("""
        INSERT INTO filtros_practica (id, portales_activos, updated_at) VALUES (1, ?, ?);
        """, (default_portales_json, now))
    elif not row_f["portales_activos"]:
        cur.execute("UPDATE filtros_practica SET portales_activos = ? WHERE id = 1;", (default_portales_json,))

    # 7. Configuración de Piloto Automático / Scheduler
    cur.execute("""
    CREATE TABLE IF NOT EXISTS configuracion_scheduler (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        activo INTEGER DEFAULT 0,
        horarios TEXT DEFAULT '01:00, 04:00, 06:30, 08:00, 12:00, 14:00, 17:00, 22:00',
        ultimo_escaneo TEXT,
        proximo_escaneo TEXT,
        total_autopostuladas INTEGER DEFAULT 0,
        motivo_detencion TEXT,
        updated_at TEXT
    );
    """)

    # 8. Historial de logs del Scheduler
    cur.execute("""
    CREATE TABLE IF NOT EXISTS scheduler_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_hora TEXT,
        ofertas_encontradas INTEGER,
        ofertas_postuladas INTEGER,
        detalle TEXT
    );
    """)

    cur.execute("SELECT id FROM configuracion_scheduler WHERE id = 1;")
    if not cur.fetchone():
        cur.execute("""
        INSERT INTO configuracion_scheduler (id, activo, horarios, updated_at)
        VALUES (1, 0, '01:00, 04:00, 06:30, 08:00, 12:00, 14:00, 17:00, 22:00', ?);
        """, (now,))

    conn.commit()
    conn.close()
    inicializar_catalogo_portales()
    seed_initial_data_if_empty()


def seed_initial_data_if_empty():
    """Importa respuestas_aprendidas y ofertas semilla si la base de datos está vacía."""
    conn = get_conn()
    cur = conn.cursor()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    seed_dir = os.path.join(base_dir, "data_seed")

    # 1. Respuestas aprendidas
    cur.execute("SELECT COUNT(*) FROM respuestas_aprendidas")
    if cur.fetchone()[0] == 0:
        resp_file = os.path.join(seed_dir, "respuestas_aprendidas.json")
        if os.path.exists(resp_file):
            try:
                with open(resp_file, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    for item in items:
                        cur.execute("""
                        INSERT OR IGNORE INTO respuestas_aprendidas (pregunta_clave, respuesta, categoria, veces_usada, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """, (item["pregunta_clave"], item["respuesta"], item.get("categoria", "general"), item.get("veces_usada", 1), item.get("created_at", "")))
                conn.commit()
            except Exception as e:
                print(f"Aviso al cargar respuestas aprendidas semilla: {e}")

    # 2. Ofertas en cola
    cur.execute("SELECT COUNT(*) FROM postulaciones")
    if cur.fetchone()[0] == 0:
        ofertas_file = os.path.join(seed_dir, "ofertas_en_cola.json")
        if os.path.exists(ofertas_file):
            try:
                with open(ofertas_file, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    for item in items:
                        cur.execute("""
                        INSERT OR IGNORE INTO postulaciones (
                            portal, external_id, url_oferta, empresa, cargo,
                            descripcion, modalidad, renta, estado, fecha_detectada, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            item.get("portal", ""), item.get("external_id", ""), item.get("url_oferta", ""),
                            item.get("empresa", ""), item.get("cargo", ""), item.get("descripcion", ""),
                            item.get("modalidad", ""), item.get("renta", 0), item.get("estado", "🟡 Lista con IA (En Cola 1-Clic)"),
                            item.get("fecha_detectada", ""), item.get("updated_at", "")
                        ))
                conn.commit()
            except Exception as e:
                print(f"Aviso al cargar ofertas semilla: {e}")

    conn.close()


def inicializar_catalogo_portales():
    """Registra la arquitectura técnica real recolectada de los 14 portales integrados."""
    catalogo = [
        ("DuocLaboral", "https://duoclaboral.cl", "HTTP Live + Sesión SSO Reqlut/Duoc", 1, 1, 1,
         "button:has-text('Postular ahora'), .form-group textarea, input[name*='answer']",
         "Bolsa oficial Duoc UC sobre motor Reqlut. Valida convenio directo y Seguro Escolar Ley 16.744."),
        ("FirstJob", "https://firstjob.me/ofertas", "SSR HTML Query (country[]=43, title=...)", 1, 1, 1,
         "a:has-text('Postular'), button:has-text('Postular'), textarea, select",
         "Portal #1 en Chile de prácticas profesionales corporativas (Transelec, Enex, Aramark, Itaú, Banco Ripley, Tanner, CCU)."),
        ("Trabajando.cl", "https://www.trabajando.cl", "REST JSON API (/api/searchjob + /api/ofertas/{id})", 1, 1, 1,
         "button:has-text('Postular'), [id*='pregunta'], textarea",
         "API oficial devuelve slug (/trabajo/{slug}), sueldo y arreglo exacto de preguntas de filtro del reclutador."),
        ("LinkedIn Jobs", "https://cl.linkedin.com/jobs", "Guest Search API (/jobs-guest/jobs/api/seeMoreJobPostings/search)", 1, 1, 1,
         "button.jobs-apply-button, div.jobs-easy-apply-modal input, textarea, select",
         "Consulta pública en tiempo real sin bloqueo para Chile con filtro temporal y Easy Apply / ATS corporativo."),
        ("Laborum Chile", "https://www.laborum.cl", "Playwright Headless Brave + API searchV2", 1, 1, 1,
         "button:has-text('Postularme'), input[name*='salary'], textarea",
         "Alto volumen de prácticas y cargos de Seguridad TI, Redes, Soporte e Infraestructura en RM."),
        ("Computrabajo", "https://cl.computrabajo.com", "SSR HTML Scraper (article.box_offer)", 1, 1, 1,
         "a:has-text('Postularme'), button:has-text('Postularme'), textarea, input[type='radio']",
         "Gran volumen diario de prácticas de Soporte TI, Redes, Telecomunicaciones e Informática en Santiago."),
        ("ChileTrabajos", "https://www.chiletrabajos.cl", "SSR HTML Scraper (param 2=query & 13=1022 RM)", 1, 1, 1,
         "a:has-text('Postular'), textarea[name*='carta'], input[type='file']",
         "Portal nacional con avisos directos de empresas TI chilenas; frecuentemente incluye correo directo del reclutador."),
        ("Get on Board", "https://www.getonbrd.com", "Official Public JSON API (/api/v0/search/jobs)", 1, 1, 1,
         "a[href*='#apply'], textarea[name*='cover_letter'], input[type='file']",
         "Principal portal tech/startups en Chile y remoto LatAm para DevOps, Cloud, SysAdmin, Ciberseguridad y Prácticas."),
        ("Prácticas Chile (Estado)", "https://www.practicaschile.cl", "Servicio Civil Elastic API (listado_practicas2/_search)", 1, 0, 1,
         "a:has-text('Iniciar sesión'), ClaveÚnica + correo institucional de contacto",
         "Portal oficial del Estado de Chile para prácticas de Educación Superior Profesional en Ministerios y Servicios Públicos."),
        ("BNE (Gob.cl)", "https://www.bne.gob.cl/buscar-empleo", "Playwright Headless + API /api/ofertas/busqueda", 1, 1, 1,
         "a[href*='/ofertas/'], button:has-text('Postular'), ClaveÚnica",
         "Bolsa Nacional de Empleo oficial del Ministerio del Trabajo con ofertas públicas y privadas en todo Chile."),
        ("Indeed Chile", "https://cl.indeed.com", "Playwright Headless Brave (div.job_seen_beacon)", 1, 1, 1,
         "button#indeedApplyButton, a:has-text('Postularse en el sitio de la empresa')",
         "Agregador global que captura ofertas directas de empresas y consultoras TI en Santiago."),
        ("Reqlut Chile", "https://reqlut.com/trabajo/trabajos-en-chile", "SSR HTML (Search[jobOfferType]=1 Prácticas / 0 Empleos)", 1, 1, 1,
         "button:has-text('Postular'), .form-group textarea, input[type='checkbox']",
         "Red abierta de portales universitarios y empresas en Chile con formulario unificado Reqlut."),
        ("Talent.com (ATS Buk/AIRA)", "https://cl.talent.com", "SSR HTML Aggregator de ATS Empresariales", 1, 1, 0,
         "input[type='file'], input[name*='name'], input[name*='email'], input[name*='phone']",
         "Indexa portales corporativos directos sobre Buk, AIRA (airavirtual.com), Workday, Teamtailor, Greenhouse y Lever."),
        ("Empleos Públicos (Estado)", "https://www.empleospublicos.cl", "Portal Servicio Civil Convocatorias Profesionales", 0, 1, 1,
         "a:has-text('Postular'), ClaveÚnica Servicio Civil",
         "Convocatorias profesionales y técnicas en infraestructura TI, soporte, redes y sistemas en organismos del Estado."),
    ]
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for row in catalogo:
        cur.execute("""
        INSERT INTO portales_catalogo (
            nombre, url_base, tipo_extraccion, soporta_practicas, soporta_empleos,
            requiere_sesion_postular, selectores_dom, notas_tecnicas, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(nombre) DO UPDATE SET
            url_base = excluded.url_base,
            tipo_extraccion = excluded.tipo_extraccion,
            soporta_practicas = excluded.soporta_practicas,
            soporta_empleos = excluded.soporta_empleos,
            requiere_sesion_postular = excluded.requiere_sesion_postular,
            selectores_dom = excluded.selectores_dom,
            notas_tecnicas = excluded.notas_tecnicas,
            updated_at = excluded.updated_at;
        """, (*row, now))
    conn.commit()
    conn.close()


def actualizar_conteo_portal(nombre: str, conteo: int, estado: str = "OK"):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
    UPDATE portales_catalogo
    SET ultimo_conteo = ?, ultimo_estado = ?, updated_at = ?
    WHERE nombre = ?;
    """, (conteo, estado, now, nombre))
    conn.commit()
    conn.close()


def obtener_catalogo_portales():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM portales_catalogo ORDER BY soporta_practicas DESC, nombre ASC;")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def obtener_perfil():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM perfil WHERE id = 1;")
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {}


def guardar_perfil(datos):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
    UPDATE perfil SET
        nombre = coalesce(?, nombre),
        rut = coalesce(?, rut),
        email = coalesce(?, email),
        email_secundario = coalesce(?, email_secundario),
        telefono = coalesce(?, telefono),
        institucion = coalesce(?, institucion),
        sede = coalesce(?, sede),
        jornada_estudios = coalesce(?, jornada_estudios),
        carrera = coalesce(?, carrera),
        comuna = coalesce(?, comuna),
        region = coalesce(?, region),
        disponibilidad = coalesce(?, disponibilidad),
        renta_esperada = coalesce(?, renta_esperada),
        renta_empleo = coalesce(?, renta_empleo),
        horas_requeridas = coalesce(?, horas_requeridas),
        nivel_ingles = coalesce(?, nivel_ingles),
        licencia_conducir = coalesce(?, licencia_conducir),
        habilidades_tech = coalesce(?, habilidades_tech),
        resumen_profesional = coalesce(?, resumen_profesional),
        raw_cv_text = coalesce(?, raw_cv_text),
        ruta_cv_pdf = coalesce(?, ruta_cv_pdf),
        updated_at = ?
    WHERE id = 1;
    """, (
        datos.get("nombre"), datos.get("rut"), datos.get("email"), datos.get("email_secundario"),
        datos.get("telefono"), datos.get("institucion"), datos.get("sede"), datos.get("jornada_estudios"),
        datos.get("carrera"), datos.get("comuna"), datos.get("region"), datos.get("disponibilidad"),
        datos.get("renta_esperada"), datos.get("renta_empleo"), datos.get("horas_requeridas"),
        datos.get("nivel_ingles"), datos.get("licencia_conducir"), datos.get("habilidades_tech"),
        datos.get("resumen_profesional"), datos.get("raw_cv_text"), datos.get("ruta_cv_pdf"),
        now
    ))
    conn.commit()
    conn.close()


def obtener_filtros():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM filtros_practica WHERE id = 1;")
    row = cur.fetchone()
    conn.close()
    d = dict(row) if row else {}
    try:
        d["portales_lista"] = json.loads(d.get("portales_activos") or "[]") or list(PORTALES_SOPORTADOS)
    except Exception:
        d["portales_lista"] = list(PORTALES_SOPORTADOS)
    return d


def guardar_filtros(datos):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current = obtener_filtros()
    portales_json = datos.get("portales_activos")
    if isinstance(portales_json, list):
        portales_json = json.dumps(portales_json, ensure_ascii=False)
    elif portales_json is None:
        portales_json = json.dumps(current.get("portales_lista", PORTALES_SOPORTADOS), ensure_ascii=False)

    cur.execute("""
    UPDATE filtros_practica SET
        modo_busqueda = ?,
        termino_personalizado = ?,
        palabras_clave = ?,
        palabras_combinadas = ?,
        palabras_excluir = ?,
        areas_seleccionadas = ?,
        portales_activos = ?,
        modalidad_preferida = ?,
        solo_rm_o_remoto = ?,
        solo_remuneradas = ?,
        renta_minima = ?,
        updated_at = ?
    WHERE id = 1;
    """, (
        datos.get("modo_busqueda", current.get("modo_busqueda", "practica_duoc")),
        datos.get("termino_personalizado", current.get("termino_personalizado", "infraestructura plataformas soporte redes cloud")),
        datos.get("palabras_clave", current.get("palabras_clave", "")),
        datos.get("palabras_combinadas", current.get("palabras_combinadas", "")),
        datos.get("palabras_excluir", current.get("palabras_excluir", "")),
        datos.get("areas_seleccionadas", current.get("areas_seleccionadas", "")),
        portales_json,
        datos.get("modalidad_preferida", current.get("modalidad_preferida", "Todas")),
        int(datos.get("solo_rm_o_remoto", current.get("solo_rm_o_remoto", 1))),
        int(datos.get("solo_remuneradas", current.get("solo_remuneradas", 0))),
        int(datos.get("renta_minima", current.get("renta_minima", 0))),
        now
    ))
    conn.commit()
    conn.close()


def obtener_postulaciones(filtro_estado=None, filtro_portal=None):
    conn = get_conn()
    cur = conn.cursor()
    clauses = []
    params = []
    if filtro_estado and filtro_estado != "Todos":
        clauses.append("estado = ?")
        params.append(filtro_estado)
    if filtro_portal and filtro_portal != "Todos":
        clauses.append("portal = ?")
        params.append(filtro_portal)
    where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    cur.execute(f"SELECT * FROM postulaciones {where_sql} ORDER BY id DESC;", tuple(params))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def agregar_postulacion(datos):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
    INSERT INTO postulaciones (
        titulo, empresa, portal, url_oferta, ubicacion, modalidad,
        asignacion_dinero, descripcion, fecha_oferta, fecha_postulacion,
        estado, respuestas_formulario, notas, score_duoc, email_reclutador,
        modo_oferta, metodo_postulacion, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        datos.get("titulo"), datos.get("empresa"), datos.get("portal"),
        datos.get("url_oferta"), datos.get("ubicacion"), datos.get("modalidad"),
        datos.get("asignacion_dinero"), datos.get("descripcion"),
        datos.get("fecha_oferta", now[:10]), datos.get("fecha_postulacion", now[:10]),
        datos.get("estado", "🟡 Postulado"), datos.get("respuestas_formulario", "{}"),
        datos.get("notas", ""), int(datos.get("score_duoc", 85)),
        datos.get("email_reclutador", ""), datos.get("modo_oferta", "practica_duoc"),
        datos.get("metodo_postulacion", "portal_asistido"), now
    ))
    nuevo_id = cur.lastrowid
    conn.commit()
    conn.close()
    return nuevo_id


def actualizar_estado_postulacion(postulacion_id, nuevo_estado, notas=None):
    conn = get_conn()
    cur = conn.cursor()
    if notas is not None:
        cur.execute("UPDATE postulaciones SET estado = ?, notas = ? WHERE id = ?;", (nuevo_estado, notas, postulacion_id))
    else:
        cur.execute("UPDATE postulaciones SET estado = ? WHERE id = ?;", (nuevo_estado, postulacion_id))
    conn.commit()
    conn.close()


def obtener_alertas_pendientes():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM alertas_pendientes WHERE estado = 'pendiente' ORDER BY id ASC;")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def registrar_alerta_pendiente(empresa, cargo, pregunta, contexto_oferta=""):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("SELECT id FROM alertas_pendientes WHERE LOWER(pregunta) = LOWER(?) AND estado = 'pendiente' LIMIT 1;", (pregunta.strip(),))
    ex = cur.fetchone()
    if ex:
        conn.close()
        return ex["id"]
    cur.execute("""
    INSERT INTO alertas_pendientes (empresa, cargo, pregunta, contexto_oferta, estado, created_at)
    VALUES (?, ?, ?, ?, 'pendiente', ?);
    """, (empresa, cargo, pregunta, contexto_oferta, now))
    alerta_id = cur.lastrowid
    conn.commit()
    conn.close()
    return alerta_id


def resolver_alerta_y_aprender(alerta_id, pregunta, respuesta, categoria="general"):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("UPDATE alertas_pendientes SET estado = 'respondida' WHERE id = ?;", (alerta_id,))
    cur.execute("""
    INSERT INTO respuestas_aprendidas (pregunta_clave, respuesta, categoria, veces_usada, created_at)
    VALUES (?, ?, ?, 1, ?)
    ON CONFLICT(pregunta_clave) DO UPDATE SET
        respuesta = excluded.respuesta,
        veces_usada = veces_usada + 1;
    """, (pregunta.strip().lower(), respuesta.strip(), categoria, now))
    conn.commit()
    conn.close()


def _limpiar_clave_pregunta(pregunta: str) -> str:
    import re
    p = (pregunta or "").strip().lower()
    p = re.sub(r"^(pregunta\s*\d+\s*[:\.\-]?)", "", p).strip()
    p = re.sub(r"\s+", " ", p)
    return p


def guardar_o_actualizar_respuesta(pregunta_clave: str, respuesta: str, categoria: str = "general", item_id: int = None) -> int:
    """Crea o actualiza una respuesta en la memoria aprendida de AutoPostula."""
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clave = _limpiar_clave_pregunta(pregunta_clave)
    resp_clean = (respuesta or "").strip()

    if item_id:
        cur.execute("""
        UPDATE respuestas_aprendidas
        SET pregunta_clave = ?, respuesta = ?, categoria = ?
        WHERE id = ?;
        """, (clave, resp_clean, categoria, int(item_id)))
        res_id = int(item_id)
    else:
        cur.execute("""
        INSERT INTO respuestas_aprendidas (pregunta_clave, respuesta, categoria, veces_usada, created_at)
        VALUES (?, ?, ?, 1, ?)
        ON CONFLICT(pregunta_clave) DO UPDATE SET
            respuesta = excluded.respuesta,
            categoria = CASE WHEN excluded.categoria != 'general' THEN excluded.categoria ELSE respuestas_aprendidas.categoria END,
            veces_usada = veces_usada + 1;
        """, (clave, resp_clean, categoria, now))
        cur.execute("SELECT id FROM respuestas_aprendidas WHERE pregunta_clave = ? LIMIT 1;", (clave,))
        row = cur.fetchone()
        res_id = row["id"] if row else cur.lastrowid

    conn.commit()
    conn.close()
    return res_id


def eliminar_respuesta_aprendida(item_id: int) -> bool:
    """Elimina una pregunta/respuesta de la memoria del bot."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM respuestas_aprendidas WHERE id = ?;", (int(item_id),))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def buscar_respuesta_aprendida(pregunta):
    """Busca si existe una respuesta aprendida (exacta, contenida o por alta similitud semántica de palabras clave)."""
    import re
    conn = get_conn()
    cur = conn.cursor()
    p_clean = _limpiar_clave_pregunta(pregunta)
    if not p_clean:
        conn.close()
        return None

    # 1. Coincidencia exacta
    cur.execute("SELECT respuesta FROM respuestas_aprendidas WHERE pregunta_clave = ? LIMIT 1;", (p_clean,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row["respuesta"]

    # 2. Coincidencia por subcadena directa
    cur.execute("SELECT pregunta_clave, respuesta FROM respuestas_aprendidas ORDER BY LENGTH(pregunta_clave) DESC;")
    all_rows = cur.fetchall()
    conn.close()

    for r in all_rows:
        clave = (r["pregunta_clave"] or "").strip().lower()
        if clave and (clave in p_clean or p_clean in clave) and len(clave) >= 8:
            return r["respuesta"]

    # 3. Coincidencia por similitud de tokens significativos (>= 70% de coincidencia)
    stopwords = {"de", "la", "el", "los", "las", "en", "para", "por", "con", "y", "o", "a", "un", "una", "tu", "su", "al", "del", "que", "qué", "cuál", "cual", "cuanto", "cuánto", "como", "cómo", "tienes", "cuentas", "puedes", "si", "no"}
    tokens_p = set(re.findall(r"[a-záéíóúñ0-9]+", p_clean)) - stopwords
    if len(tokens_p) >= 2:
        mejor_score = 0.0
        mejor_resp = None
        for r in all_rows:
            clave = (r["pregunta_clave"] or "").strip().lower()
            tokens_c = set(re.findall(r"[a-záéíóúñ0-9]+", clave)) - stopwords
            if len(tokens_c) < 2:
                continue
            inter = tokens_p.intersection(tokens_c)
            union = tokens_p.union(tokens_c)
            sim = len(inter) / max(1, min(len(tokens_p), len(tokens_c)))
            jaccard = len(inter) / max(1, len(union))
            if sim >= 0.75 and jaccard >= 0.45 and sim > mejor_score:
                mejor_score = sim
                mejor_resp = r["respuesta"]
        if mejor_resp:
            return mejor_resp

    return None


def esta_postulado(url_oferta=None, titulo=None, empresa=None) -> bool:
    """Verifica si ya existe una postulación registrada para esta oferta."""
    conn = get_conn()
    cur = conn.cursor()
    if url_oferta and len(url_oferta.strip()) > 5:
        u_clean = url_oferta.strip().split("?")[0].rstrip("/")
        cur.execute("SELECT id FROM postulaciones WHERE RTRIM(SUBSTR(url_oferta, 1, CASE WHEN INSTR(url_oferta, '?') > 0 THEN INSTR(url_oferta, '?') - 1 ELSE LENGTH(url_oferta) END), '/') = ? LIMIT 1;", (u_clean,))
        if cur.fetchone():
            conn.close()
            return True

    if titulo and empresa and empresa.lower() not in ("empresa confidencial", "empresa computrabajo", "empresa laborum", "empresa en portal"):
        cur.execute("SELECT id FROM postulaciones WHERE LOWER(titulo) = LOWER(?) AND LOWER(empresa) = LOWER(?) LIMIT 1;", (titulo.strip(), empresa.strip()))
        if cur.fetchone():
            conn.close()
            return True

    conn.close()
    return False


def obtener_respuestas_aprendidas():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM respuestas_aprendidas ORDER BY veces_usada DESC, id DESC;")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def obtener_estado_scheduler():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM configuracion_scheduler WHERE id = 1;")
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {
        "activo": 0,
        "horarios": "01:00, 04:00, 06:30, 08:00, 12:00, 14:00, 17:00, 22:00",
        "ultimo_escaneo": "Nunca",
        "proximo_escaneo": "Pendiente de activación",
        "total_autopostuladas": 0,
        "motivo_detencion": ""
    }


def guardar_estado_scheduler(activo: int, horarios: str = None, motivo_detencion: str = "", proximo_escaneo: str = None, incremento_postuladas: int = 0):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    current = obtener_estado_scheduler()
    h_val = horarios if horarios is not None else current.get("horarios", "01:00, 04:00, 06:30, 08:00, 12:00, 14:00, 17:00, 22:00")
    p_val = proximo_escaneo if proximo_escaneo is not None else current.get("proximo_escaneo", "")
    tot_val = (current.get("total_autopostuladas") or 0) + incremento_postuladas

    cur.execute("""
    UPDATE configuracion_scheduler
    SET activo = ?, horarios = ?, motivo_detencion = ?, proximo_escaneo = ?, total_autopostuladas = ?, updated_at = ?
    WHERE id = 1;
    """, (activo, h_val, motivo_detencion, p_val, tot_val, now))
    conn.commit()
    conn.close()


def actualizar_ultimo_escaneo_scheduler(proximo_escaneo: str, incremento_postuladas: int = 0):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current = obtener_estado_scheduler()
    tot_val = (current.get("total_autopostuladas") or 0) + incremento_postuladas

    cur.execute("""
    UPDATE configuracion_scheduler
    SET ultimo_escaneo = ?, proximo_escaneo = ?, total_autopostuladas = ?, updated_at = ?
    WHERE id = 1;
    """, (now, proximo_escaneo, tot_val, now))
    conn.commit()
    conn.close()


def registrar_log_scheduler(ofertas_encontradas: int, ofertas_postuladas: int, detalle: str):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
    INSERT INTO scheduler_logs (fecha_hora, ofertas_encontradas, ofertas_postuladas, detalle)
    VALUES (?, ?, ?, ?);
    """, (now, ofertas_encontradas, ofertas_postuladas, detalle))
    conn.commit()
    conn.close()


def obtener_logs_scheduler(limit: int = 25):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM scheduler_logs ORDER BY id DESC LIMIT ?;", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
