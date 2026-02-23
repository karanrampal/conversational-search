"""Unit tests for logger module."""

import logging
from pathlib import Path

from core.logger import Color, CustomFilter, CustomFormatter, setup_logger


class TestCustomFormatter:
    """Unit tests for CustomFormatter."""

    def test_colors_dict(self) -> None:
        """Test that COLORS_DICT maps log levels to correct color codes."""
        assert CustomFormatter.COLORS_DICT[logging.DEBUG] == Color.GREEN.value
        assert CustomFormatter.COLORS_DICT[logging.INFO] == Color.WHITE.value
        assert CustomFormatter.COLORS_DICT[logging.WARNING] == Color.YELLOW.value
        assert CustomFormatter.COLORS_DICT[logging.ERROR] == Color.RED.value
        assert CustomFormatter.COLORS_DICT[logging.CRITICAL] == Color.PURPLE.value

    def test_format_no_colors(self) -> None:
        """Test formatting without colors."""
        formatter = CustomFormatter(use_colors="none", format_str="%(message)s")
        record = logging.LogRecord("name", logging.INFO, "pathname", 1, "test message", None, None)
        assert formatter.format(record) == "test message"

    def test_format_full_colors(self) -> None:
        """Test formatting with full colors."""
        formatter = CustomFormatter(use_colors="full", format_str="%(message)s")
        record = logging.LogRecord("name", logging.INFO, "pathname", 1, "test message", None, None)
        formatted = formatter.format(record)
        assert Color.WHITE.value in formatted
        assert "test message" in formatted
        assert Color.RESET.value in formatted

    def test_format_partial_colors(self) -> None:
        """Test formatting with partial colors."""
        formatter = CustomFormatter(use_colors="partial", format_str="%(levelname)s: %(message)s")
        record = logging.LogRecord("name", logging.INFO, "pathname", 1, "test message", None, None)
        formatted = formatter.format(record)
        assert f"{Color.WHITE.value}INFO{Color.RESET.value}: test message" == formatted


class TestCustomFilter:
    """Unit tests for CustomFilter."""

    def test_filter_no_restrictions(self) -> None:
        """Test filter with no include or exclude lists."""
        custom_filter = CustomFilter()
        record = logging.LogRecord("some.logger", logging.INFO, "pathname", 1, "msg", None, None)
        assert custom_filter.filter(record) is True

    def test_filter_keep_loggers(self) -> None:
        """Test filter with keep_loggers whitelist."""
        custom_filter = CustomFilter(keep_loggers=["allowed"])

        record_allowed = logging.LogRecord(
            "allowed", logging.INFO, "pathname", 1, "msg", None, None
        )
        assert custom_filter.filter(record_allowed) is True

        # Child of allowed logger
        record_child = logging.LogRecord(
            "allowed.child", logging.INFO, "pathname", 1, "msg", None, None
        )
        assert custom_filter.filter(record_child) is True

        record_blocked = logging.LogRecord(
            "blocked", logging.INFO, "pathname", 1, "msg", None, None
        )
        assert custom_filter.filter(record_blocked) is False

    def test_filter_exclude_loggers(self) -> None:
        """Test filter with exclude_loggers blacklist."""
        custom_filter = CustomFilter(exclude_loggers=["blocked"])

        record_blocked = logging.LogRecord(
            "blocked", logging.INFO, "pathname", 1, "msg", None, None
        )
        assert custom_filter.filter(record_blocked) is False

        record_allowed = logging.LogRecord(
            "allowed", logging.INFO, "pathname", 1, "msg", None, None
        )
        assert custom_filter.filter(record_allowed) is True

    def test_filter_mixed(self) -> None:
        """Test filter with both keep_loggers and exclude_loggers."""
        custom_filter = CustomFilter(keep_loggers=["app"], exclude_loggers=["app.noisy"])

        assert (
            custom_filter.filter(logging.LogRecord("app", logging.INFO, "p", 1, "m", None, None))
            is True
        )

        assert (
            custom_filter.filter(
                logging.LogRecord("app.noisy", logging.INFO, "p", 1, "m", None, None)
            )
            is False
        )

        assert (
            custom_filter.filter(logging.LogRecord("other", logging.INFO, "p", 1, "m", None, None))
            is False
        )


class TestSetupLogger:
    """Unit tests for setup_logger function."""

    def test_setup_logger_basic(self) -> None:
        """Test basic logger setup."""
        setup_logger()
        logger = logging.getLogger("test_basic")
        assert logger.getEffectiveLevel() == logging.INFO

    def test_setup_logger_with_file(self, tmp_path: Path) -> None:
        """Test logger setup with file output."""
        log_file = tmp_path / "test.log"
        setup_logger(log_path=str(log_file), log_level=logging.DEBUG)

        logger = logging.getLogger("test_file")
        logger.debug("Debug message")

        assert log_file.exists()
        content = log_file.read_text()
        assert "Debug message" in content
