from typing import Annotated

from fastapi import APIRouter, Form
from fastapi.params import Query
from fastapi.responses import HTMLResponse
from mm_base6 import cbv, redirect
from mm_proxy import parse_proxy_list
from mm_std import compact_dict
from starlette.responses import RedirectResponse

from app.core.db import Protocol
from app.core.types import AppView

router = APIRouter(include_in_schema=False)


@cbv(router)
class PageRouter(AppView):
    """UI page routes."""

    @router.get("/")
    async def index(self) -> HTMLResponse:
        """Render home page."""
        return await self.render.html("index.j2")

    @router.get("/bot")
    async def bot(self) -> HTMLResponse:
        checks_per_minute = await self.core.services.proxy.counter.get_count()
        return await self.render.html("bot.j2", checks_per_minute=checks_per_minute)

    @router.get("/sources")
    async def sources_page(self) -> HTMLResponse:
        """Render sources list page."""
        stats = await self.core.services.source.calc_stats()
        sources = await self.core.db.source.find({}, "_id")
        return await self.render.html("sources.j2", sources=sources, stats=stats)

    @router.get("/proxies")
    async def proxies_page(
        self,
        source: Annotated[str | None, Query()] = None,
        status: Annotated[str | None, Query()] = None,
        protocol: Annotated[str | None, Query()] = None,
    ) -> HTMLResponse:
        """Render proxies list page."""
        query = compact_dict({"source": source, "status": status, "protocol": protocol})
        proxies = await self.core.db.proxy.find(query, "url")
        sources = [s.id for s in await self.core.db.source.find({}, "_id")]
        return await self.render.html("proxies.j2", proxies=proxies, sources=sources, query=query)


@cbv(router)
class ActionRouter(AppView):
    """Form action handlers."""

    @router.post("/sources")
    async def create_source(self, id: Annotated[str, Form()]) -> RedirectResponse:
        """Create a new source."""
        await self.core.services.source.create(id)
        self.render.flash("Source created")
        return redirect("/sources")

    @router.post("/sources/{id}/entries")
    async def set_entries(self, id: str, entries: Annotated[str, Form()] = "") -> RedirectResponse:
        """Update source entries list."""
        await self.core.services.source.update_entries(id, parse_proxy_list(entries))
        self.render.flash("Entries updated")
        return redirect("/sources")

    @router.post("/sources/{id}/entries_url")
    async def set_entries_url(self, id: str, entries_url: Annotated[str, Form()] = "") -> RedirectResponse:
        """Update source entries URL."""
        await self.core.services.source.update_entries_url(id, entries_url or None)
        self.render.flash("Entries URL updated")
        return redirect("/sources")

    @router.post("/sources/{id}/default")
    async def set_default(
        self,
        id: str,
        protocol: Annotated[str, Form()] = "",
        username: Annotated[str, Form()] = "",
        password: Annotated[str, Form()] = "",
        port: Annotated[str, Form()] = "",
    ) -> RedirectResponse:
        """Update source default connection parameters."""
        await self.core.services.source.update_default(
            id,
            protocol=Protocol(protocol) if protocol else None,
            username=username or None,
            password=password or None,
            port=int(port) if port else None,
        )
        self.render.flash("Default settings updated")
        return redirect("/sources")

    @router.post("/sources/import")
    async def import_sources(self, toml: Annotated[str, Form()]) -> RedirectResponse:
        """Import sources from TOML."""
        count = await self.core.services.source.import_from_toml(toml)
        self.render.flash(f"Imported {count} sources")
        return redirect("/sources")
