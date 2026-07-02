from pathlib import Path


def get_project_root() -> Path:
    """Return the root directory of the PROMPT-TO-CLI project."""
    return Path(__file__).resolve().parents[1]
