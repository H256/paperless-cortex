"""Regression test for issue #147 (AUDIT INFRA-003 / DOCX-001).

``docker-compose.full.yml`` used to declare ``LLM_BASE_URL=`` (empty) in the
``cortex`` service's ``environment:`` list. Compose ``environment:`` takes
precedence over ``env_file:`` (``.env``), and ``_env_optional_str`` returns
``None`` for an empty string — so the empty entry silently overrode the
``LLM_BASE_URL`` the user set in ``.env``. Every LLM/embedding/suggestion task
then failed while the API and UI looked healthy.

This test pins the invariant: no compose file may set ``LLM_BASE_URL`` to an
empty value in a service's ``environment:`` list, which would mask the ``.env``
value.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = [
    REPO_ROOT / "docker-compose.full.yml",
    REPO_ROOT / "docker-compose.app.yml",
    REPO_ROOT / "docker-compose.worker.yml",
]


def _iter_env_entries(value: object) -> list[str]:
    """Flatten a compose ``environment:`` value into ``KEY=value`` strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        return [f"{k}={v}" for k, v in value.items()]
    return []


def test_no_compose_file_sets_empty_llm_base_url() -> None:
    offenders: list[str] = []
    for compose_file in COMPOSE_FILES:
        if not compose_file.exists():
            continue
        data = yaml.safe_load(compose_file.read_text())
        services = data.get("services", {}) if isinstance(data, dict) else {}
        for service_name, service in services.items():
            if not isinstance(service, dict):
                continue
            for entry in _iter_env_entries(service.get("environment")):
                if entry.startswith("LLM_BASE_URL=") and len(entry) == len("LLM_BASE_URL="):
                    offenders.append(f"{compose_file.name}:{service_name}")
    assert not offenders, (
        "Compose file(s) set LLM_BASE_URL to an empty value, which overrides the "
        f".env value via compose environment precedence: {offenders}"
    )
