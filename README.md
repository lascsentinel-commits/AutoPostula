# 🪟 AutoPostula · Edición Windows 11 (Postulación Asistida con IA sobre Pantalla Real)

> **💻 Sistema Operativo Principal:** **Windows 11** (Brave / Chrome / Edge vía CDP puerto `9222`), compatible también con WSL2 y Docker.  
> **🐧 ¿Buscas la versión nativa para Linux Debian / Ubuntu?** Mantuvimos el repositorio dedicado de Linux en: [lascsentinel-commits/AutoPostula-Linux-Debian](https://github.com/lascsentinel-commits/AutoPostula-Linux-Debian). Ambas ediciones comparten funcionalidades y la guía técnica cruzada en [`GUIA_PORTABILIDAD_WINDOWS_LINUX.md`](./GUIA_PORTABILIDAD_WINDOWS_LINUX.md).

Sistema de postulación asistida y automática a ofertas de **Prácticas Profesionales y Empleos Técnicos** en los 14 principales portales laborales de Chile (**FirstJob, Trabajando.cl, Computrabajo, Laborum, ChileTrabajos, DuocLaboral, LinkedIn, Get on Board, Prácticas Chile, Indeed, BNE, Reqlut, Talent.com/Buk, Empleos Públicos**).

A diferencia de los bots headless tradicionales que son bloqueados por Cloudflare o llenan formularios a ciegas, **AutoPostula interactúa sobre tu navegador real (Brave / Chromium / Edge vía CDP)**:
- 👁️ **Visualización en Vivo:** Ves exactamente cada pestaña que se abre y cada respuesta que se ingresa.
- 🔍 **Visor y Botón «Revisar Válidas (14 Portales)» (`http://localhost:8087` + widget):** Muestra un cuadro destacado y el número total en grande, separa **Válidas Disponibles**, **Postulados Confirmados**, **Pausadas / CAPTCHA / Login**, **Ofertas Cerradas** y **Otras en Cola IA**, con lista seleccionable, descripción completa, enlace directo para abrirla y botón para lanzar una oferta puntual.
- 🧠 **Memoria Activa de Respuestas (`/memoria`):** Cualquier edición que hagas en pantalla se guarda automáticamente y cuentas con panel CRUD web para preguntas y respuestas.
- 🤖 **IA Contextual (Gemini):** Responde preguntas técnicas de reclutadores, motivación de empresa, horas y disponibilidad usando el perfil auténtico del alumno.
- ⏱️ **Ventanita Flotante de Control (`v4.9` con watchdog de latido 10s):** Pastilla y panel modal desplegable en la esquina inferior izquierda:
  - `[ ⏸️ Pausar Bot ]` / `[ ▶️ Reanudar Bot ]` y selectores `[ 15s ]`, `[ 30s ]`, `[ 60s ]`, `[ 2m ]` + límite de pestañas (`- / +`).
  - `[ 🔊 Leer Preguntas y Respuestas: ON/OFF ]` + `[ 🔇 Lectura Auto Descripción ]`.
  - `[ 🚀 Enviar Postulación Ahora ]`, `[ ⬅️ Link anterior ]`, `[ ⏭️ Siguiente oferta ]`.
  - `[ 🕵️ Agente investigador ]`, `[ 🧠 Ver / Editar Memoria (Q&A) ]`, `[ 🔍 Revisar Válidas (14 Portales) ]` y `[ 🛑 Detener Bot por Completo ]`.
- ⏱️ **Espera Post-Envío de 35s + Aviso 5s Antes:** Tras confirmar postulación, anuncia *"Ya postulamos a {empresa}, esperaré 35 segundos para cerrar la pestaña"* y *"Cerrando"* 5s antes de cerrar la pestaña.
- 🛡️ **Verificación Estricta y Portales Mapeados:** Detección de páginas 404/cerradas (`No podemos encontrar esta página` / `Ver el aviso finalizado`), Google OAuth en `FirstJob` y `Workday`, actualización de CV PDF vía Jobi en `Laborum`, confirmación `/candidate/postapply` en `Computrabajo`, y respeto estricto de CAPTCHAs sin automatizar. Ver detalles técnicos y compatibilidad Windows/Linux en [`GUIA_PORTABILIDAD_WINDOWS_LINUX.md`](./GUIA_PORTABILIDAD_WINDOWS_LINUX.md).

---

## 🪟 Ejecución en Windows 11

AutoPostula funciona de forma nativa en **Windows 11**:

### Opción A: 1-Clic con Script por Lotes (Recomendado)
1. Clona el repositorio en Windows:
   ```cmd
   git clone https://github.com/lascsentinel-commits/AutoPostula.git
   cd AutoPostula
   ```
2. Haz doble clic sobre **`iniciar_windows.bat`** (o ejecuta `.\iniciar_windows.ps1` en PowerShell).
3. El lanzador configurará el entorno virtual `venv`, instalará dependencias, levantará Brave o Chrome en el puerto 9222 y arrancará el bot.

### Opción B: WSL2 (Ubuntu en Windows 11)
Si prefieres Linux dentro de Windows 11, puedes usar WSL2 con WSLg:
```bash
wsl
cd AutoPostula
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 bucle_pantalla_interactivo.py
```

### Opción C: Contenedor Docker
```bash
docker compose up --build
```

---

## 🐧 Ejecución en Linux

### 1. Clonar el Repositorio
```bash
git clone https://github.com/lascsentinel-commits/AutoPostula.git
cd AutoPostula
```

### 2. Instalar Dependencias
```bash
pip install playwright google-genai
playwright install chromium
```

### 3. Configurar API Key de Gemini
Obtén tu clave gratuita en [Google AI Studio](https://aistudio.google.com/):
```bash
cp .env.example .env
# Edita .env y añade tu clave:
# GEMINI_API_KEY=tu_clave_de_gemini
```

---

## 🖥️ Cómo Ejecutar en Pantalla

### Paso 1: Abrir Brave con Depuración Remota (Puerto 9222)
Asegúrate de que Brave esté cerrado y lánzalo con el puerto de depuración:
```bash
brave --remote-debugging-port=9222 &
```
*(Inicia sesión manualmente en tus portales preferidos: FirstJob, Trabajando.cl, Computrabajo, etc.)*

### Paso 2: Lanzar el Bucle Interactivo con Pausa de Revisión
```bash
./bot_pantalla.sh --segundos 30
```
- El bot tomará las ofertas pendientes, abrirá cada una en una pestaña, rellenará las preguntas y te dará 30 segundos de revisión antes de enviar.
- Si necesitas más tiempo, haz clic en **`[ ⏸️ Pausar ]`** en el widget flotante inferior izquierdo.

---

## 📋 Adaptar para otro Alumno (Plantilla de Perfil)

Revisa el archivo **[`CUESTIONARIO_ALUMNO_PRACTICAS.md`](./CUESTIONARIO_ALUMNO_PRACTICAS.md)** y completa la plantilla **[`perfil_alumno_template.json`](./perfil_alumno_template.json)** con tus datos:
1. **Datos Personales:** Nombre, RUT, teléfono, comuna, correo de contacto.
2. **Situación Académica:** Carrera, institución, sede, año de carrera (ej. *4to año*), semestre.
3. **Condiciones de Práctica:** Horas cronológicas requeridas (ej. 360 hrs), seguro escolar Ley 16.744, carta de autorización al día.
4. **Competencias y Motivación:** Áreas de interés y stack tecnológico para personalizar las respuestas abiertas.

---

## 🌐 Portales Soportados
- **FirstJob** (`firstjob.me`)
- **Trabajando.cl** (`trabajando.cl`)
- **Computrabajo** (`computrabajo.cl`)
- **Laborum** (`laborum.cl`)
- **ChileTrabajos** (`chiletrabajos.cl`)
- **Prácticas Chile / Servicio Civil** (`practicaschile.cl`)
