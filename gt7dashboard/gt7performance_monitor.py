import time
from functools import wraps
import logging
from gt7dashboard.gt7settings import get_log_level


class ColoredFormatter(logging.Formatter):
    """Custom formatter to add colors to log levels"""

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"  # Reset color

    def format(self, record):
        # Get the original formatted message
        log_message = super().format(record)

        # Add color based on log level
        color = self.COLORS.get(record.levelname, "")
        if color:
            # Color the entire message
            return f"{color}{log_message}{self.RESET}"

        return log_message


logger = logging.getLogger(__name__)
logger.setLevel(get_log_level())

# Create colored handler if one doesn't exist
if not logger.handlers:
    handler = logging.StreamHandler()
    colored_formatter = ColoredFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
    )
    handler.setFormatter(colored_formatter)
    logger.addHandler(handler)


def performance_monitor(func):
    """Decorator to monitor method performance"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        result = func(self, *args, **kwargs)
        execution_time = time.time() - start_time

        if execution_time > 0.1:  # Log slow operations
            logger.debug(f"{func.__name__} took {execution_time:.3f}s")
        return result

    return wrapper
