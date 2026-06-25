from pathlib import Path

from src.shared.logging.init_logging import init_logging as shared_init_logging

_initialized = False


def init_logging(
    logs_dir_path: Path,
    latest_log_path: Path,
    *,
    max_session_logs: int = 10,
    console_logging: bool = True,
) -> None:
    """
    Initializes logging execution for the web frontend.
    Due to streamlit's unique execution model and possible re-runs, this function includes a guard to ensure logging is only initialized once per session.

    Uses a rotating log strategy:
    - Creates a new session log file on each launch.
    - Overwrites 'latest_log.txt' in the project root for quick access.
    - Stores previous session logs in 'logs_dir'.
    - Keeps only the most recent 'max_session_logs' session logs.

    Args:
        logs_dir_path: Directory to store log files.
        latest_log_path: Path for the latest log file (overwritten on every run).
        max_session_logs: Number of session logs to keep.
        console_logging: Whether to output logs to the console.
    """
    global _initialized

    if _initialized:
        return

    shared_init_logging(
        logs_dir_path=logs_dir_path,
        latest_log_path=latest_log_path,
        max_session_logs=max_session_logs,
        console_logging=console_logging,
    )

    _initialized = True
