from .proxy import ProxyService
from .source import SourceService


class ServiceRegistry:
    proxy: ProxyService
    source: SourceService
