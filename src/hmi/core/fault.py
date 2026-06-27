"""Centralised fault handling.

This is the heart of the template's robustness story. *Every* unexpected
error in the process — whether it comes from a Qt slot, a worker thread, a
plain Python thread, or the Qt C++ layer itself — is funnelled into a single
:class:`Fault` object and broadcast on the :class:`FaultBus`.

Why this matters for HMI:
    * Since PyQt 5.5, an unhandled exception inside a slot calls
      ``sys.excepthook`` and then **aborts the process**. On a 24/7 HMI panel
      that is unacceptable. We install hooks that log and surface the fault
      instead of letting the process die.
    * Worker threads have their own ``threading.excepthook`` that, by default,
      just prints to stderr where nobody sees it on a kiosk.
    * Qt emits its own warnings/errors through a C++ message handler that
      bypasses Python logging entirely.

The :class:`FaultBus` is a ``QObject`` so its signal can safely marshal a
fault raised on *any* thread back onto the GUI thread (Qt queues the
connection automatically), where a dialog or status bar can react.
"""

from __future__ import annotations

import logging
import sys
import threading
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from types import TracebackType

from PyQt6.QtCore import QObject, pyqtSignal

from hmi.core.exceptions import AppError, Severity

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Fault:
    """An immutable record of something that went wrong."""

    message: str
    severity: Severity = Severity.ERROR
    source: str = "app"
    exception: BaseException | None = None
    recoverable: bool = True
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def traceback_text(self) -> str:
        if self.exception is None:
            return ""
        return "".join(
            traceback.format_exception(
                type(self.exception),
                self.exception,
                self.exception.__traceback__,
            )
        )

    @classmethod
    def from_exception(
        cls, exc: BaseException, *, source: str = "app"
    ) -> "Fault":
        """Build a fault from an exception, honouring :class:`AppError` metadata."""
        if isinstance(exc, AppError):
            return cls(
                message=str(exc),
                severity=exc.severity,
                source=exc.context or source,
                exception=exc,
                recoverable=exc.recoverable,
            )
        return cls(
            message=f"{type(exc).__name__}: {exc}",
            severity=Severity.CRITICAL,
            source=source,
            exception=exc,
            recoverable=False,
        )


class FaultBus(QObject):
    """Process-wide singleton that broadcasts faults on the GUI thread.

    Connect ``faultRaised`` to your status bar, fault dialog, alarm log, etc.
    Because it is a ``QObject`` signal, emissions from worker threads are
    delivered as queued events on the receiver's (GUI) thread automatically.
    """

    faultRaised = pyqtSignal(object)  # emits Fault

    _instance: "FaultBus | None" = None

    @classmethod
    def instance(cls) -> "FaultBus":
        if cls._instance is None:
            cls._instance = FaultBus()
        return cls._instance

    def report(self, fault: Fault) -> None:
        _log_fault(fault)
        # Emitting is thread-safe; Qt marshals to the receiving thread.
        self.faultRaised.emit(fault)


_LEVEL_BY_SEVERITY = {
    Severity.INFO: logging.INFO,
    Severity.WARNING: logging.WARNING,
    Severity.ERROR: logging.ERROR,
    Severity.CRITICAL: logging.CRITICAL,
}


def _log_fault(fault: Fault) -> None:
    level = _LEVEL_BY_SEVERITY.get(fault.severity, logging.ERROR)
    log.log(level, "[%s] %s", fault.source, fault.message)
    if fault.exception is not None and level >= logging.ERROR:
        log.log(level, "%s", fault.traceback_text)


def report_fault(
    exc: BaseException | None = None,
    *,
    message: str | None = None,
    source: str = "app",
    severity: Severity = Severity.ERROR,
) -> Fault:
    """Convenience entry point used throughout the app to report a problem.

    Pass an exception, a plain message, or both. Returns the :class:`Fault`
    so callers can inspect it if needed.
    """
    if exc is not None:
        fault = Fault.from_exception(exc, source=source)
        if message is not None:
            fault = Fault(
                message=f"{message}: {fault.message}",
                severity=fault.severity,
                source=fault.source,
                exception=fault.exception,
                recoverable=fault.recoverable,
            )
    else:
        fault = Fault(
            message=message or "Unknown fault",
            severity=severity,
            source=source,
        )
    FaultBus.instance().report(fault)
    return fault


# --------------------------------------------------------------------------- #
# Global hook installation
# --------------------------------------------------------------------------- #

_original_excepthook = sys.excepthook


def _python_excepthook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: TracebackType | None,
) -> None:
    """Catches exceptions escaping the Qt event loop (i.e. from slots)."""
    if issubclass(exc_type, KeyboardInterrupt):
        _original_excepthook(exc_type, exc_value, exc_tb)
        return
    exc_value.__traceback__ = exc_tb
    FaultBus.instance().report(Fault.from_exception(exc_value, source="event-loop"))


def _threading_excepthook(args: threading.ExceptHookArgs) -> None:
    """Catches exceptions escaping plain (non-Qt) threads."""
    if args.exc_value is None:
        return
    args.exc_value.__traceback__ = args.exc_traceback
    FaultBus.instance().report(
        Fault.from_exception(args.exc_value, source=f"thread:{args.thread.name}")
    )


def install_fault_hooks() -> None:
    """Install all global hooks. Call once, early, before the event loop starts."""
    sys.excepthook = _python_excepthook
    threading.excepthook = _threading_excepthook
    _install_qt_message_handler()


def _install_qt_message_handler() -> None:
    """Route Qt's own C++ log messages into Python logging."""
    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

    qt_log = logging.getLogger("qt")
    level_map = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def handler(msg_type, context, message):  # noqa: ANN001 - Qt signature
        qt_log.log(level_map.get(msg_type, logging.INFO), "%s", message)

    qInstallMessageHandler(handler)
