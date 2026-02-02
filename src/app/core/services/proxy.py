import asyncio
import logging
from typing import override

import pydash
from bson import ObjectId
from mm_base6 import Service
from mm_concurrency import async_mutex
from mm_proxy import check_proxy_ip_via_public_services
from mm_std import utc_now, utc_now_offset

from app.core.db import Protocol, Proxy, Status
from app.core.types import AppCore
from app.core.utils import AsyncSlidingWindowCounter

logger = logging.getLogger(__name__)


class ProxyService(Service[AppCore]):
    """Service for checking proxy connectivity and managing proxy health status."""

    def __init__(self) -> None:
        self.counter = AsyncSlidingWindowCounter(window_seconds=60)  # how many proxy checks per minute

    @override
    def configure_scheduler(self) -> None:
        self.core.scheduler.add("proxy_check", 1, self.core.services.proxy.check_next)

    @async_mutex
    async def check_next(self) -> None:
        """Check batch of proxies: first unchecked, then oldest checked (>5 min ago)."""
        if not self.core.settings.proxies_check:
            return
        limit = self.core.settings.max_proxies_check
        # First: proxies never checked
        proxies = await self.core.db.proxy.find({"checked_at": None}, limit=limit)
        # Then: oldest checked (more than 5 minutes ago)
        if len(proxies) < limit:
            proxies += await self.core.db.proxy.find(
                {"checked_at": {"$lt": utc_now_offset(minutes=-5)}}, "checked_at", limit=limit - len(proxies)
            )

        async with asyncio.TaskGroup() as tg:
            for proxy in proxies:
                tg.create_task(self.check(proxy.id), name=f"check_proxy_{proxy.id}")

    async def check(self, id: ObjectId) -> dict[str, object]:
        """Check proxy connectivity and update status."""
        proxy = await self.core.db.proxy.get(id)

        result = await check_proxy_ip_via_public_services(proxy.url, timeout=self.core.settings.proxy_check_timeout)

        external_ip = result.value if result.is_ok() else None
        success = external_ip is not None

        await self.counter.record_operation()

        status = Status.OK if success else Status.DOWN
        updated: dict[str, object] = {"status": status, "checked_at": utc_now(), "external_ip": external_ip}
        if success:
            updated["last_ok_at"] = utc_now()
        updated["check_history"] = ([success, *proxy.check_history])[:100]

        updated_proxy = await self.core.db.proxy.set_and_get(id, updated)
        if updated_proxy.is_time_to_delete():
            await self.core.db.proxy.delete(id)
            updated["deleted"] = True

        return updated

    async def get_live_proxies(
        self,
        sources: list[str] | None = None,
        protocol: Protocol | None = None,
        unique_ip: bool = False,
        exclude_gateway: bool = False,
    ) -> list[Proxy]:
        """Get proxies that were OK within live_last_ok_minutes."""
        query: dict[str, object] = {
            "status": Status.OK,
            "last_ok_at": {"$gt": utc_now_offset(minutes=-1 * self.core.settings.live_last_ok_minutes)},
        }
        if sources:
            query["source"] = {"$in": sources}
        if protocol:
            query["protocol"] = protocol.value

        proxies = await self.core.db.proxy.find(query, "url")

        if exclude_gateway:
            proxies = [p for p in proxies if p.gateway is False]

        if unique_ip:
            with_ip = [p for p in proxies if p.external_ip]
            without_ip = [p for p in proxies if not p.external_ip]
            unique_with_ip = pydash.uniq_by(with_ip, lambda p: p.external_ip)
            proxies = unique_with_ip + without_ip

        return proxies
