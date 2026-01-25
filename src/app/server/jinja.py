from typing import override

from markupsafe import Markup
from mm_base6 import JinjaConfig

from app.core.db import Protocol, Status
from app.core.types import AppCore


class AppJinjaConfig(JinjaConfig[AppCore]):
    filters = {}
    globals = {"Status": Status, "Protocol": Protocol}

    @override
    async def header_status(self) -> Markup:
        stats = await self.core.services.source.calc_stats()
        return Markup(
            "<span title='all proxies'>{}</span> / <span title='ok proxies'>{}</span> / <span title='live proxies'>{}</span>"
        ).format(stats.all.all, stats.all.ok, stats.all.live)
