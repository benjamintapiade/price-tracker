"""
Scraper de precios para doite.cl

Doite corre en Shopify y expone el precio del producto en una meta tag
de tipo Open Graph Product (product:price:amount), en vez de solo mostrarlo
como texto visible. Leer esa meta tag es mucho más robusto que parsear
"$129.990" con regex, porque no depende del formato chileno de miles ni
de que el layout visual no cambie.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def scrape_doite(url: str) -> dict:
    """Scrapea un producto de doite.cl y devuelve sus datos clave.

    Parameters
    ----------
    url : str
        URL del producto en doite.cl (ej. una parka, chaqueta, etc.)

    Returns
    -------
    dict con: tienda, nombre, precio, moneda, disponibilidad, url, timestamp
    """
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    price_tag = soup.find("meta", attrs={"property": "product:price:amount"})
    currency_tag = soup.find("meta", attrs={"property": "product:price:currency"})
    title_tag = soup.find("meta", attrs={"property": "og:title"})
    availability_tag = soup.find("meta", attrs={"property": "product:availability"})

    if price_tag is None or not price_tag.get("content"):
        raise ValueError(
            f"No se encontró el precio en {url}. "
            "Es posible que Doite haya cambiado su HTML — revisar selector."
        )

    precio = float(price_tag["content"])
    moneda = currency_tag["content"] if currency_tag else "CLP"
    nombre = title_tag["content"].replace(" - Doite", "") if title_tag else url
    disponible = availability_tag["content"] if availability_tag else None

    return {
        "tienda": "Doite",
        "nombre": nombre,
        "precio": precio,
        "moneda": moneda,
        "disponibilidad": disponible,
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    resultado = scrape_doite(
        "https://www.doite.cl/products/parka-pluma-volker-hombre-doite"
    )
    for k, v in resultado.items():
        print(f"{k}: {v}")
