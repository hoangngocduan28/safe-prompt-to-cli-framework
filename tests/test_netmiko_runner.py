import pytest

from src import netmiko_runner
from src.netmiko_runner import (
    apply_config_if_safe,
    get_device_params,
    run_show_command,
    split_cli_to_config_commands,
)


DEVICES = {
    "SW1": {
        "device_type": "cisco_ios",
        "host": "192.168.56.101",
        "username": "admin",
        "password": "cisco",
        "secret": "cisco",
        "port": 22,
    }
}


class FakeConnection:
    def __init__(self) -> None:
        self.enabled = False
        self.config_commands: list[str] = []
        self.show_command = ""
        self.disconnected = False

    def enable(self) -> None:
        self.enabled = True

    def send_config_set(self, commands: list[str]) -> str:
        self.config_commands = commands
        return "config applied"

    def send_command(self, command: str) -> str:
        self.show_command = command
        return "show output"

    def disconnect(self) -> None:
        self.disconnected = True


def test_get_device_params_success() -> None:
    params = get_device_params("SW1", {"SW1": {"host": "192.168.56.101"}})

    assert params["host"] == "192.168.56.101"
    assert params["device_type"] == "cisco_ios"


def test_get_device_params_missing_device() -> None:
    with pytest.raises(KeyError):
        get_device_params("SW2", DEVICES)


def test_split_cli_to_config_commands_removes_wrappers() -> None:
    cli = """conf t
vlan 10
 name ACCOUNTING
interface GigabitEthernet0/1
 switchport mode access
 switchport access vlan 10
end"""

    commands = split_cli_to_config_commands(cli)

    assert commands == [
        "vlan 10",
        "name ACCOUNTING",
        "interface GigabitEthernet0/1",
        "switchport mode access",
        "switchport access vlan 10",
    ]


def test_reject_decision_does_not_connect(monkeypatch) -> None:
    def fail_connect(**_kwargs):
        raise AssertionError("ConnectHandler should not be called")

    monkeypatch.setattr(netmiko_runner, "ConnectHandler", fail_connect)

    result = apply_config_if_safe("SW1", "reload", "Reject", DEVICES, {})

    assert result.connected is False
    assert result.applied is False
    assert "Reject" in result.error


def test_warning_decision_does_not_connect_when_disabled(monkeypatch) -> None:
    def fail_connect(**_kwargs):
        raise AssertionError("ConnectHandler should not be called")

    monkeypatch.setattr(netmiko_runner, "ConnectHandler", fail_connect)

    result = apply_config_if_safe(
        "SW1",
        "vlan 10",
        "Warning",
        DEVICES,
        {"allow_warning_apply": False},
    )

    assert result.connected is False
    assert result.applied is False
    assert "warning apply is disabled" in result.error


def test_accept_decision_connects_and_applies_config(monkeypatch) -> None:
    fake_connection = FakeConnection()

    def fake_connect(**_kwargs):
        return fake_connection

    monkeypatch.setattr(netmiko_runner, "ConnectHandler", fake_connect)

    result = apply_config_if_safe(
        "SW1",
        "conf t\nvlan 10\n name ACCOUNTING\nend",
        "Accept",
        DEVICES,
        {"allow_warning_apply": False},
    )

    assert result.connected is True
    assert result.applied is True
    assert result.output == "config applied"
    assert fake_connection.enabled is True
    assert fake_connection.config_commands == ["vlan 10", "name ACCOUNTING"]
    assert fake_connection.disconnected is True


def test_run_show_command_connects_and_runs_command(monkeypatch) -> None:
    fake_connection = FakeConnection()

    def fake_connect(**_kwargs):
        return fake_connection

    monkeypatch.setattr(netmiko_runner, "ConnectHandler", fake_connect)

    result = run_show_command("SW1", "show vlan brief", DEVICES)

    assert result.connected is True
    assert result.applied is False
    assert result.output == "show output"
    assert fake_connection.enabled is True
    assert fake_connection.show_command == "show vlan brief"
    assert fake_connection.disconnected is True
