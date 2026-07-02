from pathlib import Path

import pytest

from src.config_loader import load_csv, load_json, load_yaml
from src.utils import get_project_root


PROJECT_ROOT = get_project_root()


def test_load_yaml_devices() -> None:
    devices = load_yaml(PROJECT_ROOT / "config" / "devices.yaml")

    assert set(devices) == {"SW1", "SW2", "SW3"}
    assert devices["SW1"]["device_type"] == "cisco_ios"
    assert devices["SW1"]["host"] == "192.168.56.101"
    assert devices["SW3"]["port"] == 22


def test_load_yaml_settings() -> None:
    settings = load_yaml(PROJECT_ROOT / "config" / "settings.yaml")

    assert settings["mock_llm"] is True
    assert settings["apply_to_eve_default"] is False
    assert settings["allow_warning_apply"] is False
    assert settings["allow_shutdown"] is False
    assert settings["temperature"] == 0


def test_load_json_mapping() -> None:
    mapping = load_json(PROJECT_ROOT / "data" / "anonymization_map.json")

    assert mapping == {}


def test_load_csv_testcases() -> None:
    testcases = load_csv(PROJECT_ROOT / "data" / "testcases.csv")

    assert len(testcases) == 8
    assert list(testcases.columns) == [
        "test_id",
        "category",
        "device",
        "intent",
        "vlan_id",
        "vlan_name",
        "interface",
        "expected_task_type",
        "expected_result",
    ]
    assert testcases.loc[0, "test_id"] == "TC01"
    assert testcases.loc[6, "expected_task_type"] == "risky"
    assert testcases.loc[7, "expected_result"] == "reject"


def test_missing_file_raises_error() -> None:
    missing_file = Path("config") / "missing.yaml"

    with pytest.raises(FileNotFoundError):
        load_yaml(missing_file)
