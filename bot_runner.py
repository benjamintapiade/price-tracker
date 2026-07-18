"""
Bot de reporte de precios, pensado para correr en GitHub Actions.

Se gatilla de dos formas:
  - Automáticamente cada 12 horas (el cron del workflow).
  - Manualmente, cuando aprietas "Run workflow" en la pestaña Actions
    de GitHub (útil si le mandaste un mensaje al bot y quieres el reporte
    al instante, sin esperar a la próxima corrida automática).

En cualquiera de esos dos casos revisa TODOS los precios y te manda por
Telegram la lista completa, destacando los que subieron o bajaron desde
la última revisión.

No hay ningún servidor corriendo 24/7: GitHub Actions "despierta" este
script, lo corre y se apaga. El historial de precios vive en
historial_precios.json, que el propio workflow actualiza y sube al repo
después de cada corrida (así el próximo run, aunque sea una máquina
nueva de GitHub, "recuerda" el precio anterior para comparar).

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

    Sin esto, cada corrida volvería a ver el mismo mensaje viejo para
    siempre y dispararía una revisión de precios innecesaria una y otra vez.
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

    # ¿Cómo se gatilló esta corrida? GitHub Actions define GITHUB_EVENT_NAME:
    #   - "schedule"          -> el cron automático de cada 12 h
    #   - "workflow_dispatch" -> apretaste "Run workflow" a mano en GitHub
    # En ambos casos queremos reportar SIEMPRE, sin depender de que haya
    # un mensaje nuevo. Solo cuando corres el script localmente en tu PC
    # (sin esa variable) mantenemos el comportamiento de "responde si le
    # escribiste al bot".
    evento = os.environ.get("GITHUB_EVENT_NAME")
    reportar_siempre = evento in ("schedule", "workflow_dispatch")

    updates = obtener_mensajes_nuevos(token)

    # Siempre confirmamos los mensajes vistos, así no se re-procesan luego.
    if updates:
        confirmar_mensajes(token, updates)

    if not reportar_siempre:
        # Modo local: solo seguimos si TÚ le escribiste al bot.
        mensajes_autorizados = [
            u
            for u in updates
            if str(u.get("message", {}).get("chat", {}).get("id")) == str(chat_id_autorizado)
        ]
        if not mensajes_autorizados:
            print("No hay mensajes tuyos nuevos. No se hace nada.")
            return

    print(f"Revisando {len(cargar_productos())} productos...")

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
