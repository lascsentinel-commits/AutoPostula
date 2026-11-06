import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import quote_plus, urljoin

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from database import PORTALES_SOPORTADOS, actualizar_conteo_portal
except Exception:
    PORTALES_SOPORTADOS = []
    def actualizar_conteo_portal(*args, **kwargs):
        pass

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}

BRAVE_BIN = "/opt/brave.com/brave/brave"

PREGUNTAS_BASE_DUOC = [
    "¿Cuál es tu carrera, sede y situación académica actual en Duoc UC?",
    "¿Cuántas horas exige tu práctica profesional y cuentas con Seguro Escolar vigente?",
    "¿Qué experiencia práctica tienes en infraestructura TI, redes, servidores Linux/Windows y soporte?"
]


def _extraer_emails(texto: str) -> list[str]:
    if not texto:
        return []
    encontrados = set(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", texto))
    ignorar = (
        "sentry", "example", "wix", "cloudflare", "chiletrabajos", "computrabajo",
        "duoclaboral", "reqlut", "firstjob", "trabajando", "serviciocivil.cl"
    )
    return [e for e in encontrados if not any(ig in e.lower() for ig in ignorar)]


def _terminos_segun_modo(modo: str = "practica_duoc", termino_extra: str = "") -> list[str]:
    extra_clean = (termino_extra or "").strip()
    if modo == "empleo_ti":
        base = [
            "soporte ti infraestructura",
            "administrador sistemas linux",
            "redes telecomunicaciones",
            "cloud devops junior",
            "ciberseguridad soc",
        ]
        if extra_clean and extra_clean.lower() not in " ".join(base):
            base.insert(0, extra_clean[:50])
        return base[:5]
    elif modo == "ambos":
        base = [
            "practica infraestructura ti",
            "practica soporte redes",
            "soporte ti infraestructura",
            "administrador sistemas linux",
        ]
        if extra_clean:
            base.insert(0, extra_clean[:50])
        return base[:5]
    else:
        return [
            "practica infraestructura",
            "practica soporte ti",
            "practica redes telecomunicaciones",
            "practica cloud sistemas",
            "practica ciberseguridad",
            "practica informatica",
        ]


# =====================================================================
# 1. FIRSTJOB (firstjob.me) — Portal #1 Prácticas y Primer Empleo Chile
# =====================================================================
def buscar_firstjob(modo="practica_duoc", termino_extra="") -> list[dict]:
    ofertas = []
    seen = set()
    if modo == "empleo_ti":
        terminos = ["infraestructura", "soporte", "cloud", "sistemas", "ciberseguridad"]
        if termino_extra:
            terminos.insert(0, termino_extra.split()[0])
    else:
        terminos = ["infraestructura", "soporte", "redes", "cloud", "sistemas", "ciberseguridad", "plataformas"]

    for term in terminos[:6]:
        try:
            url = f"https://firstjob.me/ofertas?country%5B%5D=43&title={quote_plus(term)}"
            r = requests.get(url, headers=HEADERS, timeout=9)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=re.compile(r"^/oferta/\d+")):
                full_u = "https://firstjob.me" + a["href"].split("?")[0]
                if full_u in seen:
                    continue
                seen.add(full_u)
                txt = a.get_text(" | ", strip=True)
                parts = [p.strip() for p in txt.split("|") if p.strip()]
                titulo = parts[0] if parts else txt[:85]
                empresa = parts[1] if len(parts) > 1 else "Empresa FirstJob"
                ubic = parts[2] if len(parts) > 2 else "Región Metropolitana, Chile"
                ofertas.append({
                    "titulo": titulo,
                    "empresa": empresa,
                    "portal": "FirstJob",
                    "url_oferta": full_u,
                    "ubicacion": ubic,
                    "modalidad": "Híbrido / Presencial",
                    "asignacion_dinero": "Asignación Práctica / Convenio" if "práctica" in titulo.lower() or "practica" in titulo.lower() else "Renta Mercado",
                    "descripcion": txt[:600],
                    "fecha_oferta": datetime.now().strftime("%Y-%m-%d"),
                    "preguntas": list(PREGUNTAS_BASE_DUOC),
                })
        except Exception:
            continue
    return ofertas


