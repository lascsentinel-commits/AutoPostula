"""
Módulo de Despacho Inteligente de CVs Especializados — AutoPostula v3.0
Ingeniería en Infraestructura y Plataformas Tecnológicas (Duoc UC)

Mapea cada vacante o práctica con el CV calibrado a 2 páginas que maximiza
la tasa de contacto y la concordancia ATS con los requisitos del reclutador.
"""

import os
import re

BASE_DIR_CVS = "/home/dhamit/Documentos/CV-2026-01/versiones_especializadas"
CV_UNIFICADO_PATH = "/home/dhamit/Documentos/CV-2026-01/1_CV_Dhani_Amit_Elgueta_Ríos_U-26.pdf"

CATALOGO_CVS = {
    "01_Ciberseguridad": {
        "nombre": "Ciberseguridad & SOC Junior",
        "archivo": "CV_Dhani_Elgueta_01_Ciberseguridad.pdf",
        "subcarpeta": "01_Ciberseguridad",
        "keywords": [
            "ciberseguridad", "seguridad informática", "seguridad", "soc", "siem",
            "pentest", "pentesting", "hacking", "vulnerab", "wazuh", "suricata",
            "zeek", "iso 27001", "ciso", "ethical hacking", "threat", "firewall",
            "incident", "analista soc", "blue team", "red team", "seguridad perimetral"
        ],
        "enfoque": "Monitoreo SIEM/SOC (Wazuh, Zeek, Suricata), Kali Linux, seguridad perimetral y cursos de ethical hacking."
    },
    "02_Redes_Telecomunicaciones": {
        "nombre": "Redes & Telecomunicaciones (NOC)",
        "archivo": "CV_Dhani_Elgueta_02_Redes_Telecomunicaciones.pdf",
        "subcarpeta": "02_Redes_Telecomunicaciones",
        "keywords": [
            "redes", "telecomunicaci", "conectividad", "cisco", "ccna", "switching",
            "routing", "ospf", "bgp", "vlan", "enlaces", "fibra", "noc", "networking",
            "datacenter", "data center", "wireshark", "comunicaciones", "cableado",
            "infraestructura de red", "router", "switch", "subredes", "vpn"
        ],
        "enfoque": "Routing & Switching Cisco, VLANs, OSPF, Zabbix, Wireshark, Datacenter y protocolos de capa 2/3."
    },
    "04_Cloud_DevOps": {
        "nombre": "Cloud & Plataformas DevOps",
        "archivo": "CV_Dhani_Elgueta_04_Cloud_DevOps.pdf",
        "subcarpeta": "04_Cloud_DevOps",
        "keywords": [
            "cloud", "nube", "aws", "devops", "terraform", "iac", "docker",
            "kubernetes", "k8s", "sre", "ci/cd", "pipeline", "automatización",
            "grafana", "prometheus", "python scripting", "bash", "ansible",
            "plataformas analíticas", "despliegue continuo"
        ],
        "enfoque": "Infraestructura como Código (Terraform en AWS), contenedores Docker/Kubernetes y observabilidad."
    },
    "03_SysAdmin_Sistemas": {
        "nombre": "Administración de Sistemas & Servidores",
        "archivo": "CV_Dhani_Elgueta_03_SysAdmin_Sistemas.pdf",
        "subcarpeta": "03_SysAdmin_Sistemas",
        "keywords": [
            "sistemas", "sysadmin", "servidor", "windows server", "active directory",
            "linux", "rhel", "redhat", "ubuntu server", "debian", "vmware",
            "virtualiz", "backup", "drp", "veeam", "samba", "cifs", "gpo",
            "mantención industrial", "administrador de sistemas", "infraestructura"
        ],
        "enfoque": "Linux RHEL/Ubuntu, Windows Server, Active Directory, GPOs, Samba CIFS, Veeam DRP y virtualización."
    },
    "05_Soporte_OperacionesTI": {
        "nombre": "Soporte TI Corporativo & Operaciones",
        "archivo": "CV_Dhani_Elgueta_05_Soporte_OperacionesTI.pdf",
        "subcarpeta": "05_Soporte_OperacionesTI",
        "keywords": [
            "soporte", "helpdesk", "help desk", "mesa de ayuda", "operaciones",
            "terreno", "n1", "n2", "n3", "hardware", "mantenimiento pc",
            "microinformática", "técnico", "aranda", "tickets", "sla", "office 365",
            "m365", "atención usuarios", "diagnóstico", "reparación", "soporte ti"
        ],
        "enfoque": "Asistente Soporte TI en BDO con Aranda N1-N3, cumplimiento de SLAs, M365 y reparación de hardware."
    }
}


