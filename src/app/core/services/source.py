import contextlib
import logging
from typing import override

import pydash
from mm_base6 import Service, UserError
from mm_base6.core.utils import toml_dumps, toml_loads
from mm_concurrency import async_mutex
from mm_http import http_request
from mm_mongo import MongoDeleteResult, MongoInsertOneResult
from mm_proxy import parse_proxy_list
from mm_std import utc
from pydantic import BaseModel
from pymongo.errors import BulkWriteError

from app.core.db import Protocol, Proxy, Source, Status
from app.core.types import AppCore


class Stats(BaseModel):
    """Proxy statistics for header and sources page."""

    class Count(BaseModel):
        all: int
        ok: int  # Status.OK
        live: int  # Status.OK and checked within live_last_ok_minutes

    all: Count  # unique IPs (uses distinct)
    sources: dict[str, Count]  # proxy counts per source


logger = logging.getLogger(__name__)


class SourceService(Service[AppCore]):
    """Service for managing proxy sources."""

    @override
    def configure_scheduler(self) -> None:
        """Configure scheduled source checking."""
        self.core.scheduler.add("source_check", 60, self.check_next)

    async def calc_stats(self) -> Stats:
        """Calculate proxy statistics for all sources."""
        live_threshold = utc(minutes=-1 * self.core.settings.live_last_ok_minutes)

        all_uniq_ip = await self.core.db.proxy.collection.distinct("external_ip", {"external_ip": {"$ne": None}})
        ok_uniq_ip = await self.core.db.proxy.collection.distinct(
            "external_ip", {"status": Status.OK, "external_ip": {"$ne": None}}
        )
        live_uniq_ip = await self.core.db.proxy.collection.distinct(
            "external_ip",
            {"status": Status.OK, "external_ip": {"$ne": None}, "last_ok_at": {"$gt": live_threshold}},
        )

        all_ = Stats.Count(all=len(all_uniq_ip), ok=len(ok_uniq_ip), live=len(live_uniq_ip))
        sources: dict[str, Stats.Count] = {}
        for source in await self.core.db.source.find({}, "_id"):
            sources[source.id] = Stats.Count(
                all=await self.core.db.proxy.count({"source": source.id}),
                ok=await self.core.db.proxy.count({"source": source.id, "status": Status.OK}),
                live=await self.core.db.proxy.count(
                    {"source": source.id, "status": Status.OK, "last_ok_at": {"$gt": live_threshold}}
                ),
            )
        return Stats(all=all_, sources=sources)

    async def create(self, id: str) -> MongoInsertOneResult:
        """Create a new source with the given id."""
        return await self.core.db.source.insert_one(Source(id=id))

    async def delete(self, id: str) -> MongoDeleteResult:
        """Delete source and all its associated proxies."""
        await self.core.db.proxy.delete_many({"source": id})
        return await self.core.db.source.delete(id)

    async def update_entries(self, id: str, entries: list[str]) -> None:
        """Update manual proxy entries list."""
        await self.core.db.source.set(id, {"entries": entries})

    async def update_entries_url(self, id: str, entries_url: str | None) -> None:
        """Update URL for fetching proxy list."""
        await self.core.db.source.set(id, {"entries_url": entries_url})

    async def update_default(
        self, id: str, protocol: Protocol | None, username: str | None, password: str | None, port: int | None
    ) -> None:
        """Update default connection parameters for partial entries."""
        await self.core.db.source.set(
            id,
            {
                "default_protocol": protocol,
                "default_username": username,
                "default_password": password,
                "default_port": port,
            },
        )

    async def check(self, id: str) -> int:
        """Fetch proxies from source and insert them into the database."""
        source = await self.core.db.source.get(id)
        urls = [source.build_proxy_url(entry) for entry in source.entries]

        # Collect from entries_url
        if source.entries_url:
            res = await http_request(source.entries_url, timeout=10)
            if res.is_success():
                urls.extend(source.build_proxy_url(entry) for entry in parse_proxy_list(res.body or ""))
            else:
                await self.core.event("source_check_failed", {"source_id": id, "error": res.error_message})

        # Insert new proxies, ignoring duplicates (url is unique index)
        proxies = [Proxy.new(id, url) for url in urls]
        if proxies:
            with contextlib.suppress(BulkWriteError):
                await self.core.db.proxy.insert_many(proxies, ordered=False)

        # Update checked_at
        await self.core.db.source.set(id, {"checked_at": utc()})

        return len(proxies)

    @async_mutex
    async def check_next(self) -> None:
        """Check the next source that needs checking."""
        source = await self.core.db.source.find_one(
            {"$or": [{"checked_at": None}, {"checked_at": {"$lt": utc(hours=-1)}}]},
            "checked_at",
        )
        if source:
            await self.check(source.id)

    async def export_as_toml(self) -> str:
        """Export all sources as TOML, excluding timestamps."""
        sources = [s.model_dump(exclude={"created_at", "checked_at"}) for s in await self.core.db.source.find({})]
        sources = [pydash.rename_keys(s, {"_id": "id"}) for s in sources]
        sources = [pydash.omit_by(s, lambda v: v is None) for s in sources]
        return toml_dumps({"sources": sources})

    async def import_from_toml(self, toml: str) -> int:
        """Import sources from TOML, returns count of imported sources."""
        data = toml_loads(toml)
        try:
            sources = [Source(**source) for source in data.get("sources", [])]
        except Exception as e:
            raise UserError(f"Invalid toml data: {e}") from e

        for source in sources:
            await self.core.db.source.set(source.id, source.model_dump(exclude={"_id"}), upsert=True)

        return len(sources)