# =====================================================================
# 2. TRABAJANDO.CL API JSON (/api/searchjob + /api/ofertas/{id})
# =====================================================================
def buscar_trabajando_cl(modo="practica_duoc", termino_extra="") -> list[dict]:
    ofertas = []
    seen_ids = set()
    terminos = _terminos_segun_modo(modo, termino_extra)

    for term in terminos[:5]:
        try:
            url = f"https://www.trabajando.cl/api/searchjob?palabraClave={quote_plus(term)}"
            r = requests.get(url, headers=HEADERS, timeout=9)
            if r.status_code != 200:
                continue
            items = r.json().get("ofertas", [])
            for o in items[:15]:
                oid = o.get("idOferta")
                if not oid or oid in seen_ids:
                    continue
                seen_ids.add(oid)
                cargo = o.get("nombreCargo") or ""
                emp = o.get("nombreEmpresa") or "Empresa en Trabajando.cl"
                ubic = o.get("ubicacion") or "Santiago, Región Metropolitana"
                desc = o.get("descripcionOferta") or cargo
                fpub = str(o.get("fechaPublicacion") or datetime.now().strftime("%Y-%m-%d"))[:10]
                jornada = o.get("nombreJornada") or "Completa / Práctica"
                url_final = f"https://www.trabajando.cl/trabajo-empleo?palabraClave={oid}"
                preguntas = list(PREGUNTAS_BASE_DUOC)
                sueldo_txt = "Asignación según empresa"

                # Enriquecer las ofertas relevantes de TI/Práctica con su slug real y preguntas reales
                if any(k in cargo.lower() for k in ["práctica", "practica", "practicante", "infraestructura", "soporte", "redes", "telecom", "ciber", "cloud", "linux", "sistemas", "inform"]):
                    try:
                        rd = requests.get(f"https://www.trabajando.cl/api/ofertas/{oid}", headers=HEADERS, timeout=5)
                        if rd.status_code == 200:
                            jd = rd.json()
                            if jd.get("slug"):
                                url_final = f"https://www.trabajando.cl/trabajo/{jd['slug']}"
                            if jd.get("descripcionOferta"):
                                desc = BeautifulSoup(
                                    (jd.get("descripcionOferta") or "") + " " + (jd.get("requisitosMinimos") or ""),
                                    "html.parser"
                                ).get_text(" ", strip=True)[:800]
                            if jd.get("preguntas"):
                                qs = [q.get("pregunta", "").strip() for q in jd["preguntas"] if q.get("pregunta")]
                                if qs:
                                    preguntas = qs
                            if jd.get("mostrarSueldo") and jd.get("sueldo"):
                                sueldo_txt = f"${int(jd['sueldo']):,}".replace(",", ".")
                    except Exception:
                        pass

                ofertas.append({
                    "titulo": cargo,
                    "empresa": emp,
                    "portal": "Trabajando.cl",
                    "url_oferta": url_final,
                    "ubicacion": ubic,
                    "modalidad": jornada,
                    "asignacion_dinero": sueldo_txt,
                    "descripcion": desc,
                    "fecha_oferta": fpub,
                    "preguntas": preguntas,
                    "email_reclutador": ", ".join(_extraer_emails(desc)),
                })
        except Exception:
            continue
    return ofertas


# =====================================================================
# 3. LINKEDIN JOBS CHILE (Guest Search Endpoint en vivo)
# =====================================================================
def buscar_linkedin_jobs(modo="practica_duoc", termino_extra="") -> list[dict]:
    ofertas = []
    seen = set()
    terminos = _terminos_segun_modo(modo, termino_extra)

    for kw in terminos[:4]:
        try:
            url = (
                "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                f"?keywords={quote_plus(kw)}&location={quote_plus('Santiago, Región Metropolitana de Santiago, Chile')}&f_TPR=r2592000&start=0"
            )
            r = requests.get(url, headers=HEADERS, timeout=9)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for li in soup.find_all("li"):
                t = li.find("h3", class_=re.compile(r"base-search-card__title"))
                c = li.find("h4", class_=re.compile(r"base-search-card__subtitle"))
                l = li.find("span", class_=re.compile(r"job-search-card__location"))
                a = li.find("a", href=True)
                dt = li.find("time")
                if not t or not a:
                    continue
                job_url = a["href"].split("?")[0]
                if job_url in seen:
                    continue
                seen.add(job_url)
                titulo = t.get_text(strip=True)
                ofertas.append({
                    "titulo": titulo,
                    "empresa": c.get_text(strip=True) if c else "Empresa en LinkedIn",
                    "portal": "LinkedIn Jobs",
                    "url_oferta": job_url,
                    "ubicacion": l.get_text(strip=True) if l else "Santiago, Chile",
                    "modalidad": "Híbrido / Presencial",
                    "asignacion_dinero": "Convenio Práctica / Mercado",
                    "descripcion": f"{titulo} en {c.get_text(strip=True) if c else 'Chile'}. Publicado en LinkedIn Jobs Chile.",
                    "fecha_oferta": (dt.get("datetime") if dt else None) or datetime.now().strftime("%Y-%m-%d"),
                    "preguntas": list(PREGUNTAS_BASE_DUOC),
                })
        except Exception:
            continue
    return ofertas


