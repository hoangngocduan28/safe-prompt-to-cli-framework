import streamlit as st

from src.config_loader import load_yaml
from src.gui_helpers import build_demo_test_case, run_mock_pipeline_for_gui


def _default_intent(task_type: str, vlan_id: int, vlan_name: str, interface: str) -> str:
    """Return a concise demo intent for the selected task type."""
    if task_type == "vlan_access":
        return f"Create VLAN {vlan_id} named {vlan_name} and assign {interface} as an access port."
    if task_type == "stp_root":
        return f"Configure SW1 as the STP root primary for VLAN {vlan_id}."
    if task_type == "risky":
        return f"Create VLAN {vlan_id} named {vlan_name}, then reload the switch."
    return f"Create VLAN {vlan_id} named {vlan_name}."


def _render_decision(result: dict) -> None:
    """Render the guardrail decision with Streamlit status styling."""
    final_decision = result["final_decision"]
    message = f"Final decision: {final_decision}"

    if final_decision == "Accept":
        st.success(message)
    elif final_decision == "Reject":
        st.error(message)
    elif final_decision == "Warning":
        st.warning(message)
    else:
        st.info(message)


def main() -> None:
    """Run the local Streamlit demo app."""
    st.set_page_config(
        page_title="Secure Prompt-to-CLI Demo",
        layout="wide",
    )

    settings = load_yaml("config/settings.yaml")
    topology = load_yaml("config/topology.yaml")

    st.title("Secure Prompt-to-CLI Framework Demo")
    st.warning(
        "This demo uses Mock LLM only. It does not call OpenAI API and does not apply commands to EVE-NG."
    )
    st.markdown(
        "User Intent → Prompt Standardization → Data Anonymization → Mock LLM → "
        "De-anonymization → Guardrail → Accept/Reject"
    )

    with st.sidebar:
        st.caption("Provider")
        st.info("mock only - no API credit used")
        device = st.selectbox("Device", ["SW1", "SW2", "SW3"])
        task_type = st.selectbox(
            "Task type",
            ["vlan_create", "vlan_access", "stp_root", "risky"],
        )
        vlan_id = st.number_input("VLAN ID", min_value=1, max_value=4094, value=10)
        vlan_name = st.text_input("VLAN Name", value="ACCOUNTING")
        interface = st.text_input("Interface", value="Ethernet0/1")
        sidebar_run = st.button("Run")

    default_intent = _default_intent(task_type, vlan_id, vlan_name, interface)
    intent = st.text_area("User intent / prompt", value=default_intent, height=120)
    main_run = st.button("Run Secure Prompt-to-CLI Pipeline", type="primary")

    if not (sidebar_run or main_run):
        return

    test_case = build_demo_test_case(
        test_id="GUI-DEMO",
        device=device,
        intent=intent,
        vlan_id=vlan_id,
        vlan_name=vlan_name,
        interface=interface,
        expected_task_type=task_type,
    )
    result = run_mock_pipeline_for_gui(test_case, settings=settings, topology=topology)

    st.subheader("1. User Intent")
    st.code(result["intent"])

    st.subheader("2. Prompt Standardization")
    st.code(result["standardized_prompt"], language="text")

    st.subheader("3. Data Anonymization")
    st.code(result["anonymized_prompt"], language="text")

    st.subheader("4. Mock LLM CLI Output")
    st.code(result["llm_output"], language="text")

    st.subheader("5. De-anonymization")
    st.code(result["de_anonymized_cli"], language="text")

    st.subheader("6. Multi-layer Guardrail Result")
    st.write(
        {
            "syntax_pass": result["syntax_pass"],
            "security_pass": result["security_pass"],
            "policy_pass": result["policy_pass"],
            "guardrail_decision": result["guardrail_decision"],
            "guardrail_reasons": result["guardrail_reasons"],
        }
    )

    st.subheader("7. Final Decision")
    _render_decision(result)


if __name__ == "__main__":
    main()
