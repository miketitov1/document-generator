import logging
from pathlib import Path
import shutil
import time

from src.core.exceptions.application_error import ApplicationError

LOGGER = logging.getLogger(__name__)


def get_single_subfolder(folder_path: Path) -> Path | None:
    """
    Checks if there is exactly one subfolder in the given folder and returns its path.
    If there are no subfolders or more than one subfolder, returns None.

    Args:
        folder_path (Path): The path to the folder to check.

    Returns:
        Path | None: The path of the single subfolder if found, otherwise None.
    """
    if not folder_path.is_dir():
        return None

    subfolders = [p for p in folder_path.iterdir() if p.is_dir()]

    if len(subfolders) == 1:
        return subfolders[0]

    return None


def sanitize_path_component(component: str) -> str:
    """
    Sanitizes a single path component by replacing forbidden characters
    and path separators with underscores to prevent unintended subdirectories.

    Args:
        component (str): A single directory or file name component that may
            contain data values with path separators (e.g., "72/6").

    Returns:
        str: The sanitized component with forbidden characters replaced.
    """
    import re

    # Replace both forward and backward slashes with underscores to prevent
    # data values like "72/6" from creating extra subdirectories.
    sanitized = component.replace("/", "_").replace("\\", "_")
    # Replace other forbidden Windows filename characters
    forbidden_chars = r'<>:"|?*'
    for char in forbidden_chars:
        sanitized = sanitized.replace(char, "_")
    # Strip trailing/leading spaces and dots to prevent OS errors
    sanitized = sanitized.strip(". ")
    # Collapse multiple underscores into one for cleaner names
    sanitized = re.sub(r"_+", "_", sanitized)

    return sanitized if sanitized else "_"


def init_dir(directory: Path) -> None:
    """
    Initializes a directory at the specified path.
    If the directory does not exist, it will be created.
    If the directory already exists, its contents will be cleared.

    Args:
        directory (Path): The path of the directory to initialize.
    """
    deleted_file_count = 0
    deleted_folder_count = 0
    if not directory.is_dir():
        LOGGER.warning("Directory does not exist, creating it: %s", directory)
        directory.mkdir(parents=True, exist_ok=True)
    else:
        LOGGER.info("Cleaning directory before generation: %s", directory)
        for element in directory.glob("*"):
            if element.is_file():
                element.unlink()
                LOGGER.debug("Deleted existing file in directory: %s", element)
                deleted_file_count += 1
            elif element.is_dir():
                shutil.rmtree(element)
                LOGGER.debug("Deleted existing subfolder in directory: %s", element)
                deleted_folder_count += 1
    LOGGER.info(
        "Cleaned directory. Deleted %d files and %d folders.",
        deleted_file_count,
        deleted_folder_count,
    )


def cleanup_workspace(
    workspace_path: Path,
    archives_folder: Path,
    max_allowed: int,
):
    """
    Cleans up the temporary workspace directory and enforces the archive
    retention policy by deleting the oldest archives when the limit is exceeded.
    """

    try:
        if workspace_path.exists():
            shutil.rmtree(workspace_path)
            LOGGER.info("Cleaned up temporary workspace: %s", workspace_path)
    except Exception as e:
        LOGGER.error(
            "Failed to clean up temporary workspace '%s': %s", workspace_path, str(e)
        )

    try:
        archive_files = list(archives_folder.glob("*.zip"))

        if len(archive_files) > max_allowed:
            archive_files.sort(key=lambda f: f.stat().st_mtime)
            num_to_delete = len(archive_files) - max_allowed

            # Safety threshold: Do not delete any archive modified in the last 60 seconds
            # to protect active concurrent downloads from getting truncated mid-stream.
            now = time.time()
            grace_period = 120  # seconds

            deleted_count = 0
            for i in range(num_to_delete):
                file_to_delete = archive_files[i]

                # Check mtime against the grace period
                if now - file_to_delete.stat().st_mtime < grace_period:
                    LOGGER.warning(
                        "Retention policy: Skipping deletion of '%s' as it was created recently "
                        "and may still be downloading.",
                        file_to_delete.name,
                    )
                    continue

                try:
                    file_to_delete.unlink()
                    LOGGER.info(
                        "Retention policy: Deleted oldest archive '%s'",
                        file_to_delete.name,
                    )
                    deleted_count += 1
                except Exception as e:
                    LOGGER.error(
                        "Failed to delete old archive '%s': %s",
                        file_to_delete.name,
                        str(e),
                    )

            LOGGER.info(
                "Retention check finished. Deleted %d old archive(s).", deleted_count
            )

    except Exception as e:
        LOGGER.error(
            "Error occurred while executing archive retention policy: %s", str(e)
        )
