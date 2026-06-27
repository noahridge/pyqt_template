"""Top-level navigable screens."""

from hmi.views.pages.alarms_page import AlarmsPage
from hmi.views.pages.control_page import ControlPage
from hmi.views.pages.dashboard_page import DashboardPage
from hmi.views.pages.settings_page import SettingsPage

__all__ = ["AlarmsPage", "ControlPage", "DashboardPage", "SettingsPage"]