# =====================================================================
# 4. COMPUTRABAJO CHILE (cl.computrabajo.com)
# =====================================================================
def buscar_computrabajo(modo="practica_duoc", termino_extra="") -> list[dict]:
    ofertas = []
    seen = set()
    if modo == "empleo_ti":
        slugs = [
            "trabajo-de-soporte-ti-en-rmetropolitana",
            "trabajo-de-infraestructura-ti-en-rmetropolitana",
            "trabajo-de-administrador-de-sistemas-en-rmetropolitana",
            "trabajo-de-redes-telecomunicaciones-en-rmetropolitana",
        ]
        if termino_extra:
            slug_custom = re.sub(r"[^a-z0-9]+", "-", termino_extra.lower()).strip("-")
            if slug_custom:
                slugs.insert(0, f"trabajo-de-{slug_custom}-en-rmetropolitana")
    else:
        slugs = [
            "trabajo-de-practica-soporte-ti-en-rmetropolitana",
            "trabajo-de-practica-informatica-en-rmetropolitana",
            "trabajo-de-practica-redes-en-rmetropolitana",
            "trabajo-de-practica-infraestructura-en-rmetropolitana",
            "trabajo-de-practica-telecomunicaciones-en-rmetropolitana",
        ]

    for slug in slugs[:5]:
        try:
            url = f"https://cl.computrabajo.com/{slug}"
            r = requests.get(url, headers=HEADERS, timeout=9)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for ar in soup.find_all("article", class_=re.compile(r"box_offer"))[:15]:
                a = ar.find("a", class_=re.compile(r"js-o-link")) or ar.find("a", href=True)
                if not a:
                    continue
                full_u = urljoin("https://cl.computrabajo.com", a["href"].split("#")[0])
                if full_u in seen:
                    continue
                seen.add(full_u)
                # Extraer empresa sin confundir con el título
                ps = ar.find_all("p")
                empresa = "Empresa Computrabajo"
                for p_el in ps:
                    pt = p_el.get_text(" ", strip=True)
                    if pt and pt != a.get_text(strip=True) and len(pt) < 75:
                        empresa = re.sub(r"^\d+[.,]\d+\s*", "", pt).strip()
                        break
                txt_all = ar.get_text(" ", strip=True)
                ofertas.append({
                    "titulo": a.get_text(strip=True),
                    "empresa": empresa,
                    "portal": "Computrabajo",
                    "url_oferta": full_u,
                    "ubicacion": "Santiago, Región Metropolitana",
                    "modalidad": "Remoto" if "remoto" in txt_all.lower() else "Presencial / Híbrido",
                    "asignacion_dinero": "Asignación en portal",
                    "descripcion": txt_all[:500],
                    "fecha_oferta": datetime.now().strftime("%Y-%m-%d"),
                    "preguntas": list(PREGUNTAS_BASE_DUOC),
                })
        except Exception:
            continue
    return ofertas


# =====================================================================
# 5. CHILETRABAJOS (Parámetros corregidos: 2=query & 13=1022 Santiago)
# =====================================================================
def buscar_chiletrabajos(modo="practica_duoc", termino_extra="") -> list[dict]:
    ofertas = []
    seen = set()
    terminos = _terminos_segun_modo(modo, termino_extra)

    for term in terminos[:4]:
        try:
            url = f"https://www.chiletrabajos.cl/encuentra-un-empleo?2={quote_plus(term)}&13=1022"
            resp = requests.get(url, headers=HEADERS, timeout=9)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.find_all("div", class_=re.compile(r"job-item"))[:15]:
                h2 = item.find("h2")
                enlace = h2.find("a", href=True) if h2 else item.find("a", href=True)
                if not enlace:
                    continue
                url_job = urljoin("https://www.chiletrabajos.cl", enlace["href"])
                if url_job in seen:
                    continue
                seen.add(url_job)
                titulo = enlace.get_text(strip=True)
                metas = [m.get_text(strip=True) for m in item.find_all("h3")]
                emp_loc = metas[0] if metas else "Empresa TI, Santiago"
                partes_emp = [x.strip() for x in emp_loc.split(",")]
                empresa = partes_emp[0] if partes_emp else "Empresa Confidencial"
                ubicacion = partes_emp[1] if len(partes_emp) > 1 else "Santiago, Región Metropolitana"
                fecha_txt = metas[1] if len(metas) > 1 else datetime.now().strftime("%Y-%m-%d")
                desc_elem = item.find("p")
                desc = desc_elem.get_text(" ", strip=True) if desc_elem else titulo

                ofertas.append({
                    "titulo": titulo,
                    "empresa": empresa,
                    "portal": "ChileTrabajos",
                    "url_oferta": url_job,
                    "ubicacion": f"{ubicacion}, RM",
                    "modalidad": "Remoto" if "remoto" in (titulo + " " + desc).lower() else "Presencial / Híbrido",
                    "asignacion_dinero": "Asignación de práctica / Renta",
                    "descripcion": desc[:600],
                    "fecha_oferta": fecha_txt,
                    "preguntas": list(PREGUNTAS_BASE_DUOC),
                    "email_reclutador": ", ".join(_extraer_emails(desc)),
                })
        except Exception:
            continue
    return ofertas


