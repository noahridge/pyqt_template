"""The ``@safe_slot`` decorator.

Connect a normal method to a Qt signal and an exception inside it will, by
default, tear the whole process down (see :mod:`hmi.core.fault`). On an HMI
panel one misbehaving button handler must never take out the alarm display.

``@safe_slot`` wraps a slot so that any exception is caught, reported through
the fault system, and *swallowed* — the event loop keeps spinning. Use it on
every method you connect to a signal.

Usage::

    class Dashboard(QWidget):
        @safe_slot
        def on_refresh_clicked(self):
            ...                       # may raise; app stays alive

        @safe_slot(default=0.0, source="dashboard")
        def compute(self) -> float:
            ...                       # returns 0.0 if it raises

If you also want the C++-side typing/perf of a real Qt slot, combine with
``pyqtSlot`` — apply ``pyqtSlot`` *outermost* so it wraps the guarded callable::

    @pyqtSlot()
    @safe_slot
    def on_clicked(self): ...
"""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

from hmi.core.exceptions import Severity
from hmi.core.fault import report_fault

F = TypeVar("F", bound=Callable[..., Any])


def safe_slot(
    func: F | None = None,
    *,
    default: Any = None,
    source: str | None = None,
    severity: Severity = Severity.ERROR,
    reraise: bool = False,
) -> Any:
    """Guard a slot/callback so exceptions are reported instead of crashing.

    Args:
        default: value returned when the wrapped callable raises.
        source: label attached to the fault (defaults to ``Class.method``).
        severity: severity for non-:class:`AppError` exceptions.
        reraise: if ``True``, re-raise after reporting (use only when an
            outer guard exists). Defaults to swallowing the exception.
    """

    def decorate(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - deliberate catch-all
                label = source or _derive_source(fn, args)
                report_fault(exc, source=label, severity=severity)
                if reraise:
                    raise
                return default

        return wrapper  # type: ignore[return-value]

    # Support both @safe_slot and @safe_slot(...)
    if func is not None and callable(func):
        return decorate(func)
    return decorate


def _derive_source(fn: Callable[..., Any], args: tuple[Any, ...]) -> str:
    """Best-effort 'ClassName.method' label for the fault source."""
    if args and hasattr(args[0], "__class__"):
        return f"{args[0].__class__.__name__}.{fn.__name__}"
    return fn.__qualname__
