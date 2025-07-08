"""Logging configuration for GNOME AI Assistant."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
import os


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up structured logging for the assistant service.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file (optional)
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("gnome_ai_assistant")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module."""
    return logging.getLogger(f"gnome_ai_assistant.{name}")


def setup_service_logging() -> logging.Logger:
    """Set up logging for the main service."""
    log_dir = Path.home() / ".local" / "share" / "gnome-ai-assistant" / "logs"
    log_file = log_dir / "service.log"
    
    # Get log level from environment
    log_level = os.getenv("GNOME_AI_LOG_LEVEL", "INFO")
    
    return setup_logging(
        log_level=log_level,
        log_file=str(log_file)
    )