# =====================================================================
# 6. GET ON BOARD (API Oficial JSON v0)
# =====================================================================
def buscar_getonboard(modo="practica_duoc", termino_extra="") -> list[dict]:
    ofertas = []
    seen = set()
    if modo == "practica_duoc":
        queries = ["practica", "intern", "trainee", "infraestructura", "soporte"]
    else:
        queries = ["infraestructura", "sysadmin", "devops", "soporte ti", "ciberseguridad"]
        if termino_extra:
            queries.insert(0, termino_extra[:40])

    for q in queries[:4]:
        try:
            url = f"https://www.getonbrd.com/api/v0/search/jobs?query={quote_plus(q)}&per_page=20&page=1"
            r = requests.get(url, headers=HEADERS, timeout=9)
            if r.status_code != 200:
                continue
            for j in r.json().get("data", []):
                pub_url = (j.get("links") or {}).get("public_url") or ""
                if not pub_url or pub_url in seen:
                    continue
                seen.add(pub_url)
                at = j.get("attributes") or {}
                titulo = at.get("title") or ""
                countries = str(at.get("countries") or "") + " " + str(at.get("country") or "")
                is_remote = bool(at.get("remote"))
                if "Chile" not in countries and not is_remote and "santiago" not in pub_url.lower():
                    continue
                desc_html = f"{at.get('description') or ''} {at.get('functions') or ''}"
                desc_clean = BeautifulSoup(desc_html, "html.parser").get_text(" ", strip=True)[:650]
                min_s, max_s = at.get("min_salary"), at.get("max_salary")
                renta = f"USD ${min_s} - ${max_s}" if min_s else "Según convenio Tech"
                # Inferir empresa desde slug de URL si API no expande company
                slug_parts = pub_url.rstrip("/").split("-")
                emp_guess = slug_parts[-2].capitalize() if len(slug_parts) >= 3 else "Startup / Tech GetOnBoard"
                ofertas.append({
                    "titulo": titulo,
                    "empresa": emp_guess,
                    "portal": "Get on Board",
                    "url_oferta": pub_url,
                    "ubicacion": "Remoto (Chile)" if is_remote else "Santiago, Chile",
                    "modalidad": "Remoto" if is_remote else "Híbrido",
                    "asignacion_dinero": renta,
                    "descripcion": desc_clean or titulo,
                    "fecha_oferta": datetime.now().strftime("%Y-%m-%d"),
                    "preguntas": list(PREGUNTAS_BASE_DUOC),
                })
        except Exception:
            continue
    return ofertas


# =====================================================================
# 7. PRÁCTICAS CHILE — SERVICIO CIVIL DEL ESTADO (API Elasticsearch)
# =====================================================================
def buscar_practicas_chile_estado(modo="practica_duoc") -> list[dict]:
    if modo == "empleo_ti":
        return []
    ofertas = []
    try:
        es_payload = {
            "from": 0,
            "size": 150,
            "query": {"bool": {"must": [{"match": {"Estado": "postulacion"}}]}}
        }
        r = requests.post(
            "https://apisqa.empleospublicos.cl/elastic/listado_practicas2/_search",
            headers={**HEADERS, "Content-Type": "application/json", "X-API-KEY": "cambia-este-token"},
            data=json.dumps(es_payload),
            timeout=11,
            verify=False,
        )
        if r.status_code == 200:
            for h in r.json().get("hits", {}).get("hits", []):
                src = h.get("_source") or {}
                cargo = str(src.get("Cargo") or "")
                area = str(src.get("Area de Trabajo") or "")
                if "educación media" in cargo.lower():
                    continue
                if any(k in (cargo + " " + area).lower() for k in ["tecnología de la información", "informática", "informatica", "computación", "redes", "soporte", "sistemas", "ciberseguridad", "infraestructura"]):
                    op_id = src.get("id")
                    u = src.get("url") or f"https://practicas2.serviciocivil.cl/concursos-spl/opencms/convocatorias/{op_id}"
                    inst = f"{src.get('Institucion/Entidad', 'Organismo Público')} ({src.get('Ministerio', 'Estado de Chile')})"
                    ofertas.append({
                        "titulo": cargo,
                        "empresa": inst,
                        "portal": "Prácticas Chile (Estado)",
                        "url_oferta": u,
                        "ubicacion": f"{src.get('Ciudad', 'Santiago')}, {src.get('Region', 'RM')}",
                        "modalidad": "Remoto" if "remota" in cargo.lower() else "Presencial",
                        "asignacion_dinero": str(src.get("Renta Bruta") or "Asignación Fiscal Movilización/Colación"),
                        "descripcion": f"Convocatoria oficial Servicio Civil ({op_id}). Área: {area}. Vacantes: {src.get('N de Vacantes', 1)}. Cierre: {src.get('Fecha Cierre Convocatoria', '')}.",
                        "fecha_oferta": str(src.get("Fecha Inicio") or datetime.now().strftime("%Y-%m-%d")),
                        "preguntas": list(PREGUNTAS_BASE_DUOC),
                    })
    except Exception:
        pass
    return ofertas


