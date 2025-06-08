#!/usr/bin/env python
# filepath: /Users/jlacanienta/Projects/graphrag-contract-review/logger.py
"""
Logger module for GraphRAG Contract Review
Provides logging functions and utilities for log management.
"""

import os
import logging
import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import List, Optional, Union

# Configure logging format
class CustomFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    FORMATS = {
        logging.DEBUG: format_str,
        logging.INFO: format_str,
        logging.WARNING: format_str,
        logging.ERROR: format_str,
        logging.CRITICAL: format_str
    }
    
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: The name of the logger
        
    Returns:
        A configured logger
    """
    logger = logging.getLogger(name)
    
    # Only configure if it hasn't been configured before
    if not logger.handlers:
        logger.setLevel(logging.INFO)  # Change from DEBUG to INFO to reduce verbosity
        
        # Console handler with colors
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)  # Set console handler to INFO level
        console_handler.setFormatter(CustomFormatter())
        logger.addHandler(console_handler)
        
        # File handler for daily logs
        try:
            # Get the logs directory relative to this file's location
            logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
            os.makedirs(logs_dir, exist_ok=True)
            
            log_file_path = os.path.join(logs_dir, f"graphrag-{datetime.datetime.now().strftime('%Y-%m-%d')}.log")
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setLevel(logging.INFO)  # Set file handler to INFO level
            file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            logger.addHandler(file_handler)
        except Exception as e:
            # If file logging fails, still log to console
            console_handler.setLevel(logging.WARNING)
            logger.warning(f"Could not set up file logging: {str(e)}")
    
    return logger

def get_log_file_paths(max_count: int = 10) -> List[str]:
    """
    Get a list of log file paths sorted by date (newest first).
    
    Args:
        max_count: Maximum number of log files to return
        
    Returns:
        List of absolute paths to log files
    """
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    
    if not os.path.exists(logs_dir):
        return []
    
    log_files = []
    for filename in os.listdir(logs_dir):
        if filename.endswith(".log"):
            log_files.append(os.path.join(logs_dir, filename))
    
    # Sort by modification time (newest first)
    log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    return log_files[:max_count]

def read_log_file(log_file_path: str, max_lines: int = 100) -> str:
    """
    Read the specified log file and return the last N lines.
    
    Args:
        log_file_path: Path to the log file
        max_lines: Maximum number of lines to read from the end
        
    Returns:
        String containing the log content (last N lines)
    """
    try:
        if not os.path.exists(log_file_path):
            return f"Log file not found: {log_file_path}"
        
        with open(log_file_path, 'r', encoding='utf-8') as file:
            # Read all lines and get the last max_lines
            lines = file.readlines()
            last_lines = lines[-max_lines:] if len(lines) > max_lines else lines
            return ''.join(last_lines)
    except Exception as e:
        return f"Error reading log file: {str(e)}"

def log_info(message: str, logger_instance: Optional[logging.Logger] = None, **kwargs):
    """Log an info message using the specified or default logger"""
    (logger_instance or get_logger("default")).info(message, **kwargs)

def log_error(message: str, logger_instance: Optional[logging.Logger] = None, exc_info: bool = False, **kwargs):
    """Log an error message using the specified or default logger"""
    (logger_instance or get_logger("default")).error(message, exc_info=exc_info, **kwargs)

def log_warning(message: str, logger_instance: Optional[logging.Logger] = None, **kwargs):
    """Log a warning message using the specified or default logger"""
    (logger_instance or get_logger("default")).warning(message, **kwargs)

def log_debug(message: str, logger_instance: Optional[logging.Logger] = None, **kwargs):
    """Log a debug message using the specified or default logger"""
    (logger_instance or get_logger("default")).debug(message, **kwargs)
