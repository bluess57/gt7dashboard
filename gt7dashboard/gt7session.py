import logging
from typing import List

from gt7dashboard.gt7lap import Lap

logger = logging.getLogger("gt7session")
logger.setLevel(logging.INFO)


class GT7Session:
    def __init__(self):
        self._on_load_laps_callbacks = []
        self._on_add_lap_callbacks = []
        # best lap overall
        self.special_packet_time = 0
        self.best_lap = -1
        self.min_body_height = 1000000  # deliberate high number to be counted down
        self.max_speed = 0
        self.laps = []

    def __eq__(self, other):
        return (
            other is not None
            and self.best_lap == other.best_lap
            and self.min_body_height == other.min_body_height
            and self.max_speed == other.max_speed
        )

    def reset(self):
        """Reset the session data."""
        self.special_packet_time = 0
        self.best_lap = -1
        self.min_body_height = 1000000
        self.max_speed = 0
        self.laps = []
        # Note: Callbacks are preserved during reset
        # If you want to clear them too, uncomment the next line:
        # self.clear_on_load_laps_callbacks()
        # if needed add a self.clear_on_add_lap_callbacks()

    def add_lap(self, lap: Lap):
        """Add a single lap to the session."""
        self.laps.append(lap)
        # Optionally update max_speed or other stats here
        if hasattr(lap, "max_speed"):
            self.max_speed = max(self.max_speed, getattr(lap, "max_speed", 0))
        # Call all registered callbacks
        for callback in self._on_add_lap_callbacks:
            try:
                callback(lap)
            except Exception as e:
                logger.error(f"Error calling add_lap callback: {e}")

    def get_laps(self) -> List[Lap]:
        return self.laps

    def load_laps(
        self,
        laps: List[Lap],
        to_last_position=False,
        to_first_position=False,
        replace_other_laps=False,
    ):
        if to_last_position:
            self.laps = self.laps + laps
        elif to_first_position:
            self.laps = laps + self.laps
        elif replace_other_laps:
            self.laps = laps

        if self.laps:
            self.max_speed = max(
                (getattr(lap, "max_speed", 0) for lap in self.laps), default=0
            )

        # Call all registered callbacks
        for callback in self._on_load_laps_callbacks:
            try:
                callback(laps)
            except Exception as e:
                logger.error(f"Error calling load_laps callback: {e}")

    def set_on_add_lap_callback(self, callback):
        """Register a callback to be called when a lap is added."""
        if callback not in self._on_add_lap_callbacks:
            self._on_add_lap_callbacks.append(callback)

    def set_on_load_laps_callback(self, callback):
        """Register a callback to be called when laps are loaded."""
        if callback not in self._on_load_laps_callbacks:
            self._on_load_laps_callbacks.append(callback)

    def remove_on_load_laps_callback(self, callback):
        """Remove a callback from the load_laps event."""
        if callback in self._on_load_laps_callbacks:
            self._on_load_laps_callbacks.remove(callback)

    def clear_on_load_laps_callbacks(self):
        """Clear all load_laps callbacks."""
        self._on_load_laps_callbacks.clear()

    def delete_lap(self, lap_number):
        self.laps = [
            lap for lap in self.laps if getattr(lap, "number", None) != lap_number
        ]
        logger.info("gt7session delete lap %s", lap_number)
