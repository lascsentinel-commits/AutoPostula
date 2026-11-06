import re


def sanitizar_texto_seguro(texto: str) -> str:
    """
    Blindaje contra Prompt Injection y caracteres peligrosos desde formularios externos.
    """
    if not texto:
        return ""

    limpio = re.sub(r"<[^>]*>", "", texto)

    patrones_injection = [
        r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"(?i)disregard\s+(all\s+)?guidelines",
        r"(?i)olvida\s+(todas\s+las\s+)?instrucciones(\s+anteriores)?",
        r"(?i)ignora\s+(las\s+)?instrucciones(\s+anteriores)?",
        r"(?i)system\s*prompt",
        r"(?i)prompt\s*injection",
        r"(?i)act\s+as\s+a\b",
        r"(?i)hazte\s+pasar\s+por\b",
        r"(?i)now\s+you\s+are\b",
        r"(?i)reveal\s+your\s+(secret|instructions|system)",
        r"(?i)muestra\s+tu\s+prompt",
        r"(?i)base64",
        r"```[a-z]*",
        r"---+"
    ]

    for pat in patrones_injection:
        limpio = re.sub(pat, "[FILTRADO_SEGURIDAD]", limpio)

    return limpio.strip()[:1200]


# Regiones fuera de la RM para filtro geográfico opcional cuando la oferta no es remota
REGIONES_FUERA_RM = [
    "valdivia", "antofagasta", "iquique", "tarapacá", "coquimbo", "ovalle", "la serena",
    "los lagos", "puerto montt", "osorno", "concepción", "biobío", "talcahuano",
    "temuco", "araucanía", "ñuble", "chillán", "magallanes", "punta arenas", "aysén",
    "atacama", "copiapó", "arica", "calama", "curauma", "valparaíso", "viña del mar",
    "quilpué", "rancagua", "talca", "maule", "curicó", "los ángeles"
]

CARRERAS_AJENAS = [
    "contador", "auditor contable", "contabilidad", "contable",
    "enfermería", "enfermero", "médico", "tens", "nutrición", "química y farmacia", "asuntos regulatorios",
    "cocinero", "cocina", "garzón", "garzona", "barista",
    "aseo", "limpieza", "manicurista", "pedicurista", "estética",
    "mecánico automotriz", "maquinaria pesada", "electromecánica", "topógrafo", "topografo", "construcción civil",
    "cajera", "cajero", "vendedor", "ejecutivo de ventas", "sales intern", "sales specialist",
    "recursos humanos", "reclutamiento y selección", "psicólogo", "psicología", "trabajo social",
    "abogado", "asesoría jurídica", "periodismo", "redes sociales", "community manager",
    "prevención de riesgos", "ingeniero en alimentos", "agronomía", "educación media"
]

PATRONES_PRACTICA = [
    r"pr[áa]ctica", r"practicante", r"pasant[íi]a", r"alumno[s/\-a]*\s+en\s+pr[áa]ctica",
    r"internship", r"\bintern\b", r"programa\s+de\s+pr[áa]cticas"
]

PATRONES_INFRA_DUOC = [
    r"infraestructura", r"plataforma[s]?", r"cloud", r"nube", r"aws", r"azure", r"gcp",
    r"redes", r"conectividad", r"telecomunicaciones", r"telem[áa]tica", r"cisco",
    r"servidor(es)?", r"sysadmin", r"linux", r"windows\s*server", r"active\s*directory",
    r"ciberseguridad", r"seguridad\s*(ti|inform[áa]tica|de\s+la\s+informaci[óo]n)", r"\bsoc\b",
    r"operaciones\s*ti", r"continuidad\s*operacional", r"virtualizaci[óo]n", r"devops",
    r"datacenter", r"data\s*center", r"soporte\s*(ti|it|t[ée]cnico|computacional|inform[áa]tico|n1|n2|sistemas|operacional)?",
    r"mesa\s+de\s+ayuda", r"help\s*desk", r"sistemas", r"inform[áa]tica", r"computaci[óo]n", r"\bti\b", r"\bit\b"
]