# =====================================================================
# 8. DUOCLABORAL (Verificación HTTP en vivo de ofertas vigentes + SSO)
# =====================================================================
def buscar_duoclaboral_live(modo="practica_duoc") -> list[dict]:
    ofertas = []
    candidatas = [
        ("PRÁCTICA PROFESIONAL - SOPORTE TECNICO", "DHL Express", "https://duoclaboral.cl/trabajar-en-dhl-express/trabajos/practica-profesional-soporte-tecnico/971288", "Pudahuel, Región Metropolitana", "Presencial"),
        ("Práctica Soporte de Telecomunicaciones, Conectividad y Redes", "SKC", "https://duoclaboral.cl/trabajar-en-skc/trabajos/practica-soporte-de-telecomunicaciones-conectividad-y-redes/969509/1", "Santiago, Región Metropolitana", "Presencial con acercamiento"),
        ("Practicante de Soporte y Redes - Híbrido", "Randstad", "https://duoclaboral.cl/trabajar-en-randstad/trabajos/practicante-de-soporte-y-redes-hibrido/972569", "Las Condes, Región Metropolitana", "Híbrido"),
        ("Práctica Profesional – Soporte TI e Infraestructura", "Grupo Codde Inversiones SpA", "https://duoclaboral.cl/trabajar-en-grupo-codde-inversiones-spa/trabajos/practica-profesional-soporte-ti-e-infraestructura/969784/1", "Santiago, Región Metropolitana", "Híbrido / Remoto"),
        ("Practicante de Soporte TI", "Ferretería Amunátegui", "https://duoclaboral.cl/trabajar-en-ferreteria-amunategui/trabajos/practicante-de-soporte-ti/969460", "Santiago Centro, Región Metropolitana", "Presencial"),
        ("Alumno/a en Práctica para el área TI - Providencia", "HR Burotemps", "https://duoclaboral.cl/trabajar-en-hr-burotemps-empresa-de-servicios-transitorios-limitada/trabajos/alumno-a-en-practica-para-el-area-ti-providencia/971276", "Providencia, Región Metropolitana", "Híbrido"),
        ("Practicantes para el Área de Soporte TI", "Inelcom Chile", "https://duoclaboral.cl/trabajar-en-inelcom-chile1/trabajos/practicantes-para-el-area-de-soporte-ti/967378", "Ñuñoa, Región Metropolitana", "Presencial"),
    ]
    if modo == "empleo_ti":
        return []

    for titulo, emp, url, ubic, mod in candidatas:
        try:
            r = requests.get(url, headers=HEADERS, timeout=7)
            if r.status_code == 200 and "/login" not in r.url:
                soup = BeautifulSoup(r.text, "html.parser")
                txt = soup.get_text(" ", strip=True)
                emails = _extraer_emails(txt)
                ofertas.append({
                    "titulo": titulo,
                    "empresa": emp,
                    "portal": "DuocLaboral",
                    "url_oferta": url,
                    "ubicacion": ubic,
                    "modalidad": mod,
                    "asignacion_dinero": "Convenio Oficial Duoc UC",
                    "descripcion": txt[:650],
                    "fecha_oferta": datetime.now().strftime("%Y-%m-%d"),
                    "preguntas": list(PREGUNTAS_BASE_DUOC),
                    "email_reclutador": ", ".join(emails),
                })
        except Exception:
            continue
    return ofertas


