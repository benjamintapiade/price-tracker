"""
Revisa, corriendo en TU PC (no en la nube), los productos que quedaron
fuera del bot automatizado porque sus tiendas bloquean tráfico
automatizado desde IPs de centros de datos:

  - Andesgear: devuelve 403 Forbidden (bloqueo a nivel de firewall/CDN)
  - Ripley: muestra un CAPTCHA de Cloudflare

Desde tu propia IP (residencial) estos sitios funcionan normalmente —
por eso este script existe aparte del bot en la nube, para correrlo tú
mismo de vez en cuando cuando quieras chequear estos 4 productos.

Usa un historial separado (historial_precios_locales.json) para no
mezclarse con el historial que mantiene el bot en la nube (que vive en
el repo de GitHub) — evita cualquier conflicto de git entre ambos.

Uso:
    python revisar_locales.py
"""

from run_scrapers import cargar_productos, revisar_precios
from historial import cargar_historial, guardar_historial
from bot_runner import construir_reporte_completo
from notificar import enviar_telegram

RUTA_PRODUCTOS_LOCALES = "productos_locales.json"
RUTA_HISTORIAL_LOCAL = "historial_precios_locales.json"


def main() -> None:
    productos = cargar_productos(RUTA_PRODUCTOS_LOCALES)
    resultados = revisar_precios(productos)

    historial = cargar_historial(RUTA_HISTORIAL_LOCAL)
    reporte = construir_reporte_completo(resultados, historial)
    print()
    print(reporte)

    if enviar_telegram(reporte):
        print("\nReporte enviado por Telegram.")
    else:
        print("\nNo se pudo enviar por Telegram (revisa telegram_config.json).")

    historial.update({r["id"]: r["precio"] for r in resultados})
    guardar_historial(historial, RUTA_HISTORIAL_LOCAL)


if __name__ == "__main__":
    main()
