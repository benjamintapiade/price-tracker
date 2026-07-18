"""
Scraper de precios para tiendas de la plataforma "altaventa"

Sherpalife NO corre en Shopify (es un sitio Next.js hecho a medida sobre
la plataforma "altaventa"). Resulta que varias otras tiendas chilenas
usan exactamente la misma plataforma —comparten el mismo motor, el mismo
formato de página y hasta la misma empresa (Out Company SpA)—, así que
este mismo scraper funciona para todas ellas sin cambios:

    - sherpalife.cl
    - 209sports.cl
    - safelife.cl
    - onekayak.cl
    - thearmy.cl / theclimb.cl (mismas dueñas, por si aparecen)

Por eso la función se sigue llamando scrape_sherpalife (para no romper
run_scrapers.py), pero en realidad sirve para toda la familia altaventa.
El nombre de la tienda se deduce automáticamente desde el dominio de la
URL (ver _nombre_tienda_desde_url), así el output dice "209Sports" o
"Safelife" en vez de "Sherpalife" para todos.

Métodos de extracción, en orden:

1. JSON-LD (schema.org/Product): datos estructurados en una etiqueta
   <script type="application/ld+json">. Si existe, el precio viene limpio.

2. Fallback por texto: busca el precio cerca del SKU del producto. Esto
   SÍ se confirmó que funciona, porque el HTML plano mostró el patrón
   "SKU: XXXXX ... $ NNN.NNN" tanto en sherpalife.cl como en 209sports.cl.
"""

import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Nombres "bonitos" por dominio, para que el output no diga siempre
# "Sherpalife". Si aparece un dominio nuevo de la misma plataforma que no
# esté acá, se usa el dominio tal cual como respaldo.
NOMBRES_TIENDA = {
    "sherpalife.cl": "Sherpalife",
    "209sports.cl": "209Sports",
    "safelife.cl": "Safelife",
    "onekayak.cl": "One Kayak",
    "thearmy.cl": "The Army",
    "theclimb.cl": "The Climb",
}


def _nombre_tienda_desde_url(url: str) -> str:
    dominio = urlparse(url).netloc.replace("www.", "")
    return NOMBRES_TIENDA.get(dominio, dominio)


def _extraer_de_json_ld(soup: BeautifulSoup, url: str) -> dict | None:
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue

        candidatos = data if isinstance(data, list) else [data]
        for item in candidatos:
            if not isinstance(item, dict) or item.get("@type") != "Product":
                continue
            oferta = item.get("offers", {})
            if isinstance(oferta, list):
                oferta = oferta[0] if oferta else {}
            precio = oferta.get("price")
            if precio is None:
                continue
            return {
                "tienda": _nombre_tienda_desde_url(url),
                "nombre": item.get("name", url),
                "precio": float(precio),
                "moneda": oferta.get("priceCurrency", "CLP"),
                "disponible": oferta.get("availability"),
                "url": url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metodo": "json_ld",
            }
    return None


def _extraer_por_texto_cerca_del_sku(html: str, url: str) -> dict | None:
    match = re.search(r"SKU:\s*\S+.{0,200}?\$\s?([\d.]+)", html, re.DOTALL)
    if not match:
        return None
    precio_txt = match.group(1).replace(".", "")
    return {
        "tienda": _nombre_tienda_desde_url(url),
        "nombre": None,
        "precio": float(precio_txt),
        "moneda": "CLP",
        "disponible": None,
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metodo": "fallback_regex_sku",
    }


def scrape_sherpalife(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    resultado = _extraer_de_json_ld(soup, url)
    if resultado is not None:
        return resultado

    resultado = _extraer_por_texto_cerca_del_sku(resp.text, url)
    if resultado is not None:
        return resultado

    raise ValueError(
        f"No se pudo extraer el precio de {url} con ninguno de los dos "
        "métodos. Revisar el HTML manualmente."
    )


if __name__ == "__main__":
    resultado = scrape_sherpalife(
        "https://sherpalife.cl/chaqueta-hombre-down-sweater/176894"
    )
    for k, v in resultado.items():
        print(f"{k}: {v}")
