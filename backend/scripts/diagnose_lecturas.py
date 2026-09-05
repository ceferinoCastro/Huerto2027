"""Run safe, read-only performance diagnostics for the readings collection."""

import asyncio
import json

from app.core.config import get_settings
from app.db.mongodb import MongoDatabase


async def main() -> None:
    database = MongoDatabase(get_settings())
    await database.connect()
    try:
        diagnostics = await asyncio.wait_for(
            database.readings_performance_diagnostics(),
            timeout=20,
        )
        result = {
            "status": "ok",
            "collection": "lecturas",
            **diagnostics,
        }
    except TimeoutError:
        result = {
            "status": "timeout",
            "detail": "El diagnóstico superó 20 segundos",
        }
    except Exception as exc:
        result = {
            "status": "error",
            "error_type": type(exc).__name__,
        }
    finally:
        database.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
