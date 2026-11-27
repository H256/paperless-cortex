from __future__ import annotations

import socket
from typing import Any

import pytest

from app.services.runtime.model_providers import validate_provider_base_url


def _resolve_to(monkeypatch: Any, address: str) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_a, **_k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))],
    )


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254"])
def test_hostname_resolving_to_blocked_ip_is_rejected(monkeypatch: Any, address: str) -> None:
    _resolve_to(monkeypatch, address)
    with pytest.raises(ValueError):
        validate_provider_base_url("http://innocent.example.com")


def test_decimal_ip_form_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_provider_base_url("http://2130706433")


def test_lan_hostname_is_allowed(monkeypatch: Any) -> None:
    _resolve_to(monkeypatch, "192.168.1.20")
    assert validate_provider_base_url("http://llm.elysium.lan/") == "http://llm.elysium.lan"


def test_unresolvable_hostname_is_allowed(monkeypatch: Any) -> None:
    def _fail(*_a: Any, **_k: Any) -> Any:
        raise socket.gaierror("nope")

    monkeypatch.setattr(socket, "getaddrinfo", _fail)
    assert validate_provider_base_url("http://llm.elysium.lan") == "http://llm.elysium.lan"
