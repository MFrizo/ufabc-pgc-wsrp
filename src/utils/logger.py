"""
Module: logger
Description: Standardized logging configuration for the WSRP optimization project.
             Replaces standard print() statements to provide timestamped,
             leveled, and file-persistent audit trails for benchmarking.
"""

import logging
import sys


def setup_logger(logger_name: str = "WSRP_Engine", log_level: int = logging.INFO) -> logging.Logger:
    """
    Configures and returns a standard Python logger.

    Args:
        logger_name (str): The name of the logger instance.
        log_level (int): The logging severity level (e.g., logging.INFO, logging.DEBUG).

    Returns:
        logging.Logger: The configured logger object ready to be used across modules.
    """
    # 1. Instantiate the logger
    logger = logging.getLogger(logger_name)

    # 2. Prevent adding multiple handlers if the logger is called multiple times (e.g., in Jupyter)
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(log_level)

    # 3. Define the academic standard format for logs
    # Format: [YYYY-MM-DD HH:MM:SS] [LEVEL] - Message
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 4. Standard Output Handler (Console)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Note: FileHandler can be added here later to persist logs in data/output/

    return logger

# Singleton instance for quick import across the project
project_logger = setup_logger()
