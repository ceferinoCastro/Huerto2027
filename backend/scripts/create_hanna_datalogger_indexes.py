import asyncio

from app.core.config import get_settings
from app.db.mongodb import MongoDatabase


async def main() -> None:
    database = MongoDatabase(get_settings())
    await database.connect()
    try:
        await database.ensure_hanna_datalogger_indexes()
        await database.ensure_hanna_measurement_indexes()
    finally:
        database.close()


if __name__ == "__main__":
    asyncio.run(main())
