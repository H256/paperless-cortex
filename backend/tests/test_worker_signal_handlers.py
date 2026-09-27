from __future__ import annotations

import logging
import os
import signal
import threading

from app.worker import _install_signal_handlers


def test_install_signal_handlers_sets_stop_event_on_sigterm() -> None:
    stop_event = threading.Event()

    installed = _install_signal_handlers(stop_event, logging.getLogger(__name__))

    # Both SIGTERM and SIGINT should be installed in the main thread.
    assert signal.SIGTERM in installed
    assert signal.SIGINT in installed

    # Delivering SIGTERM to this process must set the stop event.
    os.kill(os.getpid(), signal.SIGTERM)
    assert stop_event.is_set()


def test_install_signal_handlers_sets_stop_event_on_sigint() -> None:
    stop_event = threading.Event()

    _install_signal_handlers(stop_event, logging.getLogger(__name__))

    os.kill(os.getpid(), signal.SIGINT)
    assert stop_event.is_set()


def test_install_signal_handlers_degrades_outside_main_thread() -> None:
    # signal.signal raises ValueError outside the main thread; the helper must
    # degrade gracefully (install nothing, raise nothing) rather than crash.
    result: dict[str, object] = {}

    def _run() -> None:
        stop_event = threading.Event()
        result["installed"] = _install_signal_handlers(
            stop_event, logging.getLogger(__name__)
        )
        result["set"] = stop_event.is_set()

    thread = threading.Thread(target=_run)
    thread.start()
    thread.join()

    assert result["installed"] == []
    assert result["set"] is False