# =====================================================================
# 9. REQLUT CHILE (reqlut.com — Prácticas jobOfferType=1 y Empleos=0)
# =====================================================================
def buscar_reqlut_chile(modo="practica_duoc", termino_extra="") -> list[dict]:
    ofertas = []
    seen = set()
    offer_types = ["1"] if modo == "practica_duoc" else (["0"] if modo == "empleo_ti" else ["1", "0"])
    terms = [""] if modo == "practica_duoc" else [termino_extra or "informatica", "infraestructura", "soporte"]

    for otype in offer_types:
        for t_q in terms[:3]:
            try:
                url = f"https://reqlut.com/trabajo/trabajos-en-chile?Search%5BjobOfferType%5D={otype}"
                if t_q:
                    url += f"&Search%5Bterms%5D={quote_plus(t_q)}"
                r = requests.get(url, headers=HEADERS, timeout=9)
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=re.compile(r"/trabajos/.+/\d+")):
                    txt = a.get_text(" ", strip=True)
                    if not txt or txt.lower() == "postular":
                        continue
                    full_u = urljoin("https://reqlut.com", a["href"])
                    if full_u in seen:
                        continue
                    seen.add(full_u)
                    m_emp = re.search(r"/trabajar-en-([^/]+)/", a["href"])
                    emp = m_emp.group(1).replace("-", " ").title() if m_emp else "Empresa Reqlut"
                    ofertas.append({
                        "titulo": txt[:110],
                        "empresa": emp,
                        "portal": "Reqlut Chile",
                        "url_oferta": full_u,
                        "ubicacion": "Santiago, Región Metropolitana",
                        "modalidad": "Híbrido / Presencial",
                        "asignacion_dinero": "Convenio Práctica" if otype == "1" else "Renta Mercado",
                        "descripcion": f"Oferta activa en red Reqlut Chile ({emp}): {txt}",
                        "fecha_oferta": datetime.now().strftime("%Y-%m-%d"),
                        "preguntas": list(PREGUNTAS_BASE_DUOC),
                    })
            except Exception:
                continue
    return ofertas


# =====================================================================
# 10. TALENT.COM CHILE (Agregador ATS Buk / AIRA / Workday / Greenhouse)
# =====================================================================
def buscar_talent_ats(modo="practica_duoc", termino_extra="") -> list[dict]:
    ofertas = []
    seen = set()
    terminos = _terminos_segun_modo(modo, termino_extra)

    for kw in terminos[:3]:
        try:
            url = f"https://cl.talent.com/jobs?k={quote_plus(kw)}&l=Santiago"
            r = requests.get(url, headers=HEADERS, timeout=9)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for h2 in soup.find_all(["h2", "h3"]):
                titulo = h2.get_text(" ", strip=True)
                if not titulo or len(titulo) < 6:
                    continue
                card = h2.find_parent(["div", "article", "section"])
                if not card:
                    continue
                a = card.find("a", href=re.compile(r"/view\?|/redirect\?|job"))
                full_u = urljoin("https://cl.talent.com", a["href"]) if a else f"https://cl.talent.com/jobs?k={quote_plus(titulo)}&l=Santiago"
                key = titulo.lower()
                if key in seen:
                    continue
                seen.add(key)
                card_txt = card.get_text(" ", strip=True)
                ofertas.append({
                    "titulo": titulo[:110],
                    "empresa": "Empresa Corporativa (ATS Buk/AIRA)",
                    "portal": "Talent.com (ATS Buk/AIRA)",
                    "url_oferta": full_u,
                    "ubicacion": "Santiago, Región Metropolitana",
                    "modalidad": "Híbrido / Presencial",
                    "asignacion_dinero": "Según portal corporativo",
                    "descripcion": card_txt[:500],
                    "fecha_oferta": datetime.now().strftime("%Y-%m-%d"),
                    "preguntas": list(PREGUNTAS_BASE_DUOC),
                })
        except Exception:
            continue
    return ofertas


# =====================================================================
# 11. EMPLEOS PÚBLICOS (Estado de Chile — para modo Empleo TI / Ambos)
# =====================================================================
def buscar_empleos_publicos(modo="practica_duoc", termino_extra="") -> list[dict]:
    if modo == "practica_duoc":
        return []
    ofertas = []
    try:
        r = requests.get("https://www.empleospublicos.cl/pub/convocatorias/convocatorias.aspx", headers=HEADERS, timeout=9)
        if r.status_code == 200:
            ofertas.append({
                "titulo": f"Buscador Oficial TI Estado: {termino_extra or 'Ingeniero Infraestructura / Soporte / Redes'}",
                "empresa": "Servicio Civil · Empleos Públicos de Chile",
                "portal": "Empleos Públicos (Estado)",
                "url_oferta": "https://www.empleospublicos.cl/pub/convocatorias/convocatorias.aspx",
                "ubicacion": "Santiago, Región Metropolitana",
                "modalidad": "Presencial / Contrata Pública",
                "asignacion_dinero": "Escala Única de Sueldos (EUS)",
                "descripcion": "Convocatorias vigentes de infraestructura tecnológica, soporte TI, redes, ciberseguridad y sistemas en ministerios y servicios públicos.",
                "fecha_oferta": datetime.now().strftime("%Y-%m-%d"),
                "preguntas": list(PREGUNTAS_BASE_DUOC),
            })
    except Exception:
        pass
    return ofertas


