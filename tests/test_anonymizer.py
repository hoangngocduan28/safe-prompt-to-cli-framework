from src.anonymizer import anonymize_text


def test_anonymize_hostname(tmp_path) -> None:
    mapping_path = tmp_path / "anonymization_map.json"

    output, _ = anonymize_text("Configure CoreSW01", mapping_path)

    assert "DEVICE_" in output
    assert "CoreSW01" not in output


def test_anonymize_ip_and_subnet(tmp_path) -> None:
    mapping_path = tmp_path / "anonymization_map.json"

    output, _ = anonymize_text(
        "Use 192.168.10.1 in subnet 192.168.10.0/24",
        mapping_path,
    )

    assert "IP_001" in output
    assert "SUBNET_001" in output
    assert "192.168.10.1" not in output
    assert "192.168.10.0/24" not in output


def test_anonymize_vlan_name(tmp_path) -> None:
    mapping_path = tmp_path / "anonymization_map.json"

    output, _ = anonymize_text("Create VLAN 10 named ACCOUNTING", mapping_path)

    assert "VLAN_NAME_001" in output
    assert "10" in output


def test_anonymize_interface(tmp_path) -> None:
    mapping_path = tmp_path / "anonymization_map.json"

    output, _ = anonymize_text(
        "Assign GigabitEthernet0/1 to VLAN 10",
        mapping_path,
    )

    assert "INTERFACE_001" in output
    assert "GigabitEthernet0/1" not in output


def test_mapping_is_reused(tmp_path) -> None:
    mapping_path = tmp_path / "anonymization_map.json"
    text = "Configure CoreSW01"

    first_output, first_mapping = anonymize_text(text, mapping_path)
    second_output, second_mapping = anonymize_text(text, mapping_path)

    assert first_output == second_output
    assert first_mapping["DEVICE_A"] == "CoreSW01"
    assert second_mapping["DEVICE_A"] == "CoreSW01"
