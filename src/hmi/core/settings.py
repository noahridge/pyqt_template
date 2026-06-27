"""Typed application configuration.

A single ``AppConfig`` dataclass is loaded once at startup and passed down
(dependency injection) rather than read from globals scattered around the
code. It merges, in increasing priority: built-in defaults < JSON file <
environment variables. This keeps the same image deployable to many panels
with per-station overrides via env vars.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from hmi.core.exceptions import ConfigError

log = logging.getLogger(__name__)

_ENV_PREFIX = "HMI_"


@dataclass
class DeviceConfig:
    """Connection settings for the (simulated) device service."""

    name: str = "PLC-1"
    poll_interval_ms: int = 500
    # Probability [0,1] that a simulated poll fails — demonstrates fault flow.
    failure_rate: float = 0.02
    reconnect_delay_ms: int = 2000


@dataclass
class AppConfig:
    """Root configuration object."""

    app_name: str = "HMI Template"
    theme: str = "dark"
    log_level: str = "INFO"
    log_dir: str = "logs"
    fullscreen: bool = False
    # Opt-in MVVM example: register the Control page backed by a ViewModel.
    # Set false (or delete views/viewmodels + control_page) if you don't want it.
    enable_control_demo: bool = True
    device: DeviceConfig = field(default_factory=DeviceConfig)

    # ----------------------------------------------------------------- load #
    @classmethod
    def load(cls, path: str | Path | None = None) -> "AppConfig":
        """Load defaults, overlay a JSON file (if present), then env vars."""
        config = cls()
        if path is not None:
            config._merge_json(Path(path))
        config._merge_env()
        config._validate()
        return config

    def _merge_json(self, path: Path) -> None:
        if not path.exists():
            log.info("Config file %s not found; using defaults", path)
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Could not read config {path}", context="config") from exc

        device_data = data.pop("device", None)
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
        if isinstance(device_data, dict):
            for key, value in device_data.items():
                if hasattr(self.device, key):
                    setattr(self.device, key, value)

    def _merge_env(self) -> None:
        """Override scalar fields from ``HMI_*`` environment variables."""
        for f in fields(self):
            if f.name == "device":
                continue
            env_key = f"{_ENV_PREFIX}{f.name.upper()}"
            if env_key in os.environ:
                setattr(self, f.name, _coerce(os.environ[env_key], getattr(self, f.name)))
        for f in fields(self.device):
            env_key = f"{_ENV_PREFIX}DEVICE_{f.name.upper()}"
            if env_key in os.environ:
                setattr(
                    self.device,
                    f.name,
                    _coerce(os.environ[env_key], getattr(self.device, f.name)),
                )

    def _validate(self) -> None:
        if self.device.poll_interval_ms <= 0:
            raise ConfigError("device.poll_interval_ms must be > 0", context="config")
        if not 0.0 <= self.device.failure_rate <= 1.0:
            raise ConfigError("device.failure_rate must be in [0, 1]", context="config")

    def to_dict(self) -> dict:
        return asdict(self)


def _coerce(raw: str, current: object) -> object:
    """Coerce an env-var string to the type of the existing default."""
    if isinstance(current, bool):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    return raw
