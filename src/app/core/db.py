from datetime import datetime
from enum import StrEnum, unique
from urllib.parse import urlparse

from bson import ObjectId
from mm_base6 import BaseDb
from mm_mongo import AsyncMongoCollection, MongoModel
from mm_std import utc
from pydantic import Field, field_validator


@unique
class Protocol(StrEnum):
    """Proxy protocol type."""

    HTTP = "http"
    SOCKS5 = "socks5"


class Source(MongoModel[str]):
    """
    A group of proxies from a single provider or source.

    Proxies can be specified in two ways (both can be used together):
    - entries_url: URL to fetch proxy list from (e.g., https://provider.com/proxies.txt)
    - entries: manual list of proxy entries

    Entries can be in different formats:
    - Full URL: socks5://user:pass@host:port
    - Host with port: 192.168.1.1:8080
    - Host only: 192.168.1.1 (requires default_port)

    When entries are partial (not full URLs), default_* fields are used to build complete URLs.
    """

    __collection__ = "source"
    __indexes__ = ["created_at", "checked_at"]

    default_protocol: Protocol | None = Field(default=None, description="Default protocol for partial entries")
    default_username: str | None = Field(default=None, description="Default username for authentication")
    default_password: str | None = Field(default=None, description="Default password for authentication")
    default_port: int | None = Field(default=None, description="Default port for entries without port")

    entries_url: str | None = Field(default=None, description="URL to fetch proxy list from")
    entries: list[str] = Field(default_factory=list, description="Manual list of proxy entries")

    created_at: datetime = Field(default_factory=utc, description="When this source was created")
    checked_at: datetime | None = Field(default=None, description="Last time entries_url was fetched")

    @field_validator("entries_url", mode="after")
    def entries_url_validator(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    def build_proxy_url(self, entry: str) -> str:
        """
        Build full proxy URL from an entry using default values if needed.

        Args:
            entry: Proxy entry in one of the formats:
                - Full URL: socks5://user:pass@host:port (returned as-is)
                - Host with port: 192.168.1.1:8080
                - Host only: 192.168.1.1 (requires default_port)

        Returns:
            Full proxy URL like socks5://user:pass@host:port

        Raises:
            ValueError: If entry has no port and default_port is not set.
        """
        if entry.startswith(("http://", "https://", "socks5://")):
            return entry

        protocol = self.default_protocol or Protocol.HTTP
        schema = "socks5" if protocol == Protocol.SOCKS5 else "http"

        port: int | None
        if ":" in entry:
            host, port_str = entry.rsplit(":", 1)
            port = int(port_str)
        else:
            host = entry
            port = self.default_port
            if port is None:
                raise ValueError(f"No port specified for entry '{entry}' and no default_port set")

        if self.default_username and self.default_password:
            return f"{schema}://{self.default_username}:{self.default_password}@{host}:{port}"
        return f"{schema}://{host}:{port}"


@unique
class Status(StrEnum):
    """Proxy health status based on connectivity checks."""

    UNKNOWN = "UNKNOWN"  # Never checked or status expired
    OK = "OK"  # Last check was successful
    DOWN = "DOWN"  # Last check failed


class Proxy(MongoModel[ObjectId]):
    """
    A proxy endpoint with connection details and health status.

    Proxies are periodically checked for connectivity. The check_history field
    keeps track of recent check results for reliability scoring.
    """

    __collection__ = "proxy"
    __indexes__ = ["!url", "external_ip", "source", "protocol", "status", "created_at", "checked_at", "last_ok_at"]

    source: str = Field(description="Source ID that provided this proxy")
    url: str = Field(description="Full proxy URL (e.g., socks5://user:pass@host:port)")
    external_ip: str | None = Field(default=None, description="IP visible to external world when using this proxy")
    status: Status = Field(default=Status.UNKNOWN, description="Current health status")
    protocol: Protocol = Field(description="Proxy protocol (HTTP or SOCKS5)")
    created_at: datetime = Field(default_factory=utc, description="When this proxy was added")
    checked_at: datetime | None = Field(default=None, description="Last connectivity check time")
    last_ok_at: datetime | None = Field(default=None, description="Last successful check time")
    check_history: list[bool] = Field(
        default_factory=list, description="Recent check results (True=OK, False=DOWN), max 100 entries"
    )

    @property
    def history_ok_count(self) -> int:
        """Number of successful checks in check_history."""
        return len([x for x in self.check_history if x is True])

    @property
    def history_down_count(self) -> int:
        """Number of failed checks in check_history."""
        return len([x for x in self.check_history if x is False])

    @property
    def endpoint(self) -> str:
        """Proxy endpoint in host:port format, extracted from url."""
        parsed = urlparse(self.url)
        return f"{parsed.hostname}:{parsed.port}"

    @property
    def gateway(self) -> bool | None:
        """
        Whether this proxy is a gateway (external_ip differs from hostname).

        Returns:
            True: Gateway proxy (external_ip != hostname in url)
            False: Direct proxy (external_ip == hostname in url)
            None: Unknown (external_ip not yet detected)
        """
        if self.external_ip is None:
            return None
        return self.external_ip != urlparse(self.url).hostname

    def is_time_to_delete(self) -> bool:
        """
        Check if this proxy should be deleted due to prolonged failure.

        Returns True if:
        - Proxy was working before but hasn't been OK for 1 hour
        - Proxy was never OK and exists for more than 1 hour
        """
        if self.last_ok_at and self.last_ok_at < utc(hours=-1):
            return True
        return bool(self.last_ok_at is None and self.created_at < utc(hours=-1))

    @classmethod
    def new(cls, source: str, url: str) -> Proxy:
        """
        Create a new Proxy instance from a source ID and full proxy URL.

        Args:
            source: Source ID that provides this proxy
            url: Full proxy URL (e.g., socks5://user:pass@host:port)

        Returns:
            New Proxy instance with auto-generated ObjectId

        Raises:
            ValueError: If URL has no hostname
        """
        if not urlparse(url).hostname:
            raise ValueError(f"Invalid proxy URL (no hostname): {url}")
        protocol = Protocol.HTTP if url.startswith("http") else Protocol.SOCKS5
        return Proxy(id=ObjectId(), source=source, url=url, protocol=protocol)


class Db(BaseDb):
    """MongoDB collections for the proxy checker application."""

    source: AsyncMongoCollection[str, Source]
    proxy: AsyncMongoCollection[ObjectId, Proxy]
