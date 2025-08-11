import logging
import os


class GT7Settings:
    """Centralized settings for GT7 Dashboard"""

    def __init__(self):
        self._log_level = None

    def get_log_level(self) -> int:
        """Get the logging level from environment or default"""
        if self._log_level is None:
            level_str = os.getenv("GT7_LOG_LEVEL", "INFO").upper()
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL,
            }
            self._log_level = level_map.get(level_str, logging.INFO)
        return self._log_level

    def set_log_level(self, level: str):
        """Set the logging level programmatically"""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        self._log_level = level_map.get(level.upper(), logging.INFO)


# Global settings instance
settings = GT7Settings()


# Convenience function for backward compatibility
def get_log_level():
    return settings.get_log_level()
