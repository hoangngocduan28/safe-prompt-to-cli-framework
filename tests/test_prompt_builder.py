from math import nan

from src import prompt_builder


def test_testcase_from_dict_basic() -> None:
    row = {
        "test_id": " TC01 ",
        "category": " VLAN ",
        "device": " SW1 ",
        "intent": " Create VLAN 10 named ACCOUNTING ",
        "vlan_id": 10,
        "vlan_name": " ACCOUNTING ",
        "interface": "",
        "expected_task_type": " vlan_create ",
        "expected_result": " accept ",
    }

    test_case = prompt_builder.testcase_from_dict(row)

    assert test_case == prompt_builder.TestCase(
        test_id="TC01",
        category="VLAN",
        device="SW1",
        intent="Create VLAN 10 named ACCOUNTING",
        vlan_id="10",
        vlan_name="ACCOUNTING",
        interface=None,
        expected_task_type="vlan_create",
        expected_result="accept",
    )


def test_testcase_from_dict_handles_empty_values() -> None:
    row = {
        "test_id": "TC05",
        "category": "STP",
        "device": "SW1",
        "intent": "Set SW1 as STP root primary for VLAN 10",
        "vlan_id": " 10 ",
        "vlan_name": nan,
        "interface": " ",
        "expected_task_type": "stp_root",
        "expected_result": "accept",
    }

    test_case = prompt_builder.testcase_from_dict(row)

    assert test_case.vlan_id == "10"
    assert test_case.vlan_name is None
    assert test_case.interface is None


def test_build_prompt_contains_required_sections() -> None:
    prompt = prompt_builder.build_prompt(
        prompt_builder.TestCase(
            test_id="TC01",
            category="VLAN",
            device="SW1",
            intent="Create VLAN 10 named ACCOUNTING",
            vlan_id="10",
            vlan_name="ACCOUNTING",
            expected_task_type="vlan_create",
        )
    )

    assert "Role:\nYou are a Cisco network configuration assistant." in prompt
    assert "Instruction:\nGenerate Cisco IOS CLI commands for the requested switching task." in prompt
    assert "Context:" in prompt
    assert "Intent:\nCreate VLAN 10 named ACCOUNTING" in prompt
    assert "Output Constraint:" in prompt


def test_build_prompt_contains_context_values() -> None:
    prompt = prompt_builder.build_prompt(
        prompt_builder.TestCase(
            test_id="TC03",
            category="VLAN_ACCESS",
            device="SW1",
            intent="Assign GigabitEthernet0/1 to VLAN 10",
            vlan_id="10",
            vlan_name="ACCOUNTING",
            interface="GigabitEthernet0/1",
            expected_task_type="vlan_access",
        )
    )

    assert "Device: SW1" in prompt
    assert "Category: VLAN_ACCESS" in prompt
    assert "VLAN ID: 10" in prompt
    assert "VLAN Name: ACCOUNTING" in prompt
    assert "Interface: GigabitEthernet0/1" in prompt
    assert "Expected Task Type: vlan_access" in prompt


def test_build_prompt_forbids_dangerous_commands() -> None:
    prompt = prompt_builder.build_prompt(
        prompt_builder.TestCase(
            test_id="TC07",
            category="RISKY",
            device="SW1",
            intent="Create VLAN 10 then reload the switch",
            vlan_id="10",
            vlan_name="ACCOUNTING",
            expected_task_type="risky",
        )
    )

    assert (
        "Do not generate reload, erase, delete, format, debug, or other destructive commands."
        in prompt
    )
