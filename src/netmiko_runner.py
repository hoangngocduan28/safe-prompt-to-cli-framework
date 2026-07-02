from dataclasses import dataclass

try:
    from netmiko import ConnectHandler
except ImportError:
    ConnectHandler = None


@dataclass
class NetmikoResult:
    connected: bool
    applied: bool
    output: str
    error: str | None = None


WRAPPER_COMMANDS = {
    "conf t",
    "configure terminal",
    "end",
    "exit",
}


def get_device_params(device_name: str, devices: dict) -> dict:
    """Return Netmiko connection parameters for a named device."""
    if device_name not in devices:
        raise KeyError(f"Device not found: {device_name}")

    device_params = dict(devices[device_name])
    device_params.setdefault("device_type", "cisco_ios")
    return device_params


def split_cli_to_config_commands(cli: str) -> list[str]:
    """Split Cisco CLI text into configuration commands without wrappers."""
    commands: list[str] = []

    for line in cli.splitlines():
        command = line.strip()
        if not command:
            continue
        if command.lower() in WRAPPER_COMMANDS:
            continue
        commands.append(command)

    return commands


def _connect(device_params: dict):
    """Create a Netmiko connection or raise a clear dependency error."""
    if ConnectHandler is None:
        raise RuntimeError("Netmiko is not installed.")
    return ConnectHandler(**device_params)


def apply_config_if_safe(
    device_name: str,
    cli: str,
    guardrail_decision: str,
    devices: dict,
    settings: dict,
) -> NetmikoResult:
    """Apply configuration only when the guardrail decision allows it."""
    normalized_decision = guardrail_decision.strip().lower()

    if normalized_decision == "reject":
        return NetmikoResult(
            connected=False,
            applied=False,
            output="",
            error="Guardrail decision is Reject. Configuration was not applied.",
        )

    if normalized_decision == "warning" and not settings.get("allow_warning_apply", False):
        return NetmikoResult(
            connected=False,
            applied=False,
            output="",
            error="Guardrail decision is Warning and warning apply is disabled.",
        )

    if normalized_decision not in {"accept", "warning"}:
        return NetmikoResult(
            connected=False,
            applied=False,
            output="",
            error=f"Guardrail decision is {guardrail_decision}. Configuration was not applied.",
        )

    commands = split_cli_to_config_commands(cli)
    if not commands:
        return NetmikoResult(
            connected=False,
            applied=False,
            output="",
            error="No configuration commands to apply.",
        )

    connection = None
    connected = False

    try:
        device_params = get_device_params(device_name, devices)
        connection = _connect(device_params)
        connected = True

        if device_params.get("secret"):
            connection.enable()

        output = connection.send_config_set(commands)
        return NetmikoResult(
            connected=connected,
            applied=True,
            output=output,
            error=None,
        )
    except Exception as exc:
        return NetmikoResult(
            connected=connected,
            applied=False,
            output="",
            error=str(exc),
        )
    finally:
        if connection is not None:
            connection.disconnect()


def run_show_command(
    device_name: str,
    command: str,
    devices: dict,
) -> NetmikoResult:
    """Run a show command on a device through Netmiko."""
    connection = None
    connected = False

    try:
        device_params = get_device_params(device_name, devices)
        connection = _connect(device_params)
        connected = True

        if device_params.get("secret"):
            connection.enable()

        output = connection.send_command(command)
        return NetmikoResult(
            connected=connected,
            applied=False,
            output=output,
            error=None,
        )
    except Exception as exc:
        return NetmikoResult(
            connected=connected,
            applied=False,
            output="",
            error=str(exc),
        )
    finally:
        if connection is not None:
            connection.disconnect()
