"""
Recorre productos.json y llama al scraper correspondiente según el campo
"tienda" de cada entrada. Para agregar un producto nuevo, solo hay que
agregar una entrada en productos.json — no se toca este archivo ni los
scrapers, salvo que sea una tienda nueva que todavía no tenga scraper.

Para agregar una tienda nueva:
  1. Escribir scrapers/<tienda>.py con una función que reciba la URL
     y devuelva un dict (mismo formato que los otros scrapers).
  2. Agregar una línea a DISPATCH abajo.
"""

import json

from scrapers.doite import scrape_doite
from scrapers.patagonia import scrape_patagonia
from scrapers.sherpalife import scrape_sherpalife
from scrapers.andesgear import scrape_andesgear
from scrapers.ripley import scrape_ripley
from notificar import enviar_telegram

DISPATCH = {
    "doite": lambda p: scrape_doite(p["url"]),
    "patagonia": lambda p: scrape_patagonia(p["url"], talla=p.get("talla", "L")),
    "sherpalife": lambda p: scrape_sherpalife(p["url"]),
    "andesgear": lambda p: scrape_andesgear(p["url"]),
    "ripley": lambda p: scrape_ripley(p["url"]),
}


def cargar_productos(ruta: str = "productos.json") -> list[dict]:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def revisar_precios(productos: list[dict]) -> list[dict]:
    resultados = []

    for producto in productos:
        tienda = producto["tienda"]
        scraper = DISPATCH.get(tienda)

        if scraper is None:
            print(f"[SKIP] {producto['id']}: scraper de '{tienda}' aún no implementado")
            continue

        try:
            resultado = scraper(producto)
        except Exception as e:
            print(f"[ERROR] {producto['id']}: {e}")
            continue

        objetivo = producto.get("objetivo")
        bajo_objetivo = objetivo is not None and resultado["precio"] < objetivo
        resultado["id"] = producto["id"]
        resultado["objetivo"] = objetivo
        resultado["bajo_objetivo"] = bajo_objetivo
        resultados.append(resultado)

        alerta = " <-- BAJO OBJETIVO, avisar" if bajo_objetivo else ""
        print(f"[OK] {producto['id']}: ${resultado['precio']:,.0f}{alerta}")

    return resultados


def construir_mensaje_alertas(resultados: list[dict]) -> str | None:
    """Arma un mensaje consolidado con los productos bajo su objetivo.

    Devuelve None si no hay ninguno (para no mandar notificaciones vacías).
    """
    bajos = [r for r in resultados if r.get("bajo_objetivo")]
    if not bajos:
        return None

    lineas = ["🔔 Precios bajo tu objetivo:"]
    for r in bajos:
        lineas.append(
            f"- {r['id']} ({r['tienda']}): ${r['precio']:,.0f} "
            f"(objetivo: ${r['objetivo']:,.0f})\n  {r['url']}"
        )
    return "\n".join(lineas)


if __name__ == "__main__":
    productos = cargar_productos()
    resultados = revisar_precios(productos)

    mensaje = construir_mensaje_alertas(resultados)
    if mensaje:
        try:
            if enviar_telegram(mensaje):
                print("\nNotificación enviada por Telegram.")
            else:
                print("\nHabía algo que avisar, pero el envío por Telegram falló (ver error arriba).")
        except RuntimeError as e:
            print(f"\nHabía algo que avisar, pero no se pudo notificar: {e}")
    else:
        print("\nNingún producto bajo su objetivo por ahora — no se envía notificación.")
