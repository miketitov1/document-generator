import logging
import pythoncom
import win32com.client
from win32com.client.dynamic import CDispatch
from pathlib import Path

from src.core.exceptions.application_error import ApplicationError

LOGGER = logging.getLogger(__name__)


class WordPageCounter:
    """
    A utility wrapper class for working with MS Word through COM-interface.
    Lets you open files and count the number of pages in them.
    This is used to determine how many pages each generated document has for detecting overflows.
    """

    word_app: CDispatch | None = None

    def __init__(self):
        LOGGER.info("Initializing Word application for page counting.")
        try:
            # COM initialization is required in each thread that uses COM objects
            pythoncom.CoInitialize()
            self.word_app = win32com.client.Dispatch("Word.Application")
            self.word_app.Visible = False
            self.word_app.DisplayAlerts = False
        except Exception as e:
            raise ApplicationError(
                "Word Error",
                "Failed to initialize Word application for page counting.",
                e,
            ) from e
        LOGGER.info("Word application initialized successfully for page counting.")

    def count_pages(self, file_path: Path) -> int:
        if self.word_app is None:
            raise ApplicationError(
                "Word Error",
                "Word application is not initialized. Cannot count pages.",
            )

        if not file_path.is_file():
            raise ApplicationError(
                "Word Error",
                f"File does not exist for page counting: {file_path}",
            )

        doc = None
        try:
            LOGGER.debug("Opening document for page counting: %s", file_path)
            doc = self.word_app.Documents.Open(str(file_path), ReadOnly=True)
            # 2 corresponds to wdStatisticPages
            num_pages = doc.ComputeStatistics(2)
            LOGGER.debug("Document '%s' has %d page(s).", file_path, num_pages)
        except Exception as e:
            raise ApplicationError(
                "Word Error",
                f"Failed to count pages for document: {file_path}",
                e,
            ) from e
        finally:
            if doc is not None:
                doc.Close(SaveChanges=False)

        return num_pages

    def close(self):
        if self.word_app is not None:
            try:
                LOGGER.info("Closing Word application used for page counting.")
                self.word_app.Quit()
                self.word_app = None
            except Exception as e:
                LOGGER.error("Failed to close Word application: %s", e)
