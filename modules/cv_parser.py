import re
import os
import fitz # PyMuPDF
import pdfplumber

def extraer_texto_pdf(ruta_pdf):
    """Extrae todo el texto de un PDF usando PyMuPDF o fallback pdfplumber."""
    texto_total = ""
    try:
        doc = fitz.open(ruta_pdf)
        for pagina in doc:
            texto_total += pagina.get_text() + "\n"
        doc.close()
    except Exception as e:
        try:
            with pdfplumber.open(ruta_pdf) as pdf:
                for pag in pdf.pages:
                    t = pag.extract_text()
                    if t:
                        texto_total += t + "\n"
        except Exception as e2:
            print(f"Error extrayendo PDF: {e2}")
            return ""
            
    return texto_total.strip()

def analizar_cv(texto_cv):
    """Analiza el texto del CV y detecta campos clave para el perfil."""
    perfil_extraido = {}
    lineas = [l.strip() for l in texto_cv.splitlines() if l.strip()]

    # 1. Nombre completo (suele ser la primera linea del CV en mayúsculas)
    if lineas:
        primera_linea = lineas[0]
        if len(primera_linea) > 5 and len(primera_linea) < 50 and not any(char in primera_linea for char in ["@", "http", "+", "Curriculum"]):
            perfil_extraido["nombre"] = primera_linea.title()

    # 2. Email
    m_email = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", texto_cv)
    if m_email:
        perfil_extraido["email"] = m_email.group(0)
        
    # 3. Telefono chileno
    m_tel = re.search(r"(\+?56\s?9\s?\d{4}\s?\d{4}|\b9\s?\d{4}\s?\d{4}\b|\b\d{8,9}\b)", texto_cv)
    if m_tel:
        perfil_extraido["telefono"] = m_tel.group(0).strip()
        
    # 4. Institucion (Duoc UC u otra)
    if re.search(r"\b(duoc\s?uc|duoc)\b", texto_cv, re.IGNORECASE):
        perfil_extraido["institucion"] = "Duoc UC"
        
    # 5. Carrera informatica
    carreras = [
        "Ingeniería en Infraestructura y Plataformas Tecnológicas",
        "Ingeniero en Infraestructura y Plataformas Tecnológicas",
        "Ingeniería en Informática",
        "Ingeniero en Informática",
        "Ingeniería en Conectividad y Redes",
        "Analista Programador",
        "Técnico en Informática",
        "Técnico en Telecomunicaciones",
        "Ingeniería en Ciberseguridad"
    ]
    for c in carreras:
        if re.search(re.escape(c), texto_cv, re.IGNORECASE):
            perfil_extraido["carrera"] = c
            break

    # 6. Comuna / Ubicacion
    comunas = ["Las Condes", "Providencia", "Santiago", "Ñuñoa", "Maipú", "La Florida", "San Joaquín", "Puente Alto", "Pudahuel", "Quilicura", "Renca", "Peñalolén"]
    for com in comunas:
        if re.search(r"\b" + re.escape(com) + r"\b", texto_cv, re.IGNORECASE):
            perfil_extraido["comuna"] = com
            break
            
    # 7. Resumen profesional
    m_res = re.search(r"(?:PERFIL PROFESIONAL|RESUMEN|ACERCA DE M[IÍ]|EXTRACTO)\s*\n+(.*?)(?=\n+[A-ZÁÉÍÓÚ\s]{4,}|\Z)", texto_cv, re.DOTALL | re.IGNORECASE)
    if m_res:
        resumen_limpio = " ".join(m_res.group(1).split())[:400]
        if len(resumen_limpio) > 30:
            perfil_extraido["resumen_profesional"] = resumen_limpio
            
    # 8. Habilidades tecnicas comunes
    tech_keywords = [
        "Python", "JavaScript", "TypeScript", "React", "Node.js", "Java", "C#", "C++",
        "PHP", "HTML", "CSS", "SQL", "PostgreSQL", "MySQL", "MongoDB", "SQLite",
        "Git", "GitHub", "Docker", "Linux", "Bash", "Soporte Técnico", "Hardware",
        "Redes", "Cisco", "Windows Server", "Azure", "AWS", "Flutter", "Android",
        "FastAPI", "Django", "Flask", "Streamlit"
    ]
    encontradas = []
    for tech in tech_keywords:
        if re.search(r"\b" + re.escape(tech) + r"\b", texto_cv, re.IGNORECASE):
            encontradas.append(tech)
    if encontradas:
        perfil_extraido["habilidades_tech"] = ", ".join(encontradas)
        
    perfil_extraido["raw_cv_text"] = texto_cv
    return perfil_extraido
