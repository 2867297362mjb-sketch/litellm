from dataclasses import dataclass, field
from typing import cast

import httpx
import pytest

from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
from litellm.proxy.control_plane.container import HandlerTransport


@dataclass
class _RecyclingHandler:  # mutable-ok: counts how often the pool is re-read
    """Stands in for AsyncHTTPHandler, whose client property hands out a fresh pool after cache eviction."""

    pools: list[httpx.AsyncClient] = field(default_factory=list)

    @property
    def client(self) -> httpx.AsyncClient:
        pool = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"n": len(self.pools)}))
        )
        self.pools.append(pool)
        return pool


@pytest.mark.asyncio
async def test_transport_rereads_the_handlers_pool_on_every_request() -> None:
    handler = _RecyclingHandler()
    transport = HandlerTransport(cast(AsyncHTTPHandler, handler))  # cast-ok: only the client property is used
    first = await transport.request("GET", "https://dp.test/health", timeout=1.0)
    second = await transport.request("GET", "https://dp.test/health", timeout=1.0)
    assert (first.json(), second.json()) == ({"n": 1}, {"n": 2}), "a pool closed by eviction must not be reused"
