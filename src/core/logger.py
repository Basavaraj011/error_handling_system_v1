"""
Centralized logging configuration
"""
import logging
from config.settings import LOG_LEVEL, LOG_FORMAT


def logger(name: str) -> logging.Logger:
    """Setup and return a configured logger"""
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    
    # Console handler
    handler = logging.StreamHandler()
    handler.setLevel(LOG_LEVEL)
    
    # Formatter
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)
    
    # Add handler to logger
    if not logger.handlers:
        logger.addHandler(handler)
    
    return logger


# Convenience function
def get_logger(name: str) -> logging.Logger:
    """Get a logger by name"""
    return logging.getLogger(name)
