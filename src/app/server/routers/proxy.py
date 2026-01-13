from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, Request
from mm_base6 import cbv
from starlette.responses import JSONResponse, PlainTextResponse, Response

from app.core.db import Protocol, Proxy
from app.core.types import AppView

router = APIRouter(prefix="/api/proxies", tags=["proxy"])


@cbv(router)
class ProxyRouter(AppView):
    """Proxy API endpoints."""

    @router.get("/live")
    async def get_live_proxies(
        self,
        request: Request,
        sources: str | None = None,
        unique_ip: bool = False,
        protocol: Protocol | None = None,
        exclude_gateway: bool = False,
        format_: Annotated[str, Query(alias="format")] = "text",
    ) -> Response:
        """Get live proxies with optional filtering."""
        allowed = {"sources", "unique_ip", "protocol", "exclude_gateway", "format", "access_token"}
        unknown = set(request.query_params.keys()) - allowed
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unknown query parameters: {unknown}")

        proxies = await self.core.services.proxy.get_live_proxies(
            sources.split(",") if sources else None, protocol, unique_ip, exclude_gateway
        )
        proxy_urls = [p.url for p in proxies]

        if format_ == "text":
            return PlainTextResponse(content="\n".join(proxy_urls))

        return JSONResponse({"proxies": proxy_urls})

    @router.get("/{id}")
    async def get_proxy(self, id: ObjectId) -> Proxy:
        """Get proxy by ID."""
        return await self.core.db.proxy.get(id)

    @router.get("/{id}/url", response_class=PlainTextResponse)
    async def get_proxy_url(self, id: ObjectId) -> str:
        """Get proxy URL as plain text."""
        return (await self.core.db.proxy.get(id)).url

    @router.post("/{id}/check")
    async def check_proxy(self, id: ObjectId) -> dict[str, object]:
        """Check proxy connectivity."""
        return await self.core.services.proxy.check(id)
