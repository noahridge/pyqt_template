"""Settings page: read-only view of effective configuration.

Kept intentionally simple — it demonstrates injecting :class:`AppConfig` into
a page and includes a "Trigger test fault" button so you can watch the fault
pipeline end-to-end at runtime.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from hmi.core.exceptions import DeviceError
from hmi.core.safe_slot import safe_slot
from hmi.core.settings import AppConfig
from hmi.views.base_page import BasePage


class SettingsPage(BasePage):
    page_title = "Settings"
    page_key = "settings"

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        super().__init__()

    def build_ui(self) -> None:
        root = QVBoxLayout(self)
        header = QLabel(self.page_title)
        header.setObjectName("pageHeader")
        root.addWidget(header)

        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText(_format_config(self._config))
        root.addWidget(view)

        # Demonstrates that a raising slot is caught, not fatal.
        test_btn = QPushButton("Trigger test fault")
        test_btn.clicked.connect(self._raise_test_fault)
        root.addWidget(test_btn)
        root.addStretch(1)

    @safe_slot(source="SettingsPage")
    def _raise_test_fault(self) -> None:
        raise DeviceError("Operator triggered a test fault", context="settings")


def _format_config(config: AppConfig) -> str:
    import json

    return json.dumps(config.to_dict(), indent=2)
