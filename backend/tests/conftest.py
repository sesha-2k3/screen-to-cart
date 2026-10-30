"""Test isolation for the backend suite.

- Settings never read the repo-root ``.env`` (disabled at import time, before any
  test module imports ``app.main``).
- Every Settings variable is cleared from the environment around each test.
- Outbound network connections fail the test; loopback and AF_UNIX are allowed so
  TestClient and asyncio internals keep working.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from app.config import Settings, get_settings

# Must run before anything imports app.main (its module-level create_app() calls
# get_settings()). conftest.py is imported before test modules are collected.
Settings.model_config["env_file"] = None

SETTINGS_ENV_VARS: tuple[str, ...] = tuple(
    name.upper() for name in Settings.model_fields
)

_LOOPBACK_HOSTNAMES = frozenset({"localhost", "localhost.localdomain", ""})


class OutboundNetworkBlockedError(RuntimeError):
    """Raised when a test tries to open a non-loopback network connection."""


def _is_allowed_address(sock: socket.socket, address: Any) -> bool:
    if getattr(socket, "AF_UNIX", None) is not None and sock.family == socket.AF_UNIX:
        return True
    if isinstance(address, (str, bytes)):
        # Non-tuple addresses only occur for AF_UNIX-style sockets.
        return True
    if not isinstance(address, tuple) or not address:
        return False
    host = address[0]
    if isinstance(host, bytes):
        host = host.decode(errors="replace")
    if not isinstance(host, str):
        return False
    host = host.split("%", 1)[0]  # strip IPv6 zone id
    if host.lower() in _LOOPBACK_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False  # any other hostname counts as outbound


@pytest.fixture(autouse=True)
def _block_outbound_network(monkeypatch: pytest.MonkeyPatch) -> None:
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guarded_connect(self: socket.socket, address: Any) -> None:
        if not _is_allowed_address(self, address):
            raise OutboundNetworkBlockedError(
                f"Outbound network access is blocked in tests: {address!r}"
            )
        real_connect(self, address)

    def guarded_connect_ex(self: socket.socket, address: Any) -> int:
        if not _is_allowed_address(self, address):
            raise OutboundNetworkBlockedError(
                f"Outbound network access is blocked in tests: {address!r}"
            )
        return real_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)


@pytest.fixture(autouse=True)
def _clean_settings_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    """Build Settings from test-provided values only; never opens ``.env``."""

    def _make(**values: Any) -> Settings:
        return Settings(_env_file=None, **values)  # type: ignore[call-arg]

    return _make
