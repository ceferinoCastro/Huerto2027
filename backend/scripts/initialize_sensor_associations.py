#!/usr/bin/env python3
import argparse
import asyncio
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.db.mongodb import MongoDatabase
from app.services.sensor_associations import applicable_proposals, build_initial_association_proposal


def print_report(items):
    columns = ("localidad", "clave_educativa", "source", "device_sn", "sensor_sn", "variable_tecnica", "unidad", "cantidad_lecturas", "ultima_lectura", "confianza")
    print("\t".join(columns))
    for item in items:
        print("\t".join(str(item.get(column) if item.get(column) is not None else "—") for column in columns))


async def run(apply: bool) -> None:
    database = MongoDatabase(get_settings())
    await database.connect()
    try:
        inventory = await database.sensor_association_inventory()
        proposal = build_initial_association_proposal(inventory)
        print_report(proposal)
        existing = len(inventory["asociaciones"])
        applicable = applicable_proposals(proposal)
        pending = len(proposal) - len(applicable)
        print(f"\nResumen: {len(proposal)} propuestas; {len(applicable)} aplicables; {pending} pendientes; {existing} existentes.")
        if apply:
            result = await database.upsert_initial_sensor_associations(applicable)
            print(f"Aplicación: {result}")
        else:
            print("Modo dry-run: no se escribió ningún documento.")
    finally:
        database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Propone asociaciones educativas desde lecturas reales.")
    parser.add_argument("--apply", action="store_true", help="Aplica asociaciones altas y medias de forma idempotente.")
    args = parser.parse_args()
    asyncio.run(run(args.apply))
