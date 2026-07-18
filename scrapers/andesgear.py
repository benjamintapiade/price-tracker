"""
Scraper de precios para andesgear.cl (requiere Playwright)

Andesgear corre en Magento, y a diferencia de los otros 3 sitios, el
precio no viene en el HTML inicial: se renderiza con JavaScript después
de cargar la página (por eso salía "no legible" al hacer un fetch simple
en un paso anterior). Por eso este scraper necesita un navegador real
(headless) en vez de solo `requests`.

Método principal: Magento 2 (la plataforma que usa Andesgear) casi
siempre incluye el precio en un atributo HTML `data-price-amount` dentro
de un elemento con clase "price-wrapper" — esto es parte del widget de
precios estándar de Magento, usado internamente para recalcular precios
en el navegador. Es un valor numérico limpio, mucho más confiable que
parsear "$129.990" como texto.

OJO: no se pudo confirmar directamente que Andesgear tenga este atributo
exacto, porque las herramientas disponibles no permiten ver el HTML
renderizado con atributos (solo texto ya extraído, sin etiquetas). Antes
de confiar en el método principal, revisa en el navegador con las
DevTools (F12 -> pestaña "Elements", Ctrl+F "data-price-amount") si
existe cerca del precio. Si no está, dime y ajustamos el selector — como
respaldo, el scraper cae a buscar el precio como texto visible en la
página ya renderizada.

Requisitos (instalar una sola vez, en tu máquina):
    pip install playwright
    playwright install chromium
"""

import re
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _extraer_de_data_price_amount(page) -> float | None:
    """Busca el atributo data-price-amount típico de Magento 2."""
    elementos = page.query_selector_all("[data-price-amount]")
    for el in elementos:
        valor = el.get_attribute("data-price-amount")
        if valor:
            try:
                return float(valor)
            except ValueError:
                continue
    return None


def _extraer_de_texto_visible(page) -> float | None:
    """Respaldo: busca un precio con formato chileno ($XXX.XXX) en el
    texto visible de la página ya renderizada."""
    texto = page.inner_text("body")
    match = re.search(r"\$\s?(\d{1,3}(?:\.\d{3})+)", texto)
    if match:
        return float(match.group(1).replace(".", ""))
    return None


def scrape_andesgear(url: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)

        # OJO: "networkidle" espera a que la página deje de hacer
        # peticiones de red por completo, pero muchos sitios (trackers,
        # analytics, chats en vivo) mantienen conexiones abiertas
        # indefinidamente y esa espera nunca se cumple, aunque el precio
        # ya esté cargado. Por eso usamos "domcontentloaded" (mucho más
        # rápido) y después esperamos explícitamente a que aparezca el
        # precio en el DOM, con un timeout corto que no frena el resto
        # si no aparece.
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_selector("[data-price-amount]", timeout=15000)
        except PlaywrightTimeoutError:
            pass  # seguimos igual; probamos extraer con lo que haya cargado

        precio = _extraer_de_data_price_amount(page)
        metodo = "data_price_amount"

        if precio is None:
            precio = _extraer_de_texto_visible(page)
            metodo = "texto_visible"

        titulo_el = page.query_selector("h1")
        nombre = titulo_el.inner_text().strip() if titulo_el else url

        browser.close()

    if precio is None:
        raise ValueError(
            f"No se pudo extraer el precio de {url} con ninguno de los "
            "dos métodos. Puede que Andesgear haya cambiado su "
            "estructura — revisar con las DevTools del navegador."
        )

    return {
        "tienda": "Andesgear",
        "nombre": nombre,
        "precio": precio,
        "moneda": "CLP",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metodo": metodo,
    }


if __name__ == "__main__":
    resultado = scrape_andesgear(
        "https://www.andesgear.cl/chaqueta-hombre-down-sweater-hoody-84702-om4429"
    )
    for k, v in resultado.items():
        print(f"{k}: {v}")
