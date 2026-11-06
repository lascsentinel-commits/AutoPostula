# 🚀 Prompt Maestro para Configurar y Ejecutar AutoPostula con los Datos de Carolina

Copia y pega el siguiente prompt completo a cualquier asistente de IA (como Antigravity, Claude, ChatGPT o Cursor) junto con tus datos personales. El asistente se encargará de configurar todo el entorno y dejar el bot corriendo en tu pantalla.

---

```markdown
Eres mi asistente técnico de postulación laboral en Chile. Necesito que configures y ejecutes la herramienta "AutoPostula" para postular a prácticas profesionales en mis portales laborales (FirstJob, Trabajando.cl, Computrabajo, etc.), adaptándola al 100% con mis antecedentes personales y académicos.

Aquí están mis datos para la práctica:

1. DATOS PERSONALES:
- Nombre Completo: [Escribe tu Nombre y Apellidos, ej: Carolina Morales Soto]
- RUT: [Escribe tu RUT con guión, ej: 20.123.456-7]
- Teléfono / WhatsApp: [Escribe tu número con +56 9, ej: +56 9 1234 5678]
- Correo Personal: [Escribe tu correo de contacto, ej: carolina@gmail.com]
- Correo Institucional: [Escribe tu correo de alumna, ej: c.morales@duocuc.cl]
- Comuna de Residencia: [Escribe tu comuna y región, ej: Providencia, Región Metropolitana]
- Facilidad de Traslado: Total disponibilidad diurna para trasladarme dentro de la Región Metropolitana.
- Licencia de Conducir: [Indica si tienes Clase B o no tienes licencia]

2. SITUACIÓN ACADÉMICA:
- Institución: [Ej: Duoc UC / Inacap / Universidad]
- Sede: [Ej: Sede Antonio Varas / Santiago Centro]
- Carrera: [Ej: Ingeniería en Informática / Analista Programador / Ingeniería en Infraestructura]
- Año que Cursas: [Ej: 4to año (cuarto año, 8vo semestre de egreso)]
- Jornada: [Vespertino (desde las 19:00 hrs) o Diurno]

3. CONDICIONES DE PRÁCTICA:
- Horas Cronológicas Mínimas: [Ej: 360 horas cronológicas]
- Seguro Escolar: Cuento con Seguro Escolar de Accidentes bajo la Ley N° 16.744 otorgado por mi institución, con vigencia activa.
- Carta de Autorización: Sí, cuento con la Carta de Autorización y presentación de práctica profesional emitida por mi institución.
- Disponibilidad: Inmediata para jornada completa diurna (40 a 45 hrs semanales de lunes a viernes).
- Posibilidad de Extender Horas: Total disposición a extender el periodo si la empresa o el proyecto lo requiere.
- Modalidad: Total disponibilidad para trabajo presencial o híbrido.

4. CONDICIONES LEGALES Y RENTA:
- Pretensión de Renta: $0 (Acorde a la asignación o bono de movilización que tenga contemplada la empresa). Si piden número entero, poner 0.
- Ley de Inclusión N° 21.015: No requiero ajustes ni apoyos adicionales para el desempeño de mis funciones.

5. MIS COMPETENCIAS TÉCNICAS Y ÁREAS DE INTERÉS:
- Áreas de Interés: [Ej: Desarrollo Web, Calidad / QA, Soporte TI, Redes, Cloud, Análisis de Datos]
- Herramientas y Lenguajes que conozco: [Ej: Python, SQL, JavaScript, Linux, Git, etc.]
- Proyectos o logros: [Breve mención de algún proyecto que hayas hecho en la carrera]

---

INSTRUCCIONES PARA EL ASISTENTE:
1. Clona el repositorio oficial público:
   git clone https://github.com/lascsentinel-commits/AutoPostula.git
   cd AutoPostula

2. Instala las dependencias:
   pip install playwright google-genai
   playwright install chromium

3. Crea el archivo .env con la API Key de Gemini:
   GEMINI_API_KEY=tu_api_key_de_gemini

4. Edita el archivo `modules/smart_qa_solver.py` reemplazando el bloque `SYSTEM_PROMPT_DHANI` con mis datos listados arriba.
   Asegúrate de:
   - Que siempre responda de forma profesional en primera persona ("Cuento con...", "Tengo total disponibilidad...").
   - Que cuando pregunten por el año, indique explícitamente mi año de carrera (ej. 4to año).
   - Que JAMÁS responda "N/A" ni "No aplica" a preguntas de motivación; siempre debe redactar un párrafo motivado y positivo adaptado a la empresa y al cargo.

5. Inicia el navegador Brave con depuración remota:
   brave --remote-debugging-port=9222 &
   (Esperar que inicie sesión en FirstJob, Trabajando.cl o Computrabajo).

6. Ejecuta el bucle de postulación en pantalla con revisión interactiva de 30 segundos:
   ./bot_pantalla.sh --segundos 30

7. Explícame cómo funciona la pantalla:
   - El bot abrirá cada oferta en una pestaña.
   - Completará los campos y preguntas con IA.
   - En la esquina inferior izquierda veré un widget neón flotante con un timer de 30 segundos.
   - Si quiero revisar con calma, puedo hacer clic en [ ⏸️ Pausar Bot ].
   - Cuando esté lista, hago clic en [ ▶️ Reanudar Bot ] o en el botón "Postular" del portal.
   - El bot nunca cerrará una pestaña si hubo un error o falta confirmación.
```
