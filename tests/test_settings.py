"""Tests for configuration loading, layering, and validation."""

from __future__ import annotations

import json

import pytest

from hmi.core.exceptions import ConfigError
from hmi.core.settings import AppConfig


def test_defaults():
    config = AppConfig.load(None)
    assert config.theme == "dark"
    assert config.device.poll_interval_ms == 500


def test_json_overrides_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"theme": "light", "device": {"name": "PLC-9", "poll_interval_ms": 250}})
    )
    config = AppConfig.load(path)
    assert config.theme == "light"
    assert config.device.name == "PLC-9"
    assert config.device.poll_interval_ms == 250


def test_env_overrides_json(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"theme": "light"}))
    monkeypatch.setenv("HMI_THEME", "high-contrast")
    monkeypatch.setenv("HMI_DEVICE_POLL_INTERVAL_MS", "100")

    config = AppConfig.load(path)
    assert config.theme == "high-contrast"
    assert config.device.poll_interval_ms == 100


def test_invalid_config_raises(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"device": {"failure_rate": 5.0}}))
    with pytest.raises(ConfigError):
        AppConfig.load(path)
