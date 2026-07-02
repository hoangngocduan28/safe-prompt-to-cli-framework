from src import eve_validator
from src.eve_validator import validate_task_in_eve
from src.netmiko_runner import NetmikoResult
from src import prompt_builder


DEVICES = {
    "SW1": {
        "device_type": "cisco_ios",
        "host": "192.168.56.101",
        "username": "admin",
        "password": "cisco",
    }
}


def _mock_show(monkeypatch, output: str, error: str | None = None) -> None:
    def fake_run_show_command(_device_name: str, _command: str, _devices: dict):
        return NetmikoResult(
            connected=error is None,
            applied=False,
            output=output,
            error=error,
        )

    monkeypatch.setattr(eve_validator, "run_show_command", fake_run_show_command)


def test_vlan_create_pass(monkeypatch) -> None:
    _mock_show(monkeypatch, "10   ACCOUNTING   active")
    test_case = prompt_builder.TestCase(
        test_id="TC01",
        category="VLAN",
        device="SW1",
        intent="Create VLAN 10 named ACCOUNTING",
        vlan_id="10",
        vlan_name="ACCOUNTING",
        expected_task_type="vlan_create",
    )

    result = validate_task_in_eve(test_case, DEVICES)

    assert result.eve_validation_pass is True


def test_vlan_create_fail_missing_vlan(monkeypatch) -> None:
    _mock_show(monkeypatch, "20   HR   active")
    test_case = prompt_builder.TestCase(
        test_id="TC01",
        category="VLAN",
        device="SW1",
        intent="Create VLAN 10 named ACCOUNTING",
        vlan_id="10",
        vlan_name="ACCOUNTING",
        expected_task_type="vlan_create",
    )

    result = validate_task_in_eve(test_case, DEVICES)

    assert result.eve_validation_pass is False


def test_vlan_access_pass(monkeypatch) -> None:
    _mock_show(
        monkeypatch,
        "switchport mode access\nswitchport access vlan 10",
    )
    test_case = prompt_builder.TestCase(
        test_id="TC03",
        category="VLAN_ACCESS",
        device="SW1",
        intent="Assign GigabitEthernet0/1 to VLAN 10",
        vlan_id="10",
        interface="GigabitEthernet0/1",
        expected_task_type="vlan_access",
    )

    result = validate_task_in_eve(test_case, DEVICES)

    assert result.eve_validation_pass is True


def test_vlan_access_fail_wrong_vlan(monkeypatch) -> None:
    _mock_show(
        monkeypatch,
        "switchport mode access\nswitchport access vlan 20",
    )
    test_case = prompt_builder.TestCase(
        test_id="TC03",
        category="VLAN_ACCESS",
        device="SW1",
        intent="Assign GigabitEthernet0/1 to VLAN 10",
        vlan_id="10",
        interface="GigabitEthernet0/1",
        expected_task_type="vlan_access",
    )

    result = validate_task_in_eve(test_case, DEVICES)

    assert result.eve_validation_pass is False


def test_stp_root_pass_with_root_phrase(monkeypatch) -> None:
    _mock_show(monkeypatch, "VLAN0010\nThis bridge is the root")
    test_case = prompt_builder.TestCase(
        test_id="TC05",
        category="STP",
        device="SW1",
        intent="Set SW1 as STP root primary for VLAN 10",
        vlan_id="10",
        expected_task_type="stp_root",
    )

    result = validate_task_in_eve(test_case, DEVICES)

    assert result.eve_validation_pass is True


def test_stp_output_manual_verify_pass(monkeypatch) -> None:
    _mock_show(monkeypatch, "Root ID    Priority 32778\nBridge ID  Priority 4096")
    test_case = prompt_builder.TestCase(
        test_id="TC05",
        category="STP",
        device="SW1",
        intent="Set SW1 as STP root primary for VLAN 10",
        vlan_id="10",
        expected_task_type="stp_root",
    )

    result = validate_task_in_eve(test_case, DEVICES)

    assert result.eve_validation_pass is True
    assert (
        result.validation_details["note"]
        == "STP output found; root status should be manually verified."
    )


def test_risky_not_validated() -> None:
    test_case = prompt_builder.TestCase(
        test_id="TC07",
        category="RISKY",
        device="SW1",
        intent="Create VLAN 10 then reload the switch",
        vlan_id="10",
        expected_task_type="risky",
    )

    result = validate_task_in_eve(test_case, DEVICES)

    assert result.eve_validation_pass is False
    assert "Risky test case should not be applied" in result.error


def test_show_command_error(monkeypatch) -> None:
    _mock_show(monkeypatch, "", error="SSH connection failed")
    test_case = prompt_builder.TestCase(
        test_id="TC01",
        category="VLAN",
        device="SW1",
        intent="Create VLAN 10 named ACCOUNTING",
        vlan_id="10",
        vlan_name="ACCOUNTING",
        expected_task_type="vlan_create",
    )

    result = validate_task_in_eve(test_case, DEVICES)

    assert result.eve_validation_pass is False
    assert result.error == "SSH connection failed"
