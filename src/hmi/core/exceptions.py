"""Application exception hierarchy.

A small, explicit hierarchy lets the fault-handling layer reason about
*severity* and *recoverability* instead of catching bare ``Exception``
everywhere. Services raise these; the fault layer classifies them.
"""

from __future__ import annotations

from enum import Enum


class Severity(Enum):
    """How bad a fault is, used to decide UI treatment and logging level."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AppError(Exception):
    """Base class for all *expected* application errors.

    ``recoverable`` tells the fault layer whether the app can keep running
    (e.g. a device dropped a connection) or whether this is fatal.
    """

    severity: Severity = Severity.ERROR
    recoverable: bool = True

    def __init__(self, message: str, *, context: str | None = None) -> None:
        super().__init__(message)
        self.context = context


class ConfigError(AppError):
    """Invalid or missing configuration. Not recoverable at runtime."""

    severity = Severity.CRITICAL
    recoverable = False


class ServiceError(AppError):
    """A background service failed while running."""

    severity = Severity.ERROR


class DeviceError(ServiceError):
    """Communication with an external device/PLC failed.

    Recoverable: services are expected to retry/reconnect.
    """

    severity = Severity.WARNING
    recoverable = True


class ValidationError(AppError):
    """User input or incoming data failed validation."""

    severity = Severity.WARNING
