"""ViewModel base and a small binding helper.

This package is **optional**. It demonstrates a widget-based MVVM layer for
screens that have real presentation logic (commands, validation, derived
state, permission-based enabling). Simple read-only pages don't need it and
bind to the model directly — see ``views/pages/dashboard_page.py``.

A ViewModel:
    * exposes view state as ``pyqtProperty`` values with ``notify`` signals
      (so views can bind to them), and commands as ``pyqtSlot`` methods;
    * contains the presentation logic, making it unit-testable without
      instantiating any widgets or a ``QApplication`` event loop; and
    * holds **no reference to its view** — communication is one-way, view → VM
      via commands and VM → view via notify signals.

PyQt widgets have no declarative binding, so :func:`bind` provides the tiny
glue that connects a VM's notify signal to a widget setter and seeds the
initial value — keeping views free of update boilerplate.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, pyqtBoundSignal


class ViewModel(QObject):
    """Base class for view models.

    Subclasses add ``pyqtProperty`` (with ``notify=`` signals) for bindable
    state and ``pyqtSlot`` methods for commands. Keep this object ignorant of
    any concrete widget.
    """


def bind(
    notify: pyqtBoundSignal,
    getter: Callable[[], object],
    setter: Callable[..., object],
) -> None:
    """Wire a VM property to a widget setter.

    Applies ``setter(getter())`` immediately and again whenever ``notify``
    fires. This is the one-line replacement for hand-written
    "connect signal → re-read property → call setText" plumbing.

    Example::

        bind(vm.statusChanged, lambda: vm.status_text, label.setText)
        bind(vm.canStartChanged, lambda: vm.can_start, start_button.setEnabled)
    """

    def apply(*_args: object) -> None:
        setter(getter())

    notify.connect(apply)
    apply()