def evaluar_oferta_inteligente(oferta: dict, filtros: dict) -> tuple[bool, str, int]:
    """
    Evalúa si una oferta es admisible según el modo seleccionado:
    - 'practica_duoc': Práctica Profesional compatible con Ingeniería en Infraestructura y Plataformas Tecnológicas (Duoc UC, 360h).
    - 'empleo_ti': Cualquier pega / empleo formal TI o término personalizado sin exigir ser práctica.
    - 'ambos': Admite tanto prácticas Duoc UC como empleos TI / término personalizado.
    Retorna (aprobada: bool, motivo: str, score: int).
    """
    modo = filtros.get("modo_busqueda", "practica_duoc")
    titulo = (oferta.get("titulo") or "").lower()
    desc = (oferta.get("descripcion") or "").lower()
    ubic = (oferta.get("ubicacion") or "").lower()
    mod_oferta = (oferta.get("modalidad") or "").lower()
    texto_completo = f"{titulo} {desc}"

    # 1. Filtro Geográfico RM / Remoto (si está activado)
    if int(filtros.get("solo_rm_o_remoto", 1)) == 1:
        es_remoto = "remot" in titulo or "remot" in ubic or "remot" in mod_oferta or "teletrabajo" in desc
        if not es_remoto and any(reg in f"{titulo} {ubic}" for reg in REGIONES_FUERA_RM):
            return False, "Fuera de Región Metropolitana y no indica modalidad remota", 10

    # 2. Filtro Anti-Carreras Ajenas y Educación Media (Duoc UC exige Educación Superior Profesional)
    for ca in CARRERAS_AJENAS:
        if ca in titulo:
            return False, f"Área ajena al perfil TI / Duoc UC ('{ca}')", 5

    # 3. Exclusiones configuradas por el usuario (Senior, Jefaturas, etc.)
    exclusiones = [e.strip().lower() for e in (filtros.get("palabras_excluir") or "").split(",") if e.strip()]
    for exc in exclusiones:
        if re.search(r"\b" + re.escape(exc) + r"\b", titulo):
            return False, f"Excluida por nivel/requisito en título: '{exc}'", 15
        if ("año" in exc or "años" in exc or "educación media" in exc) and exc in desc:
            return False, f"Excluida por requisito incompatible: '{exc}'", 15

    # 4. Verificar condición de Práctica vs Empleo según el modo
    es_practica = any(re.search(p, titulo) for p in PATRONES_PRACTICA) or (
        modo != "empleo_ti" and any(re.search(p, desc[:300]) for p in PATRONES_PRACTICA[:4])
    )

    if modo == "practica_duoc" and not es_practica:
        return False, "Modo Práctica Duoc UC activo: el aviso es un empleo regular, no una práctica", 25

    if modo == "empleo_ti" and es_practica:
        return False, "Modo Empleo Regular activo: el aviso es solo de práctica", 30

    # 5. Evaluar afinidad con Ingeniería en Infraestructura y Plataformas Tecnológicas o término libre
    termino_custom = [t.strip().lower() for t in re.split(r"[, ]+", filtros.get("termino_personalizado") or "") if len(t.strip()) >= 3]
    match_infra_titulo = [p for p in PATRONES_INFRA_DUOC if re.search(p, titulo)]
    match_custom = [t for t in termino_custom if t in texto_completo]

    raw_combinadas = filtros.get("palabras_combinadas") or ""
    lista_combinadas = [w.strip().lower() for w in raw_combinadas.split(",") if w.strip()]
    coincidencias_tech = [w for w in lista_combinadas if w in texto_completo]

    if modo == "practica_duoc":
        if not match_infra_titulo and len(coincidencias_tech) < 1:
            return False, "No coincide con el perfil de egreso de Ing. en Infraestructura y Plataformas Tecnológicas", 20
    else:
        # En modo empleo_ti o ambos, permitir también coincidencias con el término personalizado del usuario
        if not match_infra_titulo and not match_custom and len(coincidencias_tech) < 1:
            return False, "No coincide con las tecnologías ni términos de búsqueda indicados", 20

    # 6. Modalidad preferida
    pref_mod = filtros.get("modalidad_preferida", "Todas")
    if pref_mod and pref_mod != "Todas":
        if pref_mod.lower() not in mod_oferta and pref_mod.lower() not in desc:
            return False, f"Modalidad distinta a '{pref_mod}'", 35

    # 7. Calcular Score de Afinidad Duoc UC / Perfil Dhani (0-100)
    score = 65
    especialidades_top = [
        "infraestructura", "plataforma", "cloud", "aws", "azure", "redes", "conectividad",
        "telecomunicaciones", "ciberseguridad", "seguridad ti", "soc", "servidor", "linux",
        "windows server", "operaciones ti", "continuidad", "devops", "virtualización", "soporte"
    ]
    hits_top = [k for k in especialidades_top if k in titulo]
    if hits_top:
        score += min(30, 18 + 6 * len(hits_top))
    if len(coincidencias_tech) >= 2:
        score += 5
    if any(w in titulo for w in ["fullstack", "frontend", "móvil", "comercial"]):
        score -= 15
    score = max(50, min(100, score))

    etiqueta_modo = "Práctica Duoc UC (360h compatible)" if es_practica else "Empleo TI Compatible"
    detalle_tech = ", ".join((hits_top or coincidencias_tech or match_custom)[:3]) or "TI / Informática"
    return True, f"{etiqueta_modo} · Afinidad {score}% ({detalle_tech})", score


