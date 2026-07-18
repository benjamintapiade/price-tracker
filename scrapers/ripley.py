"""
Scraper de precios para simple.ripley.cl (requiere Playwright)

Ripley corre sobre VTEX (una plataforma de e-commerce muy usada en
Latinoamérica) y, al igual que Andesgear, renderiza el precio con
JavaScript — no viene en el HTML inicial. Por eso necesita un navegador
real (headless) en vez de solo `requests`.

Este scraper intenta tres métodos, en orden de confiabilidad:

1. JSON-LD (schema.org/Product): VTEX casi siempre inyecta un bloque
   <script type="application/ld+json"> con el precio dentro de "offers".
   Es la fuente más limpia y estable. Se busca recursivamente el campo
   "price" porque VTEX a veces anida el Product dentro de otras
   estructuras (@graph, listas, etc.).

2. data-testid del precio: los componentes de VTEX suelen etiquetar el
   precio con atributos data-testid como "price-value". Se usa como
   segundo intento si no hubo JSON-LD.

3. Fallback por texto: busca un precio con formato chileno ($XXX.XXX)
   en el texto visible de la página ya renderizada. Confirmado que el
   precio aparece así ("$129.990") al inspeccionar la página. Es el
   respaldo más frágil pero siempre disponible.

OJO: no se pudo confirmar directamente cuál de los métodos 1 o 2 aplica,
porque las herramientas disponibles solo dejaron ver el texto renderizado
(sin etiquetas ni atributos). Al correrlo, el campo "metodo" del
resultado te dirá cuál se activó. Si cae siempre al fallback y quieres
algo más robusto, avísame y ajustamos el selector con las DevTools.

Requisitos (instalar una sola vez, en tu máquina):
    pip install playwright
    playwright install chromium
"""

import json
import re
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _buscar_precio_en_json_ld(obj) -> float | None:
    """Busca recursivamente un campo 'price' dentro de una estructura
    JSON-LD (que puede venir anidada en @graph, listas, offers, etc.)."""
    if isinstance(obj, dict):
        # Preferimos el price que esté dentro de "offers" (el del producto)
        if "offers" in obj:
            precio = _buscar_precio_en_json_ld(obj["offers"])
            if precio is not None:
                return precio
        for clave in ("price", "lowPrice", "highPrice"):
            if clave in obj:
                try:
                    return float(obj[clave])
                except (TypeError, ValueError):
                    pass
        for valor in obj.values():
            precio = _buscar_precio_en_json_ld(valor)
            if precio is not None:
                return precio
    elif isinstance(obj, list):
        for item in obj:
            precio = _buscar_precio_en_json_ld(item)
            if precio is not None:
                return precio
    return None


def _extraer_de_json_ld(page) -> float | None:
    scripts = page.query_selector_all('script[type="application/ld+json"]')
    for script in scripts:
        contenido = script.inner_text()
        try:
            data = json.loads(contenido)
        except (TypeError, ValueError):
            continue
        precio = _buscar_precio_en_json_ld(data)
        if precio is not None:
            return precio
    return None


def _extraer_de_testid(page) -> float | None:
    el = page.query_selector('[data-testid="price-value"]')
    if el is None:
        return None
    texto = el.inner_text()
    match = re.search(r"(\d{1,3}(?:\.\d{3})+)", texto)
    if match:
        return float(match.group(1).replace(".", ""))
    return None


def _extraer_de_texto_visible(page) -> float | None:
    texto = page.inner_text("body")
    match = re.search(r"\$\s?(\d{1,3}(?:\.\d{3})+)", texto)
    if match:
        return float(match.group(1).replace(".", ""))
    return None


def scrape_ripley(url: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)

        # Igual que en Andesgear: "networkidle" se cuelga en sitios con
        # trackers/analytics que nunca dejan la red del todo quieta.
        # Usamos "domcontentloaded" y esperamos explícitamente a que
        # aparezca el título del producto (h1) como señal de que el
        # contenido principal ya renderizó.
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_selector("h1", timeout=15000)
        except PlaywrightTimeoutError:
            pass  # seguimos igual; probamos extraer con lo que haya cargado

        precio = _extraer_de_json_ld(page)
        metodo = "json_ld"

        if precio is None:
            precio = _extraer_de_testid(page)
            metodo = "data_testid"

        if precio is None:
            precio = _extraer_de_texto_visible(page)
            metodo = "texto_visible"

        titulo_el = page.query_selector("h1")
        nombre = titulo_el.inner_text().strip() if titulo_el else url

        diagnostico = None
        if precio is None:
            titulo_pagina = page.title()
            texto_pagina = page.inner_text("body")[:300]
            diagnostico = (
                f"Título de la página: {titulo_pagina!r}. "
                f"Primeros 300 caracteres: {texto_pagina!r}"
            )

        browser.close()

    if precio is None:
        raise ValueError(
            f"No se pudo extraer el precio de {url} con ninguno de los "
            "tres métodos. Puede que Ripley haya cambiado su estructura, "
            f"o haya bloqueado al navegador. Diagnóstico: {diagnostico}"
        )

    return {
        "tienda": "Ripley",
        "nombre": nombre,
        "precio": precio,
        "moneda": "CLP",
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metodo": metodo,
    }


if __name__ == "__main__":
    resultado = scrape_ripley(
        "https://simple.ripley.cl/parka-pluma-volker-hombre-doite-mpm10001835901"
    )
    for k, v in resultado.items():
        print(f"{k}: {v}")
