"""Logging configuration and management service."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from constants import (
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
    DEFAULT_LOG_LEVEL,
    APP_NAME,
)
from services.appdata_service import AppDataService


class LoggingService:
    """Configures and manages application logging.

    Sets up rotating file handlers and console output.
    """

    def __init__(self):
        self._configured = False
        self._log_file_path: Optional[Path] = None

    def configure_logging(
        self,
        appdata_service: AppDataService,
        log_level: str = DEFAULT_LOG_LEVEL,
        console_output: bool = True
    ) -> None:
        """Configure the logging system.

        Args:
            appdata_service: Service to get log file paths
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console_output: Whether to output logs to console
        """
        if self._configured:
            return

        # Get log file path
        self._log_file_path = appdata_service.get_log_file_path()

        # Create root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level.upper()))

        # Clear any existing handlers
        root_logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Add rotating file handler
        try:
            file_handler = RotatingFileHandler(
                filename=self._log_file_path,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)  # Always log everything to file
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not create log file handler: {e}", file=sys.stderr)

        # Add console handler if requested
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, log_level.upper()))
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        self._configured = True

        # Log initialization
        logger = logging.getLogger(__name__)
        logger.info(f"{APP_NAME} logging initialized")
        logger.info(f"Log level: {log_level}")
        logger.info(f"Log file: {self._log_file_path}")

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance for a specific module.

        Args:
            name: Logger name (typically __name__)

        Returns:
            Logger instance
        """
        return logging.getLogger(name)

    def set_log_level(self, level: str) -> None:
        """Change the logging level at runtime.

        Args:
            level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        log_level = getattr(logging, level.upper())
        logging.getLogger().setLevel(log_level)

        # Update console handler level if it exists
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, RotatingFileHandler):
                handler.setLevel(log_level)

        logger = logging.getLogger(__name__)
        logger.info(f"Log level changed to {level}")

    @property
    def log_file_path(self) -> Optional[Path]:
        """Get the current log file path."""
        return self._log_file_path

    @property
    def is_configured(self) -> bool:
        """Check if logging has been configured."""
        return self._configured
