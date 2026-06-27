"""Application composition root.

This is the *only* place where the layers are wired together. Everything
else depends inward on :mod:`hmi.core`; nothing else knows the concrete set of
services, pages, or how they connect. To grow the app you edit
:meth:`HmiApplication._build` — register a service here, add a page there —
without touching the components themselves.

Startup order matters and is deliberate:
    1. logging          (so everything after is observable)
    2. fault hooks       (so any failure during the rest is captured)
    3. config            (validated; a bad config aborts cleanly)
    4. models            (the tag store)
    5. services          (background I/O)
    6. UI                (window, pages, indicators)
    7. start services    (only once the UI can receive their signals)
"""

from __future__ import annotations

import logging
from importlib import resources
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from hmi.alarms.manager import AlarmManager
from hmi.core.fault import install_fault_hooks
from hmi.core.logging_config import configure_logging
from hmi.core.settings import AppConfig
from hmi.models.tag import Tag, TagStore
from hmi.services.device_service import DeviceService
from hmi.views.main_window import MainWindow
from hmi.views.pages.alarms_page import AlarmsPage
from hmi.views.pages.control_page import ControlPage
from hmi.views.pages.dashboard_page import DashboardPage
from hmi.views.pages.settings_page import SettingsPage
from hmi.views.viewmodels.pump_control import PumpControlViewModel

log = logging.getLogger(__name__)


class HmiApplication:
    """Owns the ``QApplication`` and the object graph for one running HMI."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.qt_app = QApplication.instance() or QApplication([])
        self.qt_app.setApplicationName(config.app_name)

        # --- models ---------------------------------------------------- #
        self.store = TagStore()
        self._define_tags()

        # --- services -------------------------------------------------- #
        self.device = DeviceService(config.device, self.store)

        # --- alarm engine ---------------------------------------------- #
        self.alarms = AlarmManager(self.store)

        # --- UI -------------------------------------------------------- #
        self.window = MainWindow(config.app_name)
        self._build_ui()
        self._apply_theme()

    # ------------------------------------------------------------- setup #
    def _define_tags(self) -> None:
        """Define the process tags and their alarm limits."""
        self.store.define_many(
            [
                Tag("tank.level", unit="%", high_limit=85.0, low_limit=15.0),
                Tag("reactor.temperature", unit="°C", high_limit=82.0),
            ]
        )

    def _build_ui(self) -> None:
        # Register pages. Adding a screen to the app is a single line here.
        # Dashboard/Alarms bind to the model directly (no logic to test).
        self.window.add_page(DashboardPage(self.store))
        self.window.add_page(AlarmsPage())

        # Opt-in MVVM example: a control screen whose logic lives in a
        # ViewModel. The VM is kept alive on `self`; the page only renders it.
        if self.config.enable_control_demo:
            self.pump_vm = PumpControlViewModel(self.store, self.device)
            self.window.add_page(ControlPage(self.pump_vm))

        self.window.add_page(SettingsPage(self.config))

        # One status indicator per service. It defaults to DISCONNECTED and
        # then tracks the service via the bus's connectionStateChanged signal.
        self.window.add_status_indicator(self.device.name, self.device.name)

    def _apply_theme(self) -> None:
        try:
            qss = (
                resources.files("hmi.resources.styles")
                .joinpath(f"{self.config.theme}.qss")
                .read_text(encoding="utf-8")
            )
            self.qt_app.setStyleSheet(qss)
        except (FileNotFoundError, ModuleNotFoundError, OSError):
            log.warning("Theme '%s' not found; using default style", self.config.theme)

    # --------------------------------------------------------------- run #
    def run(self) -> int:
        """Show the window, start services, and enter the Qt event loop."""
        if self.config.fullscreen:
            self.window.showFullScreen()
        else:
            self.window.show()

        # Start I/O only after the UI exists to receive its signals.
        self.device.start()

        try:
            return self.qt_app.exec()
        finally:
            self.device.stop()


def main(argv: list[str] | None = None) -> int:
    """Console entry point (see ``[project.scripts]`` in pyproject.toml)."""
    config_path = Path("config.json")
    config = AppConfig.load(config_path if config_path.exists() else None)

    configure_logging(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        log_dir=Path(config.log_dir),
    )
    install_fault_hooks()
    log.info("Starting %s", config.app_name)

    app = HmiApplication(config)
    return app.run()
