from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings


def is_queue_enabled(settings: Settings) -> bool:
    return bool(settings.queue_enabled)
