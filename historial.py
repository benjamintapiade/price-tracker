"""
Guarda el último precio conocido de cada producto en un archivo JSON
simple (historial_precios.json), para poder comparar y destacar qué
productos subieron o bajaron entre una revisión y la siguiente.

Se eligió JSON en vez de SQLite a propósito: así el archivo se puede
comitear directamente al repo de git en cada corrida de GitHub Actions
(un archivo de texto se ve bien en los diffs de git; una base de datos
binaria no).
"""

import json

RUTA_HISTORIAL = "historial_precios.json"


def cargar_historial() -> dict:
    try:
        with open(RUTA_HISTORIAL, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def guardar_historial(historial: dict) -> None:
    with open(RUTA_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2, sort_keys=True)
