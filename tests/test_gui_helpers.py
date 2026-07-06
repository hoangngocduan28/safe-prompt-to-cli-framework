from src.gui_helpers import build_demo_test_case, run_mock_pipeline_for_gui


SETTINGS = {"allow_shutdown": False, "llm_provider": "openai"}
TOPOLOGY = {
    "devices": {
        "SW1": {"interfaces": ["Ethernet0/0", "Ethernet0/1", "Ethernet0/2"]},
        "SW2": {"interfaces": ["Ethernet0/0", "Ethernet0/1", "Ethernet0/2"]},
        "SW3": {"interfaces": ["Ethernet0/0", "Ethernet0/1", "Ethernet0/2"]},
    }
}


def test_build_demo_test_case_vlan_create() -> None:
    test_case = build_demo_test_case(
        test_id="GUI01",
        device="SW1",
        intent="Create VLAN 10 named ACCOUNTING",
        vlan_id="10",
        vlan_name="ACCOUNTING",
        interface="",
        expected_task_type="vlan_create",
    )

    assert test_case.test_id == "GUI01"
    assert test_case.device == "SW1"
    assert test_case.intent == "Create VLAN 10 named ACCOUNTING"
    assert test_case.vlan_id == 10
    assert test_case.vlan_name == "ACCOUNTING"
    assert test_case.interface is None
    assert test_case.expected_task_type == "vlan_create"
    assert test_case.expected_result == "accept"


def test_build_demo_test_case_risky_defaults_to_reject() -> None:
    test_case = build_demo_test_case(
        test_id="GUI02",
        device="SW1",
        intent="Create VLAN 10 then reload",
        vlan_id=10,
        vlan_name="ACCOUNTING",
        interface=None,
        expected_task_type="risky",
    )

    assert test_case.expected_result == "reject"


def test_run_mock_pipeline_vlan_create_accept() -> None:
    test_case = build_demo_test_case(
        test_id="GUI03",
        device="SW1",
        intent="Create VLAN 10 named ACCOUNTING",
        vlan_id=10,
        vlan_name="ACCOUNTING",
        interface=None,
        expected_task_type="vlan_create",
    )

    result = run_mock_pipeline_for_gui(test_case, settings=SETTINGS, topology=TOPOLOGY)

    assert result["final_decision"] == "Accept"
    assert "vlan 10" in result["de_anonymized_cli"]


def test_run_mock_pipeline_risky_reject(monkeypatch) -> None:
    def fail_openai(*_args, **_kwargs):
        raise AssertionError("OpenAI must not be called by GUI helper")

    monkeypatch.setattr("src.llm_client.generate_cli_openai", fail_openai)
    test_case = build_demo_test_case(
        test_id="GUI04",
        device="SW1",
        intent="Create VLAN 10 named ACCOUNTING then reload",
        vlan_id=10,
        vlan_name="ACCOUNTING",
        interface=None,
        expected_task_type="risky",
    )

    result = run_mock_pipeline_for_gui(test_case, settings=SETTINGS, topology=TOPOLOGY)

    assert result["final_decision"] == "Reject"
    assert result.get("eve_applied") is None
    assert result.get("eve_connected") is None


def test_run_mock_pipeline_returns_all_expected_keys() -> None:
    test_case = build_demo_test_case(
        test_id="GUI05",
        device="SW1",
        intent="Create VLAN 10 named ACCOUNTING",
        vlan_id=10,
        vlan_name="ACCOUNTING",
        interface=None,
        expected_task_type="vlan_create",
    )

    result = run_mock_pipeline_for_gui(test_case, settings=SETTINGS, topology=TOPOLOGY)

    assert set(result) == {
        "test_id",
        "device",
        "intent",
        "expected_task_type",
        "standardized_prompt",
        "anonymized_prompt",
        "llm_output",
        "de_anonymized_cli",
        "syntax_pass",
        "security_pass",
        "policy_pass",
        "guardrail_decision",
        "guardrail_reasons",
        "final_decision",
    }
