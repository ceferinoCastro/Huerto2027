#!/usr/bin/env python3
import argparse
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.db.mongodb import MongoDatabase
from app.services.sensor_associations import EDUCATIONAL_POSTER_SEED

# Coordenadas y metadata visual exactas que ocupaba SENSOR_CARD_CATALOG en
# frontend/js/catalogo-carteles.js antes de la Fase 2 del rediseño (el catálogo
# visual dinámico reemplazó ese array estático por GET /api/v1/carteles).
# Se conservan aquí para poder migrar los 11 carteles fijos sin alterar el
# diseño visual existente.
_VISUAL_SEED: dict[str, dict] = {
    "temperatura_aire": {
        "icono": "temperature", "grupo_visual": "air", "compartir_conexion_con": "atmosphere",
        "mostrar_conexion": True, "posicion_x": 39, "posicion_y": 25.3333,
        "destino_x": 49, "destino_y": 16, "destino_zona": "aire sobre el huerto",
        "ruta_punto1_x": 44, "ruta_punto1_y": 15, "ancla": "bottom",
        "etiqueta_corta": "T° del aire",
        "explicacion": "Indica qué tan cálido o frío está el aire alrededor de las plantas.",
    },
    "humedad_aire": {
        "icono": "humidity", "grupo_visual": "air", "compartir_conexion_con": "atmosphere",
        "mostrar_conexion": True, "posicion_x": 25, "posicion_y": 25.3333,
        "destino_x": 49, "destino_y": 16, "destino_zona": "aire sobre el huerto",
        "ruta_punto1_x": 52, "ruta_punto1_y": 12, "ancla": "bottom",
        "etiqueta_corta": "Agua en el aire",
        "explicacion": "Muestra cuánta humedad contiene el aire que rodea el huerto.",
    },
    "humedad_hojas": {
        "icono": "leaf-water", "grupo_visual": "plant", "compartir_conexion_con": None,
        "mostrar_conexion": True, "posicion_x": 66, "posicion_y": 21.3333,
        "destino_x": 60, "destino_y": 36, "destino_zona": "hojas de la planta",
        "ruta_punto1_x": 62, "ruta_punto1_y": 29.3333, "ancla": "left",
        "etiqueta_corta": "Agua en hojas",
        "explicacion": "Indica si las hojas se encuentran secas o tienen agua sobre su superficie.",
    },
    "temperatura_tierra": {
        "icono": "temperature-soil", "grupo_visual": "earth", "compartir_conexion_con": None,
        "mostrar_conexion": True, "posicion_x": 40, "posicion_y": 37.3333,
        "destino_x": 44, "destino_y": 52, "destino_zona": "superficie de la tierra",
        "ruta_punto1_x": 42, "ruta_punto1_y": 45.3333, "ancla": "bottom",
        "etiqueta_corta": "T° de la tierra",
        "explicacion": "Muestra la temperatura de la superficie de la tierra del huerto.",
    },
    "temperatura_bajo_tierra": {
        "icono": "temperature-depth", "grupo_visual": "earth", "compartir_conexion_con": None,
        "mostrar_conexion": True, "posicion_x": 38, "posicion_y": 74.6667,
        "destino_x": 42, "destino_y": 65.3333, "destino_zona": "interior profundo izquierdo del cajón",
        "ruta_punto1_x": 40, "ruta_punto1_y": 69.3333, "ancla": "top",
        "etiqueta_corta": "T° bajo tierra",
        "explicacion": "Muestra la temperatura en la zona profunda de la tierra, cerca de las raíces.",
    },
    "humedad_tierra": {
        "icono": "soil-water", "grupo_visual": "earth", "compartir_conexion_con": None,
        "mostrar_conexion": True, "posicion_x": 64, "posicion_y": 74.6667,
        "destino_x": 63, "destino_y": 64, "destino_zona": "volumen profundo derecho de tierra",
        "ruta_punto1_x": 63.5, "ruta_punto1_y": 69.3333, "ancla": "top",
        "etiqueta_corta": "Agua en tierra",
        "explicacion": "Indica cuánta agua hay disponible en la tierra para las raíces.",
    },
    "ph_agua": {
        "icono": "ph-water", "grupo_visual": "water", "compartir_conexion_con": "pond",
        "mostrar_conexion": False, "posicion_x": 8, "posicion_y": 40,
        "destino_x": 12, "destino_y": 73.3333, "destino_zona": "estanque verde",
        "ancla": "bottom", "etiqueta_corta": "pH del agua",
        "explicacion": "Indica si el agua es más ácida, neutra o alcalina.",
    },
    "sales_agua": {
        "icono": "salts-water", "grupo_visual": "water", "compartir_conexion_con": "pond",
        "mostrar_conexion": False, "posicion_x": 8, "posicion_y": 49.3333,
        "destino_x": 12, "destino_y": 73.3333, "destino_zona": "estanque verde",
        "ancla": "bottom", "etiqueta_corta": "Sales del agua",
        "explicacion": "Muestra la cantidad de sales presentes en el agua del estanque.",
    },
    "temperatura_agua": {
        "icono": "temperature-water", "grupo_visual": "water", "compartir_conexion_con": "pond",
        "mostrar_conexion": True, "posicion_x": 8, "posicion_y": 58.6667,
        "destino_x": 12, "destino_y": 73.3333, "destino_zona": "estanque verde",
        "ruta_punto1_x": 10, "ruta_punto1_y": 66.6667, "ancla": "bottom",
        "etiqueta_corta": "T° del agua",
        "explicacion": "Indica qué tan fría o cálida está el agua almacenada en el estanque.",
    },
    "altura_planta": {
        "icono": "plant-height", "grupo_visual": "plant", "compartir_conexion_con": None,
        "mostrar_conexion": True, "posicion_x": 73, "posicion_y": 36,
        "destino_x": 64.5, "destino_y": 31.3333, "destino_zona": "parte superior de la planta",
        "ruta_punto1_x": 66, "ruta_punto1_y": 33.3333, "ancla": "left",
        "etiqueta_corta": "Alto de planta",
        "explicacion": "Muestra cuánto ha crecido la planta desde la superficie de la tierra.",
        "regla": {
            "id": "plant-height-ruler", "label": "Regla para medir el alto de la planta",
            "x": 64.5, "y1": 52, "y2": 31.3333, "tickSide": "right",
        },
    },
    "largo_raiz": {
        "icono": "root-length", "grupo_visual": "earth", "compartir_conexion_con": None,
        "mostrar_conexion": True, "posicion_x": 51, "posicion_y": 74.6667,
        "destino_x": 53, "destino_y": 69.3333, "destino_zona": "raíz principal visible",
        "ruta_punto1_x": 52, "ruta_punto1_y": 70.6667, "ancla": "top",
        "etiqueta_corta": "Largo de raíz",
        "explicacion": "Muestra cuánto ha crecido la raíz principal bajo la tierra.",
        "regla": {
            "id": "root-length-ruler", "label": "Regla para medir el largo de la raíz",
            "x": 58, "y1": 52, "y2": 72.6667, "tickSide": "right",
        },
    },
}


