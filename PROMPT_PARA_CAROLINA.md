# 🚀 Prompt Maestro para Configurar y Ejecutar AutoPostula con los Datos de Carolina (Windows 11)

Copia y pega el siguiente prompt completo a cualquier asistente o agente de IA (como Antigravity, Claude Code, Cursor, Gemini o ChatGPT) en tu computador con **Windows 11**.

El agente se encargará de configurar el entorno de forma 100% automática, crear tu perfil personalizado y dejar el bot corriendo en tu pantalla con la ventanita interactiva para que revises cada postulación.

---

```markdown
Eres mi agente técnico de automatización laboral en Windows 11. Necesito que configures y ejecutes la herramienta "AutoPostula" para postular a prácticas profesionales en portales laborales de Chile (FirstJob, Trabajando.cl, Computrabajo, etc.), adaptándola al 100% con mis antecedentes personales y académicos.

Aquí están mis datos para la práctica profesional:

1. DATOS PERSONALES:
- Nombre Completo: [Escribe tu Nombre y Apellidos, ej: Carolina Morales Soto]
- RUT: [Escribe tu RUT con guión, ej: 20.123.456-7]
- Teléfono / WhatsApp: [Escribe tu número con +56 9, ej: +56 9 1234 5678]
- Correo Personal de Contacto: [Escribe tu correo de contacto, ej: carolina.morales@gmail.com]
- Correo Institucional: [Escribe tu correo de alumna, ej: c.morales@duocuc.cl]
- Comuna de Residencia: [Escribe tu comuna y región, ej: Santiago Centro, Región Metropolitana]
- Facilidad de Traslado: Total disponibilidad diurna para trasladarme en transporte público / metro dentro de la RM.
- Licencia de Conducir: [Indica si cuentas con Clase B o no cuentas con licencia por el momento]

2. SITUACIÓN ACADÉMICA:
- Institución: [Ej: Duoc UC / Inacap / Universidad Santo Tomás / etc.]
- Sede: [Ej: Sede Antonio Varas / Sede San Joaquín / etc.]
- Carrera: [Ej: Ingeniería en Informática / Analista Programador / Ingeniería en Infraestructura]
- Nivel: [Ingeniería / Técnico]
- Año que Cursas: [Ej: 4to año (cuarto año, 8vo semestre de egreso)]
- Jornada: [Vespertino (desde las 19:00 hrs) o Diurno]

3. CONDICIONES DE PRÁCTICA:
- Horas Cronológicas Mínimas: [Ej: 360 horas cronológicas]
- Seguro Escolar: Cuento con Seguro Escolar de Accidentes bajo la Ley N° 16.744 otorgado por mi institución, con vigencia activa durante todo el periodo.
- Carta de Autorización: Sí, cuento con la Carta de Autorización y presentación de práctica emitida por mi institución, lista para entrega inmediata.
- Disponibilidad: Inmediata para jornada completa diurna (40 a 45 hrs semanales de lunes a viernes).
- Disposición de Extensión: Total disposición a extender el periodo si el equipo o proyecto lo requiere.
- Modalidad: Presencial, híbrida o remota.

4. CONDICIONES LEGALES Y RENTA:
- Pretensión de Renta: $0 (Acorde a la asignación o bono de movilización que tenga contemplada la empresa para alumnos en práctica). Si piden número entero estricto, colocar 0.
- Ley de Inclusión N° 21.015: No requiero ajustes ni apoyos adicionales para el desempeño normal y eficiente de las funciones del cargo.

5. MIS COMPETENCIAS TÉCNICAS Y ÁREAS DE INTERÉS:
- Áreas de Interés: [Ej: Desarrollo de Software, QA / Testing, Cloud, Redes, Soporte TI, Análisis de Datos]
- Lenguajes y Herramientas: [Ej: Python, JavaScript, SQL, Git, Linux, Docker, etc.]
- Breve Motivación: [Ej: Busco integrarme a un equipo dinámico donde pueda aportar soluciones reales, aprender de tecnologías modernas y consolidar mi crecimiento profesional.]

---

INSTRUCCIONES PARA EL AGENTE EN WINDOWS 11:

1. CLONAR EL REPOSITORIO OFICIAL:
   Abre una terminal (PowerShell o CMD) y ejecuta:
   git clone https://github.com/lascsentinel-commits/AutoPostula.git
   cd AutoPostula

2. CREAR EL ARCHIVO DE PERFIL `perfil_alumno.json`:
   Copia la plantilla `perfil_alumno_template.json` a `perfil_alumno.json` y reemplaza todos los campos con los datos de Carolina entregados arriba. El bot leerá este archivo automáticamente sin necesidad de tocar código.

3. CONFIGURAR LA LLAVE DE GEMINI:
   Crea el archivo `.env` en la raíz de `AutoPostula/` con la siguiente variable:
   GEMINI_API_KEY=tu_api_key_de_gemini
   (Se puede obtener gratis en https://aistudio.google.com/apikey).

4. ELEGIR EL MÉTODO DE EJECUCIÓN EN WINDOWS 11:
   Tienes tres alternativas disponibles:

   👉 OPCIÓN A: NATIVA EN WINDOWS 11 (RECOMENDADA, LA MÁS FÁCIL)
   - Simplemente haz doble clic en el archivo `iniciar_windows.bat` (o ejecuta `.\iniciar_windows.ps1` en PowerShell).
   - El script creará el entorno `venv`, instalará dependencias (`requirements.txt`), abrirá automáticamente Brave o Google Chrome con `--remote-debugging-port=9222` y arrancará el bot.

   👉 OPCIÓN B: WSL2 (UBUNTU EN WINDOWS 11)
   - Si prefieres un entorno Linux dentro de Windows 11, abre PowerShell y ejecuta `wsl`.
   - Dentro de Ubuntu en WSL2:
     sudo apt update && sudo apt install -y python3-pip python3-venv
     cd AutoPostula
     python3 -m venv venv && source venv/bin/activate
     pip install -r requirements.txt
     python3 bucle_pantalla_interactivo.py
   - Nota: El navegador puede ser el de Windows conectándose a `localhost:9222`.

   👉 OPCIÓN C: DOCKER DESKTOP
   - Si tienes Docker Desktop instalado en Windows 11:
     docker compose up --build

5. CÓMO POSTULAR Y USAR EL PANEL INTERACTIVO EN PANTALLA:
   - En el navegador abierto con el puerto 9222, inicia sesión en tus cuentas de Trabajando.cl, FirstJob y portales de empleo.
   - Deja abiertas las pestañas de las ofertas de práctica a las que quieras postular.
   - En la esquina inferior izquierda de cada oferta aparecerá una pastilla azul: `[ ⏸️ En Marcha | 30s | ⚙️ ]`.
   - Al hacer clic en la pastilla, se desplegará una ventanita con controles:
     * `[ ⏸️ PAUSAR BOT ]` / `[ ▶️ REANUDAR BOT ]`: Pausa el bot de inmediato para que puedas leer o cambiar cualquier respuesta con calma.
     * Selectores de tiempo `[ 15s ]`, `[ 30s ]`, `[ 60s ]`, `[ 2m ]`: Ajusta cuántos segundos tienes para revisar antes del envío.
     * `[ 🚀 Enviar Postulación Ahora ]`: Si ya revisaste y todo está perfecto, pulsa este botón y el bot enviará la postulación de inmediato sin esperar el temporizador.
     * `[ 🛑 Detener Bot por Completo ]`: Detiene el bot con seguridad si deseas salir.
```

---

## 💡 Consejos de Seguridad y Éxito
- **Tus credenciales nunca se suben a ningún sitio**: Las sesiones de tus portales quedan guardadas en tu propio navegador en tu computador.
- **Tu CV**: Puedes dejar tu archivo `cv.pdf` en la carpeta principal de `AutoPostula/` para que los portales lo adjunten de forma automática.
- **Confirmación en Vivo**: Nunca se cerrará ninguna pestaña sin que veas en pantalla el mensaje de éxito de postulación confirmada.
