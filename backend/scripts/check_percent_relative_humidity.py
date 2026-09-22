#!/usr/bin/env python3
"""Revisa en qué localidades hay lecturas o asociaciones de humedad relativa del aire.

Busca la variable técnica "Percent Relative Humidity" (y el alias legacy
"Relative Humidity") en la colección `lecturas`, y la clave educativa
`humedad_aire` en `asociaciones_sensores`, para cada localidad soportada.
"""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.db.mongodb import LOCALITY_DEVICE_SN, MongoDatabase

VARIABLES = ["Percent Relative Humidity", "Relative Humidity"]


async def run() -> None:
    database = MongoDatabase(get_settings())
    await database.connect()
    try:
        db = database._database
        if db is None:
            raise RuntimeError("MongoDB no está inicializado")

        print("== Lecturas por localidad (colección `lecturas`) ==")
        for locality, device_sn in LOCALITY_DEVICE_SN.items():
            if device_sn is None:
                print(f"{locality:12s} sin device_sn configurado (sin datalogger asignado)")
                continue
            pipeline = [
                {"$match": {"device_sn": device_sn, "variable": {"$in": VARIABLES}}},
                {"$group": {
                    "_id": {"sensor_sn": "$sensor_sn", "sensor_name": "$sensor_name", "variable": "$variable"},
                    "count": {"$sum": 1},
                    "last_dt": {"$max": "$datetime"},
                }},
            ]
            groups = [
                {**item.pop("_id"), **item}
                async for item in db["lecturas"].aggregate(pipeline)
            ]
            if not groups:
                print(f"{locality:12s} (device_sn={device_sn}) sin lecturas de humedad relativa")
                continue
            for group in groups:
                print(
                    f"{locality:12s} (device_sn={device_sn}) sensor_sn={group.get('sensor_sn')} "
                    f"sensor_name={group.get('sensor_name')} variable={group.get('variable')!r} "
                    f"count={group.get('count')} last_dt={group.get('last_dt')}"
                )

        print("\n== Asociaciones (colección `asociaciones_sensores`, clave_educativa=humedad_aire) ==")
        cursor = db["asociaciones_sensores"].find({"clave_educativa": "humedad_aire"})
        asociaciones = await cursor.to_list(length=1000)
        if not asociaciones:
            print("No hay asociaciones guardadas para humedad_aire en ninguna localidad.")
        for item in asociaciones:
            print(
                f"{item.get('localidad', '?'):12s} colegio_id={item.get('colegio_id')} "
                f"variable_tecnica={item.get('variable_tecnica')!r} sensor_sn={item.get('sensor_sn')} "
                f"estado_asociacion={item.get('estado_asociacion')}"
            )
    finally:
        database.close()


if __name__ == "__main__":
    asyncio.run(run())
