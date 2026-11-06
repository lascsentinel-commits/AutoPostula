import argparse
import os
import sys
import time
from datetime import datetime, timedelta

# Asegurar path correcto
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from database import (
    PORTALES_SOPORTADOS,
    actualizar_ultimo_escaneo_scheduler,
    esta_postulado,
    guardar_estado_scheduler,
    init_db,
    obtener_estado_scheduler,
    obtener_filtros,
    obtener_perfil,
    registrar_log_scheduler,
)
from modules.ai_matcher import evaluar_oferta_inteligente
from modules.auto_applier import ejecutar_autopostulacion_lote
from modules.scrapers import buscar_todas_las_practicas


def calcular_proximo_horario(horarios_str: str) -> str:
    """Devuelve el próximo horario programado en formato 'YYYY-MM-DD HH:MM'."""
    horas = [h.strip() for h in (horarios_str or "").split(",") if h.strip()]
    if not horas:
        return "Sin horarios configurados"

    ahora = datetime.now()
    candidatos = []

    for h in horas:
        try:
            parts = h.split(":")
            h_int = int(parts[0])
            m_int = int(parts[1]) if len(parts) > 1 else 0
            t_hoy = ahora.replace(hour=h_int, minute=m_int, second=0, microsecond=0)
            if t_hoy > ahora:
                candidatos.append(t_hoy)
            else:
                candidatos.append(t_hoy + timedelta(days=1))
        except Exception:
            continue

    if not candidatos:
        return "Horarios inválidos"

    candidatos.sort()
    prox = candidatos[0]
    return prox.strftime("%Y-%m-%d %H:%M")


def ejecutar_ciclo_escaneo(abrir_en_brave: bool = False, max_pestanas_brave: int = 8, usar_playwright: bool = False) -> dict:
    """Ejecuta una búsqueda completa en los 14 portales y procesa ofertas válidas."""
    init_db()
    ahora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    perfil = obtener_perfil()
    filtros = obtener_filtros()
    estado = obtener_estado_scheduler()

    modo = filtros.get("modo_busqueda", "practica_duoc")
    termino = filtros.get("termino_personalizado") or "infraestructura plataformas soporte redes cloud"
    portales_activos = filtros.get("portales_lista") or list(PORTALES_SOPORTADOS)

    print(f"[{ahora_str}] 🚀 Iniciando escaneo multi-portal ({len(portales_activos)} portales | modo={modo})...")

    # 1. Escanear ofertas reales en paralelo en los portales activos
    ofertas = buscar_todas_las_practicas(
        palabras_clave=termino,
        portales=portales_activos,
        modo=modo,
    )
    print(f"[{ahora_str}] Se recolectaron {len(ofertas)} ofertas únicas en bruto.")

    # 2. Filtrar ofertas compatibles que aún NO están postuladas
    pendientes_validas = []
    for of in ofertas:
        valida, motivo, score = evaluar_oferta_inteligente(of, filtros)
        ya_esta = esta_postulado(url_oferta=of.get("url_oferta"), titulo=of.get("titulo"), empresa=of.get("empresa"))
        if valida and not ya_esta:
            of["score_duoc"] = score
            of["motivo_duoc"] = motivo
            pendientes_validas.append(of)

    pendientes_validas.sort(key=lambda x: x.get("score_duoc", 0), reverse=True)
    print(f"[{ahora_str}] Ofertas admisibles nuevas: {len(pendientes_validas)}")

    # 3. Procesar y preparar/postular con IA
    postuladas_count = 0
    pestanas = 0
    if pendientes_validas:
        res = ejecutar_autopostulacion_lote(
            pendientes_validas,
            perfil,
            modo=modo,
            abrir_en_brave=abrir_en_brave,
            max_pestanas_brave=max_pestanas_brave,
            usar_playwright=usar_playwright,
        )
        postuladas_count = res.get("postuladas", 0)
        pestanas = res.get("pestanas_abiertas", 0)
        detalle_log = (
            f"Escaneo {modo} en {len(portales_activos)} portales: {len(ofertas)} avisos leídos, "
            f"{postuladas_count} nuevas ofertas preparadas/postuladas con IA"
            + (f" ({pestanas} abiertas en Brave)." if pestanas else ".")
        )
    else:
        detalle_log = (
            f"Escaneo {modo} en {len(portales_activos)} portales: {len(ofertas)} avisos revisados. "
            f"Sin nuevas vacantes pendientes; todo al día."
        )

    # 4. Registrar logs y actualizar próximo horario
    prox = calcular_proximo_horario(
        estado.get("horarios", "01:00, 04:00, 06:30, 08:00, 12:00, 14:00, 17:00, 22:00")
    )
    actualizar_ultimo_escaneo_scheduler(proximo_escaneo=prox, incremento_postuladas=postuladas_count)
    registrar_log_scheduler(
        ofertas_encontradas=len(ofertas),
        ofertas_postuladas=postuladas_count,
        detalle=detalle_log,
    )
    print(f"[{ahora_str}] ✅ Ciclo completado. Próximo escaneo programado: {prox}")
    return {
        "encontradas": len(ofertas),
        "nuevas_postuladas": postuladas_count,
        "pestanas_abiertas": pestanas,
        "proximo_escaneo": prox,
        "detalle": detalle_log,
    }


def main():
    parser = argparse.ArgumentParser(description="AutoPostula Daemon Scheduler 24/7 (14 Portales)")
    parser.add_argument("--once", action="store_true", help="Ejecuta un único ciclo de escaneo y termina.")
    parser.add_argument("--open-brave", action="store_true", help="Abre el top de nuevas ofertas en Brave.")
    parser.add_argument("--playwright", action="store_true", help="Intenta postulación vía sesión persistente Playwright.")
    args = parser.parse_args()

    init_db()

    if args.once:
        ejecutar_ciclo_escaneo(
            abrir_en_brave=args.open_brave,
            max_pestanas_brave=8,
            usar_playwright=args.playwright,
        )
        return

    print("🤖 AutoPostula Daemon Scheduler iniciado (Monitoreo 24/7 en 14 portales de Chile).")
    ultimo_minuto_ejecutado = ""

    while True:
        try:
            estado = obtener_estado_scheduler()
            ahora = datetime.now()
            hora_minuto = ahora.strftime("%H:%M")

            if estado.get("activo") == 1:
                horarios = [h.strip() for h in estado.get("horarios", "").split(",") if h.strip()]
                if hora_minuto in horarios and hora_minuto != ultimo_minuto_ejecutado:
                    ultimo_minuto_ejecutado = hora_minuto
                    ejecutar_ciclo_escaneo(abrir_en_brave=False, usar_playwright=False)
            else:
                ultimo_minuto_ejecutado = ""

        except Exception as e:
            print(f"Error en loop scheduler: {e}")

        time.sleep(20)


if __name__ == "__main__":
    main()
