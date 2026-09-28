"""Regression tests for the Docker Compose redis readiness gate (issue #149).

``docker-compose.full.yml`` sets ``QUEUE_ENABLED=1`` so the app container runs
the queue worker. Previously redis had no healthcheck and ``depends_on`` had no
condition, so the worker could start before redis was ready and die silently.
These tests load the compose file with PyYAML (no Docker build required) and
assert:

- the redis service declares a healthcheck that pings redis, and
- the cortex service waits for redis to be healthy (``service_healthy``) while
  the other services only wait for ``service_started``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
FULL_COMPOSE = REPO_ROOT / "docker-compose.full.yml"


def _load() -> dict:
    with FULL_COMPOSE.open() as fh:
        return yaml.safe_load(fh)


def test_redis_service_declares_ping_healthcheck() -> None:
    services = _load()["services"]
    healthcheck = services["redis"].get("healthcheck")

    assert healthcheck is not None, "redis service must declare a healthcheck"
    assert healthcheck["test"] == ["CMD", "redis-cli", "ping"]
    # The healthcheck must be configured to actually run (interval/timeout set).
    assert healthcheck.get("interval")
    assert healthcheck.get("timeout")
    assert healthcheck.get("retries", 0) > 0


def test_cortex_waits_for_healthy_redis() -> None:
    depends_on = _load()["services"]["cortex"]["depends_on"]

    # Long-form mapping: redis must gate on health, not just container start.
    assert depends_on["redis"]["condition"] == "service_healthy"
    # The other services only need to be up, not healthy.
    assert depends_on["postgres"]["condition"] == "service_started"
    assert depends_on["qdrant"]["condition"] == "service_started"


def test_cortex_still_enables_queue() -> None:
    # The fix must not disable the in-container worker: QUEUE_ENABLED stays set.
    environment = _load()["services"]["cortex"]["environment"]
    assert "QUEUE_ENABLED=1" in environment