def es_oferta_practica(oferta, filtros):
    """Wrapper retrocompatible que devuelve (aprobada: bool, motivo: str)."""
    ok, motivo, _ = evaluar_oferta_inteligente(oferta, filtros)
    return ok, motivo


def generar_respuesta_persuasiva_ia(pregunta_sanitizada: str, perfil: dict, contexto_oferta: str = "") -> str:
    """
    Genera respuestas técnicas persuasivas alineadas a Ingeniería en Infraestructura y Plataformas Tecnológicas (Duoc UC).
    """
    p_lower = pregunta_sanitizada.lower()
    carrera = perfil.get("carrera") or "Ingeniería en Infraestructura y Plataformas Tecnológicas"
    inst = perfil.get("institucion") or "Duoc UC"
    sede = perfil.get("sede") or "Sede Antonio Varas"
    skills = perfil.get("habilidades_tech") or "Linux, Windows Server, Active Directory, AWS, Terraform, Docker, Redes Cisco, Zabbix, Grafana, Wazuh y Python"

    if any(k in p_lower for k in ["por qué deberíamos", "por que deberiamos", "mejor candidato", "por qué contratarte", "por que tú", "por que tu"]):
        return (
            f"Soy estudiante de último semestre de {carrera} en {inst} ({sede}, horario vespertino), restándome únicamente "
            f"la práctica profesional de 360 horas y 3 ramos vespertinos para titularme. Integro administración real de servidores "
            f"Linux/Windows, Active Directory, Cloud AWS con Terraform, monitoreo con Zabbix/Grafana, ciberseguridad (Wazuh/Suricata/Zeek) "
            f"y soporte físico/microsoldadura, lo que me permite aportar continuidad operacional y resultados desde el primer día."
        )

    if any(k in p_lower for k in ["cloud", "aws", "azure", "gcp", "terraform", "devops", "docker", "kubernetes", "virtualiz"]):
        return (
            "Cuento con experiencia práctica desplegando infraestructura como código (IaC) con Terraform y Ansible en AWS/GCP "
            "(EC2, VPC, S3, EBS), contenedorización con Docker y Kubernetes, y virtualización on-premise con VMware, KVM/QEMU e Hyper-V, "
            "incluyendo respaldos con Veeam y observabilidad con Prometheus y Grafana."
        )

    if any(k in p_lower for k in ["ciberseguridad", "seguridad", "soc", "firewall", "wazuh", "vulnerab"]):
        return (
            "He diseñado e implementado la plataforma SOAR LZOC integrando EDR (Velociraptor), NDR (Zeek y Suricata), SIEM Wazuh, "
            "Threat Intelligence (MISP), firewalls Cisco ASA con ACL, escaneos con Nessus/OpenVAS y hardening de servidores Linux y Windows GPO."
        )

    if any(k in p_lower for k in ["red", "redes", "cisco", "telecom", "conectividad", "switch", "vlan", "cableado"]):
        return (
            "Cuento con certificaciones Duoc UC en Implementación de Redes Pequeñas y Medianas y Soporte en Infraestructura de Datacenter. "
            "Manejo switching/routing Cisco, VLANs, firewalls Cisco ASA, túneles Cloudflare, VPN, DNS/DHCP, monitoreo SNMP con Zabbix/LibreNMS y cableado estructurado."
        )

    if any(k in p_lower for k in ["hardware", "soldar", "soldadura", "armado", "reparación", "reparacion", "mantenimiento", "físico", "fisico"]):
        return (
            "Poseo amplia experiencia práctica en diagnóstico y reparación de computadores, servidores y dispositivos a nivel componente, "
            "incluyendo microsoldadura electrónica, mantenimiento preventivo/correctivo, clonación/recuperación de almacenamiento y gestión de tickets Aranda/GLPI/osTicket."
        )

    if any(k in p_lower for k in ["mayor logro", "logro", "proyecto técnico", "proyecto tecnico", "orgulloso", "proyectos has"]):
        return (
            "Mi proyecto destacado es LZOC, una plataforma SOAR de continuidad operacional en alta disponibilidad (HAProxy, PostgreSQL, Redis) "
            "que correlaciona alertas de Zabbix, Wazuh, Suricata y Zeek con inventario NetBox, ticketing automático y remediación con Ansible y Terraform."
        )

    if any(k in p_lower for k in ["aprender", "tecnología que no conoces", "organizas", "nueva herramienta", "autodidacta"]):
        return (
            "Aprendo levantando laboratorios reales con contenedores Docker o máquinas virtuales KVM/VMware, documentando cada arquitectura "
            "y automatizando pruebas en Python/Bash, lo que me permite adaptarme al stack corporativo del equipo en pocos días."
        )

    if any(k in p_lower for k in ["interesa", "motiva", "gustaría", "por qué postulaste"]):
        return (
            f"Me motiva enormemente aportar mis competencias de {carrera} en un entorno real de operación tecnológica, "
            "contribuyendo a la disponibilidad de plataformas, redes, seguridad y soporte mientras consolido mi cierre de carrera en Duoc UC."
        )

    return (
        f"Estudiante de último semestre de {carrera} en {inst} ({sede}, vespertino), con experiencia práctica en {skills}. "
        "Destaco por mi proactividad, rigor operacional, comunicación clara con usuarios y disponibilidad diurna inmediata."
    )


