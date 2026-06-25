import traceback
import logging

LOGGER = logging.getLogger(__name__)

class ApplicationError(Exception):
    """
    Custom exception class for application-specific errors, designed to work with GUI error dialogs.

    Attributes:
        title (str): The title for the error dialog (e.g. for QMessageBox.critical).
        message (str): The main user-friendly error message.
        original_exception (Exception | None): The original exception if one exists.
        traceback_info (str): Text representation of the traceback (original or current stack).
    """

    title: str
    message: str
    original_exception: Exception | None
    traceback_info: str

    ACCEPTABLE_ERROR_LEVELS = {logging.WARNING, logging.ERROR, logging.CRITICAL}

    def __init__(
        self, title: str, message: str, original_exception: Exception | None = None
    ):
        super().__init__(message)
        self.title = title
        self.message = message
        self.original_exception = original_exception

        # Capture traceback information
        # If we have an original exception, we want its traceback.
        # If not, we want to know where this ApplicationError was raised.
        if original_exception:
            self.traceback_info = "".join(
                traceback.format_exception(
                    type(original_exception),
                    original_exception,
                    original_exception.__traceback__,
                )
            )
        else:
            # Capture current stack if no original exception is provided
            # [:-1] removes the line corresponding to this __init__ call
            self.traceback_info = "".join(traceback.format_stack()[:-1])

    def __str__(self):
        base_msg = f"[{self.title}] {self.message}"
        if self.original_exception:
            return f"{base_msg} (Caused by: {str(self.original_exception)})"
        return base_msg

    def log(
        self, logger: logging.Logger | None = None, level: int = logging.ERROR
    ) -> None:
        """
        Logs the application error with full details including the traceback.

        Args:
            logger: The logger instance to use. If None, uses a logger for this module.
            level: The logging level to use (default: ERROR).
        """
        if logger is None:
            logger = LOGGER
            logger.warning(
                "No logger provided to ApplicationError.log(), using default logger for the module."
            )

        if level not in self.ACCEPTABLE_ERROR_LEVELS:
            logger.warning(
                "Invalid logging level of %s provided to ApplicationError.log(), defaulting to ERROR.",
                level,
            )
            level = logging.ERROR

        # We include the traceback_info in the log message explicitly because
        # sometimes we might be logging this error later, outside the except block
        log_message = f"{self.title}: {self.message}\nOriginal Error: {self.original_exception}\nTraceback:\n{self.traceback_info}"
        logger.log(level, log_message)