def print_report(items):
    columns = ("clave_educativa", "nombre_educativo", "categoria", "unidad", "orden", "fuente_sugerida")
    print("\t".join(columns))
    for item in items:
        print("\t".join(str(item.get(column) if item.get(column) is not None else "—") for column in columns))


async def run(apply: bool) -> None:
    database = MongoDatabase(get_settings())
    await database.connect()
    try:
        existentes = {item["_id"]: item for item in await database.list_carteles(force_refresh=True)}
        seed_by_key = {item["clave_educativa"]: item for item in EDUCATIONAL_POSTER_SEED}
        propuestos = [item for item in EDUCATIONAL_POSTER_SEED if item["clave_educativa"] not in existentes]
        variable_desactualizada = [
            clave for clave, item in existentes.items()
            if clave in seed_by_key
            and item.get("variable_tecnica_sugerida") != seed_by_key[clave]["variable_tecnica_sugerida"]
        ]
        actualizables = sorted(set(_VISUAL_SEED) & set(existentes) | set(variable_desactualizada))
        print_report(EDUCATIONAL_POSTER_SEED)
        print(
            f"\nResumen: {len(EDUCATIONAL_POSTER_SEED)} carteles semilla; {len(propuestos)} nuevos; "
            f"{len(existentes)} ya existentes; {len(actualizables)} para actualizar "
            f"(metadata visual y/o variable_tecnica_sugerida)."
        )
        if apply:
            for item in propuestos:
                await database.create_cartel({**item, **_VISUAL_SEED.get(item["clave_educativa"], {})})
            for clave in actualizables:
                documento = {
                    **existentes[clave],
                    "variable_tecnica_sugerida": seed_by_key[clave]["variable_tecnica_sugerida"],
                    **_VISUAL_SEED.get(clave, {}),
                }
                documento.pop("_id", None)
                documento["clave_educativa"] = clave
                await database.update_cartel(clave, documento)
            print(f"Aplicación: {len(propuestos)} carteles creados; {len(actualizables)} actualizados con metadata visual.")
        else:
            print("Modo dry-run: no se escribió ningún documento.")
    finally:
        database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migra los 11 carteles fijos a carteles_educativos.")
    parser.add_argument("--apply", action="store_true", help="Crea/actualiza los carteles de forma idempotente.")
    args = parser.parse_args()
    asyncio.run(run(args.apply))