# =====================================================================
# 12, 13 & 14. PLAYWRIGHT HEADLESS BRAVE: LABORUM, INDEED CHILE & BNE.GOB.CL
# =====================================================================
def buscar_portales_playwright(portales_solicitados: list[str], modo="practica_duoc", termino_extra="") -> dict[str, list[dict]]:
    resultados = {
        "Laborum Chile": [],
        "Indeed Chile": [],
        "BNE (Gob.cl)": [],
    }
    necesita = [p for p in ("Laborum Chile", "Indeed Chile", "BNE (Gob.cl)") if p in portales_solicitados]
    if not necesita or not os.path.exists(BRAVE_BIN):
        return resultados

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=BRAVE_BIN, headless=True, args=["--no-sandbox", "--disable-gpu"])
            ctx = browser.new_context(locale="es-CL", user_agent=HEADERS["User-Agent"])

            # 12. LABORUM CHILE
            if "Laborum Chile" in necesita:
                pg = ctx.new_page()
                if modo == "empleo_ti":
                    slugs = ["empleos-busqueda-infraestructura-ti.html", "empleos-busqueda-soporte-ti.html", "empleos-busqueda-administrador-sistemas.html"]
                else:
                    slugs = ["empleos-busqueda-practica-informatica.html", "empleos-busqueda-practica-soporte-ti.html", "empleos-busqueda-practica-redes.html"]
                seen_l = set()
                for sl in slugs:
                    try:
                        pg.goto(f"https://www.laborum.cl/{sl}", wait_until="domcontentloaded", timeout=12000)
                        pg.wait_for_timeout(2200)
                        cards = pg.eval_on_selector_all("a[href*='/empleos/']", "els => els.map(e => ({text: e.innerText, href: e.href}))")
                        for c in cards:
                            if c["href"] in seen_l:
                                continue
                            seen_l.add(c["href"])
                            lines = [ln.strip() for ln in c["text"].splitlines() if ln.strip()]
                            if len(lines) >= 2:
                                titulo = lines[1] if any(w in lines[0].lower() for w in ["publicado", "actualizado", "nuevo", "hoy", "ayer"]) else lines[0]
                                emp = lines[2] if len(lines) > 2 else "Empresa en Laborum"
                                resultados["Laborum Chile"].append({
                                    "titulo": titulo,
                                    "empresa": emp,
                                    "portal": "Laborum Chile",
                                    "url_oferta": c["href"],
                                    "ubicacion": "Santiago, Región Metropolitana",
                                    "modalidad": "Híbrido / Presencial",
                                    "asignacion_dinero": "Asignación en Laborum",
                                    "descripcion": " | ".join(lines)[:550],
                                    "fecha_oferta": datetime.now().strftime("%Y-%m-%d"),
                                    "preguntas": list(PREGUNTAS_BASE_DUOC),
                                })
                    except Exception:
                        continue
                pg.close()

            # 13. INDEED CHILE
            if "Indeed Chile" in necesita:
                pg2 = ctx.new_page()
                qs_i = ["practica soporte ti", "practica infraestructura ti"] if modo != "empleo_ti" else [termino_extra or "infraestructura soporte ti", "sysadmin linux"]
                seen_i = set()
                for qi in qs_i:
                    try:
                        pg2.goto(f"https://cl.indeed.com/jobs?q={quote_plus(qi)}&l=Santiago", wait_until="domcontentloaded", timeout=12000)
                        pg2.wait_for_timeout(2000)
                        icards = pg2.eval_on_selector_all("div.job_seen_beacon", """els => els.map(el => {
                            const a = el.querySelector('h2.jobTitle a, a.jcs-JobTitle');
                            const comp = el.querySelector('[data-testid=\"company-name\"]');
                            const loc = el.querySelector('[data-testid=\"text-location\"]');
                            return a ? {title: a.innerText, href: a.href, comp: comp ? comp.innerText : '', loc: loc ? loc.innerText : ''} : null;
                        }).filter(Boolean)""")
                        for ic in icards:
                            if ic["href"] in seen_i:
                                continue
                            seen_i.add(ic["href"])
                            resultados["Indeed Chile"].append({
                                "titulo": ic["title"].strip(),
                                "empresa": ic["comp"].strip() or "Empresa Indeed Chile",
                                "portal": "Indeed Chile",
                                "url_oferta": ic["href"],
                                "ubicacion": ic["loc"].strip() or "Santiago, RM",
                                "modalidad": "Presencial / Híbrido",
                                "asignacion_dinero": "Según aviso",
                                "descripcion": f"{ic['title']} — {ic['comp']} ({ic['loc']})",
                                "fecha_oferta": datetime.now().strftime("%Y-%m-%d"),
                                "preguntas": list(PREGUNTAS_BASE_DUOC),
                            })
                    except Exception:
                        continue
                pg2.close()

            # 14. BNE (BOLSA NACIONAL DE EMPLEO - bne.gob.cl)
            if "BNE (Gob.cl)" in necesita:
                pg3 = ctx.new_page()
                q_bne = "practica informatica soporte" if modo == "practica_duoc" else (termino_extra or "informatica infraestructura soporte")
                try:
                    pg3.goto(f"https://bne.gob.cl/buscar-empleo?textoLibre={quote_plus(q_bne)}", wait_until="domcontentloaded", timeout=12000)
                    pg3.wait_for_timeout(2600)
                    bcards = pg3.eval_on_selector_all("a[href*='/ofertas/']", """els => els.map(a => {
                        const card = a.closest('div, article, li');
                        return {href: a.href, text: card ? card.innerText : a.innerText};
                    })""")
                    seen_b = set()
                    for bc in bcards:
                        if bc["href"] in seen_b:
                            continue
                        seen_b.add(bc["href"])
                        lines = [ln.strip() for ln in bc["text"].splitlines() if ln.strip() and ln.strip().lower() != "ver más"]
                        if lines:
                            resultados["BNE (Gob.cl)"].append({
                                "titulo": lines[0][:100],
                                "empresa": lines[1][:70] if len(lines) > 1 else "Empresa BNE Chile",
                                "portal": "BNE (Gob.cl)",
                                "url_oferta": bc["href"],
                                "ubicacion": "Chile / RM",
                                "modalidad": "Presencial / Híbrido",
                                "asignacion_dinero": "Registrada en BNE",
                                "descripcion": " | ".join(lines)[:500],
                                "fecha_oferta": datetime.now().strftime("%Y-%m-%d"),
                                "preguntas": list(PREGUNTAS_BASE_DUOC),
                            })
                except Exception:
                    pass
                pg3.close()

            browser.close()
    except Exception:
        pass
    return resultados


