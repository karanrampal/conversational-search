"""Logging functionality."""

import logging
from enum import Enum
from string import Template
from typing import Literal, NotRequired, TypedDict, Unpack, override


class Color(Enum):
    """Enum for colors in terminal."""

    RED = "\033[0;91m"
    GREEN = "\033[0;92m"
    YELLOW = "\033[0;93m"
    BLUE = "\033[0;94m"
    PURPLE = "\033[0;95m"
    WHITE = "\033[0;97m"
    RESET = "\033[0m"


class CustomFormatter(logging.Formatter):
    """Custom formatter for logging messages with colors.
    Args:
        format_str (str): format string for logging messages
        date_fmt (str): format string for date
        use_colors (Literal["full", "partial", "none"]): color mode
    """

    str_template = Template("$color$logtext$reset")
    COLORS_DICT = {
        logging.DEBUG: Color.GREEN.value,
        logging.INFO: Color.WHITE.value,
        logging.WARNING: Color.YELLOW.value,
        logging.ERROR: Color.RED.value,
        logging.CRITICAL: Color.PURPLE.value,
    }

    def __init__(
        self,
        format_str: str = "%(asctime)s [%(levelname)5s|%(name)5s|L:%(lineno)3d]: %(message)s",
        date_fmt: str = "%Y-%m-%d %H:%M:%S %Z",
        use_colors: Literal["full", "partial", "none"] = "none",
    ) -> None:
        super().__init__(format_str, date_fmt)
        self.format_str = format_str
        self.date_fmt = date_fmt
        self.use_colors = use_colors

    @override
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors based on log level.
        Args:
            record (LogRecord): log record to format
        Returns:
            (str) formatted log message
        """
        if self.use_colors == "none":
            formatter = logging.Formatter(self.format_str, self.date_fmt)
            return formatter.format(record)

        color = CustomFormatter.COLORS_DICT.get(record.levelno, Color.WHITE.value)

        if self.use_colors == "full":
            log_fmt = CustomFormatter.str_template.substitute(
                color=color, logtext=self.format_str, reset=Color.RESET.value
            )
        else:  # partial
            # Create a copy to avoid side effects on other handlers
            record = logging.makeLogRecord(record.__dict__)
            record.levelname = f"{color}{record.levelname}{Color.RESET.value}"
            log_fmt = self.format_str

        formatter = logging.Formatter(log_fmt, self.date_fmt)
        return formatter.format(record)


class CustomFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """Custom filter for logging messages.

    Behavior:
        - If `keep_loggers` is provided, it acts as a strict whitelist. Only loggers
          matching these names (or their children) will be allowed.
        - If `exclude_loggers` is provided, it acts as a blacklist. Loggers matching
          these names will be blocked.
        - If BOTH are provided, a logger must be in the keep list AND NOT in the
          exclude list to be shown. Exclusion takes precedence over inclusion for
          overlapping matches.

    Args:
        keep_loggers (list[str] | None): list of logger names to keep
        exclude_loggers (list[str] | None): list of logger names to exclude
    """

    def __init__(
        self,
        keep_loggers: list[str] | None = None,
        exclude_loggers: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.keep_loggers = keep_loggers or []
        self.exclude_loggers = exclude_loggers or []

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records based on names.
        Args:
            record (LogRecord): log record to filter
        Returns:
            (bool) True if record should be logged, False otherwise
        """
        is_included = not self.keep_loggers or any(
            name in record.name for name in self.keep_loggers
        )
        is_excluded = self.exclude_loggers and any(
            name in record.name for name in self.exclude_loggers
        )

        return is_included and not is_excluded


class LogParameters(TypedDict):
    """Parameters for setting up the logger"""

    format_str: NotRequired[str]
    date_fmt: NotRequired[str]
    use_colors: NotRequired[Literal["full", "partial", "none"]]
    keep_loggers: NotRequired[list[str]]
    exclude_loggers: NotRequired[list[str]]


def setup_logger(
    log_level: int = logging.INFO,
    log_path: str | None = None,
    **kwargs: Unpack[LogParameters],
) -> None:
    """Set the logger to log info in terminal and file at log_path.
    Args:
        log_level (int): logging level
        log_path (Optional[str]): location of log file
    Kwargs:
        format_str (str): custom formatter for log messages
        date_fmt (str): format string for date
        use_colors (Literal["full", "partial", "none"]): color mode
        keep_loggers (list[str]): list of logger names to keep
        exclude_loggers (list[str]): list of logger names to exclude
    """
    format_str = kwargs.get(
        "format_str", "%(asctime)s [%(levelname)5s|%(name)5s|L:%(lineno)3d]: %(message)s"
    )
    date_fmt = kwargs.get("date_fmt", "%Y-%m-%d %H:%M:%S %Z")
    keep_loggers = kwargs.get("keep_loggers")
    exclude_loggers = kwargs.get("exclude_loggers")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        CustomFormatter(format_str, date_fmt, kwargs.get("use_colors", "none"))
    )

    if keep_loggers or exclude_loggers:
        stream_handler.addFilter(CustomFilter(keep_loggers, exclude_loggers))

    all_handlers: list[logging.Handler] = [stream_handler]
    if log_path:
        file_handler = logging.FileHandler(log_path, mode="w")
        file_handler.setFormatter(logging.Formatter(format_str, date_fmt))
        all_handlers.append(file_handler)

    logging.basicConfig(level=log_level, handlers=all_handlers, force=True)
