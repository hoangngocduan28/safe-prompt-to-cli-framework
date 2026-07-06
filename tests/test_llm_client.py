import pytest

from src import llm_client
from src.llm_client import generate_cli, generate_cli_openai
from src.prompt_builder import TestCase as PromptTestCase, build_prompt


def _test_case() -> PromptTestCase:
    return PromptTestCase(
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


def test_generate_cli_mock_still_works() -> None:
    test_case = _test_case()
    prompt = build_prompt(test_case)

    assert generate_cli(prompt, test_case, mode="mock") == "\n".join(
        [
            "conf t",
            "vlan 10",
            "name ACCOUNTING",
            "end",
        ]
    )


def test_generate_cli_unknown_mode_raises() -> None:
    test_case = _test_case()

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        generate_cli("prompt", test_case, mode="bogus")


def test_generate_cli_openai_missing_key_raises(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        generate_cli_openai("prompt")


def test_strip_markdown_fences_from_openai_output(monkeypatch) -> None:
    class FakeResponses:
        def create(self, **_kwargs):
            return type(
                "Response",
                (),
                {"output_text": "```cisco\nconf t\nvlan 10\nend\n```"},
            )()

    class FakeOpenAI:
        def __init__(self, **_kwargs):
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_client, "OpenAI", FakeOpenAI)

    assert generate_cli_openai("prompt") == "conf t\nvlan 10\nend"


def test_generate_cli_openai_uses_mocked_client(monkeypatch) -> None:
    calls = {}

    class FakeResponses:
        def create(self, **kwargs):
            calls["create"] = kwargs
            return type("Response", (), {"output_text": "conf t\nvlan 20\nend"})()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(llm_client, "OpenAI", FakeOpenAI)

    result = generate_cli_openai(
        "Generate VLAN 20",
        {
            "openai_model": "test-model",
            "openai_temperature": 0.2,
            "openai_timeout_seconds": 12,
        },
    )

    assert result == "conf t\nvlan 20\nend"
    assert calls["client"] == {"api_key": "test-key"}
    assert calls["create"]["model"] == "test-model"
    assert calls["create"]["temperature"] == 0.2
    assert calls["create"]["timeout"] == 12
    assert calls["create"]["input"].startswith(
        "You are a Cisco IOS CLI generation engine"
    )
    assert calls["create"]["input"].endswith("Generate VLAN 20")
