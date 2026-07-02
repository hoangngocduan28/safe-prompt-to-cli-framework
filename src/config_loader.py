from pathlib import Path
import json

import pandas as pd
import yaml


def _ensure_file(path: str | Path) -> Path:
    """Return a Path object after verifying that the file exists."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not file_path.is_file():
        raise FileNotFoundError(f"Path is not a file: {file_path}")
    return file_path


def load_yaml(path: str | Path) -> dict:
    """Load a YAML file and return its mapping content."""
    file_path = _ensure_file(path)

    try:
        with file_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML file: {file_path}") from exc

    if data is None:
        raise ValueError(f"YAML file is empty: {file_path}")
    if not isinstance(data, dict):
        raise ValueError(f"YAML file must contain a mapping: {file_path}")

    return data


def load_json(path: str | Path) -> dict:
    """Load a JSON file and return its object content."""
    file_path = _ensure_file(path)

    try:
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {file_path}") from exc

    if data is None:
        raise ValueError(f"JSON file is empty: {file_path}")
    if not isinstance(data, dict):
        raise ValueError(f"JSON file must contain an object: {file_path}")

    return data


def load_csv(path: str | Path) -> pd.DataFrame:
    """Load a CSV file and return it as a pandas DataFrame."""
    file_path = _ensure_file(path)
    return pd.read_csv(file_path)
