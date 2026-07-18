"""
Scraper de precios para cl.patagonia.com

Patagonia Chile corre en Shopify. Todas las tiendas Shopify exponen los
datos de cada producto en un endpoint JSON público, solo agregando ".json"
a la URL del producto:

    https://cl.patagonia.com/products/chaqueta-hombre-down-sweater
    -> https://cl.patagonia.com/products/chaqueta-hombre-down-sweater.json

Esto es mucho más robusto que parsear el HTML/CSS visible, porque no
depende de las clases CSS del theme (que cambian con cualquier rediseño).
"""

import requests
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urlunparse

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _seleccionar_variante(variantes: list[dict], variant_id: str | None, talla: str) -> dict | None:
    """Elige la variante correcta.

    Si la URL traía ?variant=<id> (Shopify lo usa para preseleccionar
    color+talla en la página), esa es la fuente de verdad más precisa —
    identifica exactamente el color que se quería trackear. Si no viene,
    o no calza con ninguna variante, se cae a buscar solo por talla.
    """
    if variant_id is not None:
        for v in variantes:
            if str(v.get("id")) == str(variant_id):
                return v

    for v in variantes:
        opciones = [v.get("option1"), v.get("option2"), v.get("option3")]
        if talla in opciones:
            return v

    return None


def scrape_patagonia(url: str, talla: str = "L") -> dict:
    """Scrapea un producto de cl.patagonia.com.

    Parameters
    ----------
    url : str
        URL del producto. Puede incluir ?variant=<id> para especificar
        un color exacto (Shopify usa esto para preseleccionar variantes).
    talla : str
        Talla a buscar si no viene un ?variant= en la URL, o como
        respaldo si el variant_id no calza con ninguna variante.

    Returns
    -------
    dict con: tienda, nombre, variante, precio, moneda, disponible, url, timestamp
    """
    parsed = urlparse(url)
    variant_id = parse_qs(parsed.query).get("variant", [None])[0]
    # Importante: sacar el query string ANTES de agregar ".json" — Shopify
    # no reconoce "...?variant=123.json", solo "....json" a secas. El
    # variant_id ya lo guardamos arriba para usarlo más abajo.
    base_url = urlunparse(parsed._replace(query="", fragment=""))

    json_url = base_url.rstrip("/") + ".json"
    resp = requests.get(json_url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if "product" not in data:
        raise ValueError(
            f"{json_url} no devolvió un producto Shopify válido. "
            "¿La URL es correcta y sigue siendo un producto Shopify?"
        )

    product = data["product"]
    variantes = product.get("variants", [])
    variante = _seleccionar_variante(variantes, variant_id, talla)

    if variante is None:
        opciones_disponibles = [v.get("title") for v in variantes]
        raise ValueError(
            f"No se encontró el variant_id '{variant_id}' ni la talla "
            f"'{talla}' en {url}. Variantes disponibles: {opciones_disponibles}"
        )

    return {
        "tienda": "Patagonia oficial",
        "nombre": product.get("title"),
        "variante": variante.get("title"),
        "precio": float(variante["price"]),
        "moneda": "CLP",
        "disponible": variante.get("available"),
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    resultado = scrape_patagonia(
        "https://cl.patagonia.com/products/chaqueta-hombre-down-sweater",
        talla="L",
    )
    for k, v in resultado.items():
        print(f"{k}: {v}")
