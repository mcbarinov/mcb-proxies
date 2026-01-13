from fastapi import APIRouter
from mm_base6 import cbv
from mm_mongo import MongoDeleteResult
from starlette.responses import PlainTextResponse

from app.core.db import Source
from app.core.types import AppView

router = APIRouter(prefix="/api/sources", tags=["source"])


@cbv(router)
class SourceRouter(AppView):
    """Source API endpoints."""

    @router.get("/export")
    async def export_sources(self) -> PlainTextResponse:
        """Export all sources as TOML."""
        return PlainTextResponse(await self.core.services.source.export_as_toml())

    @router.get("/{id}")
    async def get_source(self, id: str) -> Source:
        """Get source by ID."""
        return await self.core.db.source.get(id)

    @router.delete("/{id}")
    async def delete_source(self, id: str) -> MongoDeleteResult:
        """Delete source and all its proxies."""
        return await self.core.services.source.delete(id)

    @router.post("/{id}/check")
    async def check_source(self, id: str) -> int:
        """Fetch proxies from source and insert them into the database."""
        return await self.core.services.source.check(id)
