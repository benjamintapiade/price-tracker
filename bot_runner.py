"""
Bot "on-demand": cuando le mandas cualquier mensaje al bot de Telegram,
este script (corrido por GitHub Actions cada 5 minutos) detecta que
llegó un mensaje tuyo, revisa TODOS los precios y te responde con la
lista completa, destacando los que subieron o bajaron desde la última
revisión.

No hay ningún servidor corriendo 24/7: GitHub Actions "despierta" este
script cada 5 minutos, revisa si hay mensajes nuevos, y si hay uno tuyo,
corre todo y te contesta por Telegram. El historial de precios vive en
historial_precios.json, que el propio workflow de GitHub Actions
actualiza y sube al repo después de cada corrida (así el próximo run,
aunque sea una máquina nueva de GitHub, "recuerda" el precio anterior).

Seguridad: solo reacciona a mensajes que vengan de TU chat_id (el que
configuraste). Si alguien más le escribe al bot, el mensaje se descarta
sin gastar minutos de Actions en scrapear nada.

Config de credenciales: primero busca las variables de entorno
TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID (así corre en GitHub Actions,
usando GitHub Secrets). Si no las encuentra, cae a leer
telegram_config.json (para poder probarlo en tu PC también).
"""

import json
import os

import requests

from run_scrapers import cargar_productos, revisar_precios
from historial import cargar_historial, guardar_historial


def _config_telegram() -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        return token, chat_id

    with open("telegram_config.json", encoding="utf-8") as f:
        config = json.load(f)
    return config["bot_token"], str(config["chat_id"])


def obtener_mensajes_nuevos(token: str) -> list[dict]:
    resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15)
    resp.raise_for_status()
    return resp.json().get("result", [])


def confirmar_mensajes(token: str, updates: list[dict]) -> None:
    """Le dice a Telegram "ya vi estos mensajes, no me los vuelvas a mandar".

    Sin esto, cada corrida (cada 5 min) volvería a ver el mismo mensaje
    viejo para siempre y dispararía una revisión de precios innecesaria
    una y otra vez.
    """
    if not updates:
        return
    ultimo_id = max(u["update_id"] for u in updates)
    requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        params={"offset": ultimo_id + 1},
        timeout=15,
    )


def construir_reporte_completo(resultados: list[dict], historial: dict) -> str:
    """Arma el reporte con TODOS los productos, marcando los que cambiaron."""
    lineas = ["📋 <b>Precios actuales:</b>"]
    for r in resultados:
        anterior = historial.get(r["id"])
        precio_actual = r["precio"]

        if anterior is None:
            marca = "🆕 "
        elif precio_actual < anterior:
            marca = f"⬇️ (bajó ${anterior - precio_actual:,.0f}) "
        elif precio_actual > anterior:
            marca = f"⬆️ (subió ${precio_actual - anterior:,.0f}) "
        else:
            marca = ""

        lineas.append(f"{marca}{r['id']} ({r['tienda']}): ${precio_actual:,.0f}")

    return "\n".join(lineas)


def enviar_respuesta(token: str, chat_id: str, mensaje: str) -> None:
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": mensaje, "parse_mode": "HTML"},
        timeout=15,
    )


def main() -> None:
    token, chat_id_autorizado = _config_telegram()

    updates = obtener_mensajes_nuevos(token)
    if not updates:
        print("No hay mensajes nuevos. No se hace nada.")
        return

    mensajes_autorizados = [
        u
        for u in updates
        if str(u.get("message", {}).get("chat", {}).get("id")) == str(chat_id_autorizado)
    ]

    # Confirmamos TODOS los mensajes vistos (autorizados o no), para no
    # volver a procesarlos en la próxima corrida.
    confirmar_mensajes(token, updates)

    if not mensajes_autorizados:
        print("Había mensajes nuevos, pero de otro chat_id. Se ignoran.")
        return

    print(f"Mensaje recibido de tu chat_id. Revisando {len(cargar_productos())} productos...")

    productos = cargar_productos()
    resultados = revisar_precios(productos)

    historial = cargar_historial()
    reporte = construir_reporte_completo(resultados, historial)
    enviar_respuesta(token, chat_id_autorizado, reporte)

    historial.update({r["id"]: r["precio"] for r in resultados})
    guardar_historial(historial)

    print("Reporte enviado y historial actualizado.")


if __name__ == "__main__":
    main()
