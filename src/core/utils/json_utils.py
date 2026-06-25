import json
from pathlib import Path
from typing import Any


def load_json(file_path: str | Path) -> dict[str, Any]:
    """
    Loads JSON data from a file.

    Args:
        file_path: Path to the JSON file.

    Returns:
        dict[str, Any]: The loaded JSON data.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not a valid JSON.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"JSON file not found at: {file_path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
        return data
    


def save_json(file_path: str | Path, data: dict[str, Any] | str) -> None:
    """
    Saves data to a JSON file.

    Args:
        file_path: Destination path for the JSON file.
        data: Dictionary to save.

    Raises:
        IOError: If there is an error writing to the file.
    """
    path = Path(file_path)
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