def obtener_cv_optimo(titulo: str, descripcion: str = "", preferir_unificado: bool = True) -> dict:
    """
    Analiza el cargo y descripción de una vacante y determina el CV que mejor
    se alinea con las expectativas de la empresa.
    Si preferir_unificado es True y existe el CV Maestro Unificado, devuelve este archivo
    para todas las postulaciones, manteniendo el enfoque contextual de la vacante.
    """
    if preferir_unificado and os.path.exists(CV_UNIFICADO_PATH):
        # Determinar de todas formas la especialidad para las notas y cartas de presentación
        titulo_limpio = (titulo or "").lower()
        desc_limpia = (descripcion or "").lower()
        scores = {}
        for cat_id, data in CATALOGO_CVS.items():
            sc = sum(5 if (re.search(r"\b" + re.escape(kw) + r"\b", titulo_limpio) or kw in titulo_limpio) else (1 if re.search(r"\b" + re.escape(kw) + r"\b", desc_limpia) else 0) for kw in data["keywords"])
            scores[cat_id] = sc
        mejor_cat = max(scores, key=scores.get) if scores else "05_Soporte_OperacionesTI"
        info = CATALOGO_CVS.get(mejor_cat, CATALOGO_CVS["05_Soporte_OperacionesTI"])

        return {
            "categoria_id": "00_Master_Unificado",
            "nombre_especialidad": "CV Maestro Integral Unificado",
            "archivo": os.path.basename(CV_UNIFICADO_PATH),
            "ruta_pdf": CV_UNIFICADO_PATH,
            "existe": True,
            "score_match": scores.get(mejor_cat, 100),
            "motivo": f"CV Maestro Completo 6 págs (Enfoque detectado: {info['nombre']})",
            "enfoque": info["enfoque"]
        }
    titulo_limpio = (titulo or "").lower()
    desc_limpia = (descripcion or "").lower()
    texto_completo = f"{titulo_limpio} {desc_limpia}"

    scores = {}
    coincidencias = {}

    for cat_id, data in CATALOGO_CVS.items():
        score = 0
        hits = []
        for kw in data["keywords"]:
            if re.search(r"\b" + re.escape(kw) + r"\b", titulo_limpio) or kw in titulo_limpio:
                score += 5  # Alto impacto si está en el título del cargo
                hits.append(f"cargo:{kw}")
            elif re.search(r"\b" + re.escape(kw) + r"\b", desc_limpia):
                score += 1
                hits.append(f"desc:{kw}")
        scores[cat_id] = score
        coincidencias[cat_id] = hits

    mejor_cat = max(scores, key=scores.get)
    if scores[mejor_cat] == 0:
        # Fallback inteligente: si menciona práctica general TI, asignar Soporte u Operaciones
        mejor_cat = "05_Soporte_OperacionesTI"
        motivo = "Asignación estándar por perfil de entrada (Soporte TI y Operaciones Duoc UC)"
    else:
        motivo = f"Coincidencias clave: {', '.join(coincidencias[mejor_cat][:4])}"

    info = CATALOGO_CVS[mejor_cat]
    ruta_pdf = os.path.join(BASE_DIR_CVS, info["subcarpeta"], info["archivo"])

    return {
        "categoria_id": mejor_cat,
        "nombre_especialidad": info["nombre"],
        "archivo": info["archivo"],
        "ruta_pdf": ruta_pdf,
        "existe": os.path.exists(ruta_pdf),
        "score_match": scores[mejor_cat],
        "motivo": motivo,
        "enfoque": info["enfoque"]
    }


def listar_todos_cvs() -> list:
    """Devuelve la lista completa de CVs especializados disponibles."""
    lista = []
    for cat_id, data in CATALOGO_CVS.items():
        ruta = os.path.join(BASE_DIR_CVS, data["subcarpeta"], data["archivo"])
        lista.append({
            "categoria_id": cat_id,
            "nombre": data["nombre"],
            "archivo": data["archivo"],
            "ruta_pdf": ruta,
            "existe": os.path.exists(ruta),
            "enfoque": data["enfoque"]
        })
    return lista

