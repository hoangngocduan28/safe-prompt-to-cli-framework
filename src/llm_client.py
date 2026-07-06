import os
import re

from openai import OpenAI
from src.prompt_builder import TestCase


OPENAI_SAFETY_INSTRUCTION = """You are a Cisco IOS CLI generation engine for a controlled EVE-NG lab.
Return only Cisco IOS CLI commands.
Do not include explanations.
Do not include Markdown.
Do not include comments.
Do not generate destructive commands such as reload, write erase, erase startup-config, delete flash:, format flash:, debug all.
Only generate VLAN and STP switching configuration."""


def _prompt_value(prompt: str, label: str) -> str | None:
    """Extract a value from the standardized prompt context."""
    pattern = re.compile(rf"^{re.escape(label)}:\s*(.+)$", re.MULTILINE)
    match = pattern.search(prompt)
    if not match:
        return None

    value = match.group(1).strip()
    return None if value == "N/A" else value


def _value_from_prompt_or_testcase(
    prompt: str,
    label: str,
    fallback: str | None,
) -> str | None:
    """Prefer prompt context values, falling back to the TestCase object."""
    return _prompt_value(prompt, label) or fallback


def _risky_command(intent: str) -> str:
    """Return the risky command requested by the test intent."""
    lowered = intent.lower()
    if "reload" in lowered:
        return "reload"
    if "write erase" in lowered:
        return "write erase"
    if "delete flash" in lowered:
        return "delete flash:"
    return "debug all"


def _strip_markdown_fences(text: str) -> str:
    """Remove Markdown code fence wrappers from model output."""
    lines = text.strip().splitlines()
    if not lines:
        return ""

    if lines[0].strip().lower().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]

    return "\n".join(lines).strip()


def _extract_response_text(response: object) -> str:
    """Return text from an OpenAI Responses API object."""
    output_text = getattr(response, "output_text", None)
    if output_text is not None:
        return str(output_text)

    output_parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text is not None:
                output_parts.append(str(text))

    return "\n".join(output_parts)


def generate_cli_openai(prompt: str, settings: dict | None = None) -> str:
    """Generate Cisco IOS CLI with the OpenAI Responses API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is required for OpenAI LLM provider."
        )

    settings = settings or {}
    model = settings.get("openai_model", "gpt-5.5")
    temperature = settings.get("openai_temperature", 0)
    timeout = settings.get("openai_timeout_seconds", 30)
    safe_prompt = f"{OPENAI_SAFETY_INSTRUCTION}\n\n{prompt}"

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=safe_prompt,
        temperature=temperature,
        timeout=timeout,
    )
    return _strip_markdown_fences(_extract_response_text(response))


def generate_cli(
    prompt: str,
    test_case: TestCase,
    mode: str = "mock",
    settings: dict | None = None,
) -> str:
    """Generate Cisco-style CLI using the selected LLM provider."""
    if mode == "openai":
        return generate_cli_openai(prompt, settings)
    if mode != "mock":
        raise ValueError(f"Unsupported LLM provider: {mode}")

    vlan_id = _value_from_prompt_or_testcase(prompt, "VLAN ID", test_case.vlan_id)
    vlan_name = _value_from_prompt_or_testcase(prompt, "VLAN Name", test_case.vlan_name)
    interface = _value_from_prompt_or_testcase(prompt, "Interface", test_case.interface)
    task_type = test_case.expected_task_type

    if task_type == "vlan_create":
        return "\n".join(
            [
                "conf t",
                f"vlan {vlan_id}",
                f"name {vlan_name}",
                "end",
            ]
        )

    if task_type == "vlan_access":
        resolved_vlan_name = vlan_name or f"VLAN_{vlan_id}"
        return "\n".join(
            [
                "conf t",
                f"vlan {vlan_id}",
                f"name {resolved_vlan_name}",
                f"interface {interface}",
                "switchport mode access",
                f"switchport access vlan {vlan_id}",
                "end",
            ]
        )

    if task_type == "stp_root":
        return "\n".join(
            [
                "conf t",
                f"spanning-tree vlan {vlan_id} root primary",
                "end",
            ]
        )

    if task_type == "risky":
        resolved_vlan_name = vlan_name or f"VLAN_{vlan_id}"
        return "\n".join(
            [
                "conf t",
                f"vlan {vlan_id}",
                f"name {resolved_vlan_name}",
                "end",
                _risky_command(test_case.intent),
            ]
        )

    return ""
