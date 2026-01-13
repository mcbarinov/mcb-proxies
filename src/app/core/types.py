from typing import TYPE_CHECKING

from mm_base6 import Core, View

if TYPE_CHECKING:
    from app.config import Settings, State
    from app.core.db import Db
    from app.core.services import ServiceRegistry

    AppCore = Core[Settings, State, Db, ServiceRegistry]
    AppView = View[Settings, State, Db, ServiceRegistry]
else:
    # Runtime: use string forward references to avoid circular imports
    AppCore = Core["Settings", "State", "Db", "ServiceRegistry"]
    AppView = View["Settings", "State", "Db", "ServiceRegistry"]
