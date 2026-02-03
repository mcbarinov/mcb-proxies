import asyncio

from mm_base6 import Core, run

from app import config
from app.core.db import Db
from app.core.services import ServiceRegistry
from app.server.jinja import JinjaConfig


async def main() -> None:
    core = await Core.init(
        config=config.config,
        settings_cls=config.Settings,
        state_cls=config.State,
        db_cls=Db,
        service_registry_cls=ServiceRegistry,
    )

    await run(
        core=core,
        jinja_config_cls=JinjaConfig,
        host="0.0.0.0",  # noqa: S104 # nosec
        port=3000,
        uvicorn_log_level="warning",
    )


if __name__ == "__main__":
    asyncio.run(main())
