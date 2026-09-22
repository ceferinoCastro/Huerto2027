#!/usr/bin/env python3
"""Asigna los umbrales agronómicos por defecto de lechuga a las campañas activas.

Recorre `campania` (colección) buscando documentos con estado == "activa" y les
fija `rangos_variables` con LETTUCE_RANGES, dejando un registro de auditoría en
`historial_cambios`. Campañas finalizadas, canceladas o planificadas no se tocan.
"""
import argparse
import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.db.mongodb import CAMPAIGNS_COLLECTION, MongoDatabase

LETTUCE_RANGES = {
    "temperatura_aire": {"min": 10, "max": 24},
    "humedad_aire": {"min": 50, "max": 80},
    "humedad_hojas": {"min": 0, "max": 20},
    "temperatura_tierra": {"min": 10, "max": 22},
    "temperatura_bajo_tierra": {"min": 10, "max": 20},
    "humedad_tierra": {"min": 60, "max": 85},
    "ph_agua": {"min": 6.0, "max": 7.0},
    "sales_agua": {"min": 0.8, "max": 1.6},
    "temperatura_agua": {"min": 10, "max": 20},
    "altura_planta": {"min": 0, "max": 30},
    "largo_raiz": {"min": 0, "max": 25},
}


def print_report(campaigns: list[dict]) -> None:
    columns = ("_id", "colegio", "cultivo", "nombre", "revision")
    print("\t".join(columns))
    for item in campaigns:
        cultivo = item.get("cultivo") or item.get("especie") or "—"
        row = {**item, "cultivo": cultivo}
        print("\t".join(str(row.get(column, "—")) for column in columns))


async def run(apply: bool) -> None:
    database = MongoDatabase(get_settings())
    await database.connect()
    try:
        collection = database._database[CAMPAIGNS_COLLECTION]
        campaigns = await collection.find({"estado": "activa"}).to_list(length=1000)
        print_report(campaigns)
        print(f"\nResumen: {len(campaigns)} campañas activas encontradas.")
        if not campaigns:
            print("Nada que hacer.")
            return

        # Idempotencia: una campaña que ya tiene exactamente estos umbrales se
        # omite, para que re-ejecutar el script no acumule revisiones ni
        # entradas de auditoría duplicadas.
        pendientes = [c for c in campaigns if c.get("rangos_variables") != LETTUCE_RANGES]
        al_dia = len(campaigns) - len(pendientes)
        print(f"{len(pendientes)} campañas a actualizar; {al_dia} ya tienen los umbrales de lechuga.")

        if not apply:
            for campaign in pendientes:
                print(f"  [dry-run] se actualizaría: {campaign['_id']} ({campaign.get('colegio', '—')})")
            print("\nModo dry-run: no se escribió ningún documento. Use --apply para persistir los cambios.")
            return

        now = datetime.now(timezone.utc)
        actualizadas = 0
        for campaign in pendientes:
            revision = int(campaign.get("revision") or 0)
            audit_entry = {
                "accion": "umbrales_lechuga_por_defecto",
                "fecha": now,
                "revision": revision + 1,
                "cambios": {
                    "rangos_variables": {
                        "anterior": campaign.get("rangos_variables") or {},
                        "nuevo": LETTUCE_RANGES,
                    }
                },
            }
            result = await collection.update_one(
                {"_id": campaign["_id"]},
                {
                    "$set": {
                        "rangos_variables": LETTUCE_RANGES,
                        "revision": revision + 1,
                        "updated_at": now,
                    },
                    "$push": {"historial_cambios": audit_entry},
                },
            )
            if result.modified_count:
                actualizadas += 1
        print(f"Aplicación: {actualizadas} campañas activas actualizadas con los umbrales de lechuga.")
    finally:
        database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Asigna los umbrales agronómicos por defecto de lechuga a todas las campañas activas."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persiste los cambios en MongoDB. Sin esta bandera el script solo hace un dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fuerza el modo dry-run explícitamente (comportamiento por defecto).",
    )
    args = parser.parse_args()
    asyncio.run(run(apply=args.apply and not args.dry_run))