# =====================================================================
# ORQUESTADOR CONCURRENTE DE LOS 14 PORTALES EN VIVO
# =====================================================================
def buscar_todas_las_practicas(palabras_clave="práctica infraestructura", portales=None, modo="practica_duoc"):
    """
    Escanea en paralelo los 14 portales reales de Chile tanto para Prácticas Duoc UC
    como para cualquier pega / empleo TI.
    """
    if not portales:
        portales = list(PORTALES_SOPORTADOS)

    ofertas_totales = []
    tareas_http = {}

    with ThreadPoolExecutor(max_workers=8) as ex:
        if "FirstJob" in portales:
            tareas_http[ex.submit(buscar_firstjob, modo, palabras_clave)] = "FirstJob"
        if "Trabajando.cl" in portales:
            tareas_http[ex.submit(buscar_trabajando_cl, modo, palabras_clave)] = "Trabajando.cl"
        if "LinkedIn Jobs" in portales:
            tareas_http[ex.submit(buscar_linkedin_jobs, modo, palabras_clave)] = "LinkedIn Jobs"
        if "Computrabajo" in portales:
            tareas_http[ex.submit(buscar_computrabajo, modo, palabras_clave)] = "Computrabajo"
        if "ChileTrabajos" in portales:
            tareas_http[ex.submit(buscar_chiletrabajos, modo, palabras_clave)] = "ChileTrabajos"
        if "Get on Board" in portales:
            tareas_http[ex.submit(buscar_getonboard, modo, palabras_clave)] = "Get on Board"
        if "Prácticas Chile (Estado)" in portales:
            tareas_http[ex.submit(buscar_practicas_chile_estado, modo)] = "Prácticas Chile (Estado)"
        if "DuocLaboral" in portales:
            tareas_http[ex.submit(buscar_duoclaboral_live, modo)] = "DuocLaboral"
        if "Reqlut Chile" in portales:
            tareas_http[ex.submit(buscar_reqlut_chile, modo, palabras_clave)] = "Reqlut Chile"
        if "Talent.com (ATS Buk/AIRA)" in portales:
            tareas_http[ex.submit(buscar_talent_ats, modo, palabras_clave)] = "Talent.com (ATS Buk/AIRA)"
        if "Empleos Públicos (Estado)" in portales:
            tareas_http[ex.submit(buscar_empleos_publicos, modo, palabras_clave)] = "Empleos Públicos (Estado)"

        for fut in as_completed(tareas_http):
            nombre_p = tareas_http[fut]
            try:
                res = fut.result() or []
                ofertas_totales.extend(res)
                actualizar_conteo_portal(nombre_p, len(res), "OK")
            except Exception as e:
                actualizar_conteo_portal(nombre_p, 0, f"WARN: {str(e)[:40]}")

    # Portales SPA con Playwright Headless Brave
    res_pw = buscar_portales_playwright(portales, modo, palabras_clave)
    for nombre_pw, lista_pw in res_pw.items():
        if nombre_pw in portales:
            ofertas_totales.extend(lista_pw)
            actualizar_conteo_portal(nombre_pw, len(lista_pw), "OK")

    # Deduplicar por URL limpia preservando orden de prioridad
    vistos = set()
    unicas = []
    for of in ofertas_totales:
        u_key = (of.get("url_oferta") or "").split("?")[0].rstrip("/")
        if not u_key or u_key in vistos:
            continue
        vistos.add(u_key)
        unicas.append(of)

    return unicas
