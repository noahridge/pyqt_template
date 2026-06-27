"""Base class for full-screen pages hosted by the navigator.

Pages are the top-level screens an operator switches between (Dashboard,
Alarms, Settings…). Giving them a common base with explicit ``on_show`` /
``on_hide`` lifecycle hooks lets a large app start/stop expensive work (chart
animations, fast polling) only while a page is visible — important on
resource-constrained HMI hardware.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget


class BasePage(QWidget):
    """Common base for navigable pages.

    Subclasses set :attr:`page_title` and override :meth:`build_ui`. The
    navigator calls :meth:`on_show` / :meth:`on_hide` as pages come and go.
    """

    #: Human-readable title shown in the nav bar and header.
    page_title: str = "Page"
    #: Stable key used for programmatic navigation.
    page_key: str = "page"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.build_ui()

    def build_ui(self) -> None:  # pragma: no cover - overridden
        """Construct the page's widgets. Override me."""

    def on_show(self) -> None:
        """Called when this page becomes visible. Override to resume work."""

    def on_hide(self) -> None:
        """Called when this page is hidden. Override to pause work."""
