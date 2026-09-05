"""Create the approved indexes for `mediciones_plantas` only."""

import asyncio
import json

from app.core.config import get_settings
from app.db.mongodb import MongoDatabase, PLANT_MEASUREMENTS_COLLECTION


async def main() -> None:
    database = MongoDatabase(get_settings())
    try:
        await database.connect()
        await database.ensure_plant_measurement_indexes()
        indexes = await database._database[
            PLANT_MEASUREMENTS_COLLECTION
        ].list_indexes().to_list(length=20)
        result = {
            "status": "ok",
            "collection": PLANT_MEASUREMENTS_COLLECTION,
            "indexes": [
                {
                    "name": item.get("name"),
                    "key": dict(item.get("key", {})),
                    "unique": bool(item.get("unique", False)),
                }
                for item in indexes
            ],
        }
    except Exception as exc:
        result = {"status": "error", "error_type": type(exc).__name__}
    finally:
        database.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
