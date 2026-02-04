from __future__ import annotations

from app.config import Settings


def require_queue_enabled(settings: Settings) -> bool:
    return bool(settings.queue_enabled)
