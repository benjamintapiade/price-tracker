"""
Envía notificaciones de Telegram cuando un producto baja de precio.

Requiere un bot de Telegram propio (gratis, se crea en ~2 minutos):

  1. Abre Telegram y busca el bot @BotFather.
  2. Envíale /newbot y sigue las instrucciones (nombre + username del bot).
     Te va a entregar un TOKEN como "123456789:ABCdefGhIJKlmNoPQRstuVwXyZ".
  3. Busca tu bot recién creado por su username y mándale cualquier mensaje
     (ej. "hola") para "activar" la conversación.
  4. Corre en una terminal, reemplazando TU_TOKEN:
         python -c "from notificar import obtener_chat_id; obtener_chat_id('TU_TOKEN')"
     Esto te imprime tu chat_id.
  5. Crea un archivo telegram_config.json (junto a este archivo) así:
         {
           "bot_token": "TU_TOKEN_AQUI",
           "chat_id": "TU_CHAT_ID_AQUI"
         }

IMPORTANTE: telegram_config.json tiene credenciales — no lo subas a
GitHub más adelante (cuando lleguemos al paso de automatización, lo
agregamos al .gitignore).
"""

import json
import requests

CONFIG_PATH = "telegram_config.json"


def _cargar_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8-sig") as f:
            contenido = f.read()
    except FileNotFoundError:
        raise RuntimeError(
            f"No encontré {CONFIG_PATH}. Crea ese archivo con tu bot_token "
            "y chat_id (ver instrucciones al inicio de notificar.py)."
        )

    if not contenido.strip():
        raise RuntimeError(
            f"{CONFIG_PATH} existe pero está vacío. Asegúrate de guardar "
            "el contenido JSON con bot_token y chat_id antes de cerrar el "
            "archivo."
        )

    try:
        return json.loads(contenido)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"{CONFIG_PATH} no tiene un JSON válido ({e}). Revisa que las "
            'comillas sean rectas ("), no "curvas" (a veces Word o el '
            "autocorrector las cambia), y que no falten llaves o comas."
        )


def obtener_chat_id(bot_token: str) -> None:
    """Imprime el chat_id de la última persona que le escribió al bot.

    Uso: manda un mensaje cualquiera al bot en Telegram PRIMERO, y
    después corre esta función con tu token.
    """
    resp = requests.get(
        f"https://api.telegram.org/bot{bot_token}/getUpdates", timeout=15
    )
    resp.raise_for_status()
    data = resp.json()

    resultados = data.get("result", [])
    if not resultados:
        print(
            "No hay mensajes todavía. Manda un mensaje cualquiera a tu bot "
            "en Telegram y vuelve a intentar."
        )
        return

    chat_id = resultados[-1]["message"]["chat"]["id"]
    print(f"Tu chat_id es: {chat_id}")


def enviar_telegram(mensaje: str) -> bool:
    """Envía un mensaje de texto al chat configurado.

    Devuelve True si Telegram confirmó el envío, False si algo falló.
    """
    config = _cargar_config()
    bot_token = config["bot_token"]
    chat_id = config["chat_id"]

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    resp = requests.post(
        url, data={"chat_id": chat_id, "text": mensaje}, timeout=15
    )

    if resp.status_code != 200:
        print(f"[ERROR] Telegram devolvió {resp.status_code}: {resp.text}")
        return False

    return True


if __name__ == "__main__":
    ok = enviar_telegram("🔔 Prueba del price-tracker: si ves esto, ¡funciona!")
    print("Enviado correctamente" if ok else "Falló el envío")