def resolver_pregunta_formulario(pregunta: str, perfil: dict, respuestas_aprendidas_fn=None, contexto_oferta: str = "", modo: str = "practica_duoc"):
    """
    Resuelve preguntas de formularios de postulación (tanto para Prácticas Duoc UC como para Empleos TI).
    Devuelve (respondida: bool, respuesta: str, requiere_usuario: bool).
    """
    p_segura = sanitizar_texto_seguro(pregunta)
    p_lower = p_segura.lower().strip()

    # 1. Renta / Asignación según si es Práctica o Empleo formal
    if any(k in p_lower for k in ["renta", "sueldo", "pretensión", "pretension", "líquida", "liquida", "honorarios", "remuneración", "asignación", "ingresos esperados"]):
        if modo == "empleo_ti":
            renta_emp = int(perfil.get("renta_empleo") or 950000)
            return True, f"${renta_emp:,}".replace(",", "."), False
        renta = perfil.get("renta_esperada", 0)
        if renta is None or int(renta) == 0:
            return True, "Acorde a la asignación de práctica definida por la empresa (abierto a convenio institucional de movilización/colación).", False
        return True, f"${int(renta):,}".replace(",", "."), False

    # 2. RUT / Documento de identidad
    if any(k in p_lower for k in ["rut", "run", "cédula", "cedula", "documento de identidad"]):
        return True, perfil.get("rut", "20.338.608-7"), False

    # 3. Licencia de conducir
    if any(k in p_lower for k in ["licencia de conducir", "licencia clase", "conducir", "clase b"]):
        lic = perfil.get("licencia_conducir") or "Clase B"
        return True, f"Sí, cuento con Licencia de Conducir {lic} al día.", False

    # 4. Seguro escolar Duoc UC
    if any(k in p_lower for k in ["seguro", "seguro escolar", "accidentes"]):
        return True, "Sí, cuento con Seguro Escolar de Accidentes vigente (Ley 16.744) y Carta de Presentación emitidos por Duoc UC a través de Vivo Duoc.", False

    # 5. Horas de práctica requeridas por Duoc UC
    if any(k in p_lower for k in ["horas", "duración", "duracion", "cuántas horas", "periodo de práctica", "meses de práctica"]):
        hrs = int(perfil.get("horas_requeridas") or 360)
        return True, f"{hrs} horas cronológicas mínimas según malla oficial de Ingeniería en Infraestructura y Plataformas Tecnológicas en Duoc UC (con total disposición a extender si el proyecto lo requiere).", False

    # 6. Disponibilidad horaria
    if any(k in p_lower for k in ["disponibilidad", "cuándo puedes empezar", "fecha de inicio", "incorporación", "empezar", "horario"]):
        return True, (
            "Disponibilidad inmediata en jornada diurna completa (estudio en jornada vespertina en Duoc UC Sede Antonio Varas, "
            "por lo que tengo disponibilidad completa en horario hábil diurno)."
        ), False

    # 7. Carrera / Institución / Avance curricular
    if any(k in p_lower for k in ["carrera", "qué estudias", "título", "profesión", "especialidad"]):
        return True, f"{perfil.get('carrera', 'Ingeniería en Infraestructura y Plataformas Tecnológicas')} — {perfil.get('institucion', 'Duoc UC')} ({perfil.get('sede', 'Sede Antonio Varas')})", False

    if any(k in p_lower for k in ["universidad", "instituto", "casa de estudio", "institución", "duoc"]):
        return True, f"{perfil.get('institucion', 'Duoc UC')} ({perfil.get('sede', 'Sede Antonio Varas')})", False

    if any(k in p_lower for k in ["avance", "malla", "ramos", "asignaturas", "situación académica", "situacion academica", "titulación", "egreso", "semestre"]):
        return True, (
            "Último semestre de Ingeniería en Infraestructura y Plataformas Tecnológicas en Duoc UC Sede Antonio Varas (vespertino). "
            "Solo me restan las 360 horas de Práctica Profesional y finalizar 3 asignaturas vespertinas para obtener el título profesional."
        ), False

    # 8. Inglés
    if any(k in p_lower for k in ["inglés", "ingles", "english", "idioma"]):
        ingles = perfil.get("nivel_ingles", "Intermedio B1")
        return True, f"{ingles} certificado (lectura fluida de documentación técnica y comunicación operativa).", False

    # 9. Comuna / Residencia / Traslado
    if any(k in p_lower for k in ["comuna", "ciudad", "dónde vives", "residencia", "traslado", "desplazar", "ubicación"]):
        comuna = perfil.get("comuna", "Las Condes")
        region = perfil.get("region", "Región Metropolitana")
        return True, f"{comuna}, {region}. Disponibilidad completa para modalidad presencial en toda la RM, híbrida o remota.", False

    # 10. Active Directory / Windows / Linux / Herramientas TI
    if any(k in p_lower for k in ["active directory", "windows server", "microsoft 365", "linux", "bash", "docker", "sql", "oracle", "postgresql", "python"]):
        return True, (
            "Sí, cuento con experiencia práctica administrando Linux (Oracle/RHEL/Ubuntu/Debian), Windows Server con Active Directory y GPOs, "
            "Microsoft 365/Azure AD, contenedores Docker/Kubernetes, bases de datos PostgreSQL/Oracle y automatización en Python, Bash y PowerShell."
        ), False

    # 11. Computador / Teletrabajo
    if any(k in p_lower for k in ["computador", "notebook", "internet", "home office", "teletrabajo"]):
        return True, "Sí, dispongo de estación de trabajo propia con Linux/Windows, fibra óptica de alta velocidad y entorno óptimo para trabajo híbrido o remoto.", False

    # 12. Memoria aprendida
    if respuestas_aprendidas_fn:
        resp_guardada = respuestas_aprendidas_fn(p_segura)
        if resp_guardada:
            return True, resp_guardada, False

    # 13. Motor persuasivo general para cualquier pregunta abierta o técnica
    resp_ia = generar_respuesta_persuasiva_ia(p_segura, perfil, contexto_oferta)
    return True, resp_ia, False
