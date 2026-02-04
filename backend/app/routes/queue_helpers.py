from __future__ import annotations


def queue_disabled_response(**extra: object) -> dict[str, object]:
    return {"enabled": False, **extra}
