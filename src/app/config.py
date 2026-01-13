from typing import Annotated

from mm_base6 import BaseSettings, BaseState, Config, setting_field

config = Config(openapi_tags=["source", "proxy"], ui_menu={"/bot": "bot", "/sources": "sources", "/proxies": "proxies"})


class Settings(BaseSettings):
    live_last_ok_minutes: Annotated[int, setting_field(15, "live proxies only if they checked less than this minutes ago")]
    proxies_check: Annotated[bool, setting_field(True, "enable periodic proxy check")]
    max_proxies_check: Annotated[int, setting_field(30, "max proxies to check in one iteration")]
    proxy_check_timeout: Annotated[float, setting_field(5.1, "timeout for proxy check")]


class State(BaseState):
    pass
