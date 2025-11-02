import logging

def log_event(message, level="info"):
    """Log events with specified level."""
    logger = logging.getLogger()
    getattr(logger, level)(message)
