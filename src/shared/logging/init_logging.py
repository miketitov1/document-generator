import logging
from pathlib import Path
from datetime import datetime


def _configure_framework_loggers() -> None:
    for logger_name in (
        "fastapi",
        "streamlit",
        "streamlit.runtime",
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "watchdog",
        "watchfiles",
    ):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)
        logger.propagate = True


def init_logging(
    logs_dir_path: Path,
    latest_log_path: Path,
    *,
    max_session_logs: int = 10,
    console_logging: bool = True,
) -> None:
    """
    Initializes logging execution.

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

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    _configure_framework_loggers()

    # Paths
    logs_dir_path.mkdir(parents=True, exist_ok=True)
    latest_log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y.%m.%d_%H.%M.%S")
    session_log_path = logs_dir_path / f"{timestamp}_log.txt"

    # Formatters
    console_formatter = logging.Formatter("[%(levelname)s]: %(message)s")

    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s]: %(message)s",
        datefmt="%Y-%m-%d] [%H:%M:%S",
    )

    # Console handler
    if console_logging:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        root.addHandler(console_handler)

    # Latest log handler (always overwritten)
    latest_file_handler = logging.FileHandler(
        latest_log_path,
        mode="w",
        encoding="utf-8",
    )
    latest_file_handler.setLevel(logging.DEBUG)
    latest_file_handler.setFormatter(file_formatter)
    root.addHandler(latest_file_handler)

    # Session log handler (unique per launch)
    session_file_handler = logging.FileHandler(
        session_log_path,
        mode="w",
        encoding="utf-8",
    )
    session_file_handler.setLevel(logging.DEBUG)
    session_file_handler.setFormatter(file_formatter)
    root.addHandler(session_file_handler)

    # Cleanup old session logs
    cleanup_old_logs(logs_dir_path, max_session_logs)

    # Final message
    logging.getLogger(__name__).info("Logging successfully initialized.")
    logging.getLogger(__name__).info("latest_log = %s", latest_log_path)
    logging.getLogger(__name__).info("session_log = %s", session_log_path)


def cleanup_old_logs(logs_dir_path: Path, max_session_logs: int) -> None:
    """
    Deletes the oldest log files if the number of logs exceeds the limit.

    Args:
        logs_dir_path: The directory containing the log files.
        max_session_logs: The maximum number of log files to keep.
    """
    session_logs = sorted(
        logs_dir_path.glob("*_log.txt"),
        key=lambda p: p.stat().st_mtime,
    )

    excess_logs = session_logs[:-max_session_logs]
    for log_file in excess_logs:
        try:
            log_file.unlink()
        except Exception:
            logging.getLogger(__name__).exception(
                "Failed to delete old log file: %s", log_file
            )