"""Create only the approved indexes for read queries on `lecturas`."""

import asyncio
import json
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

from app.core.config import get_settings


INDEX_SPECS = (
    ([('timestamp_utc', DESCENDING)], "timestamp_utc_desc"),
    (
        [('device_sn', ASCENDING), ('timestamp_utc', DESCENDING)],
        "device_sn_timestamp_utc_desc",
    ),
    (
        [
            ('device_sn', ASCENDING),
            ('variable', ASCENDING),
            ('timestamp_utc', DESCENDING),
        ],
        "device_sn_variable_timestamp_utc_desc",
    ),
)


async def list_index_summaries(collection: Any) -> list[dict[str, Any]]:
    raw_indexes = await collection.list_indexes().to_list(length=100)
    return [
        {"name": index.get("name"), "key": dict(index.get("key", {}))}
        for index in raw_indexes
    ]


async def main() -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
    )
    collection = client[settings.mongodb_database]["lecturas"]

    try:
        existing_before = {
            index["name"] for index in await list_index_summaries(collection)
        }
        requested = []
        for keys, name in INDEX_SPECS:
            await collection.create_index(keys, name=name)
            requested.append(
                {
                    "name": name,
                    "status": (
                        "existing" if name in existing_before else "created"
                    ),
                }
            )

        result = {
            "status": "ok",
            "collection": "lecturas",
            "requested": requested,
            "indexes": await list_index_summaries(collection),
        }
    except Exception as exc:
        result = {
            "status": "error",
            "error_type": type(exc).__name__,
        }
    finally:
        client.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
