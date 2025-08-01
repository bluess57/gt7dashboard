import logging
from typing import List

from gt7dashboard.gt7lap import Lap

logger = logging.getLogger("gt7session")
logger.setLevel(logging.INFO)


class GT7Session:
    def __init__(self):
        self._on_load_laps_callback = None
        self._on_add_lap_callback = None
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

    def add_lap(self, lap: Lap):
        """Add a single lap to the session."""
        self.laps.append(lap)
        # Optionally update max_speed or other stats here
        if hasattr(lap, "max_speed"):
            self.max_speed = max(self.max_speed, getattr(lap, "max_speed", 0))
        if self._on_add_lap_callback:
            self._on_add_lap_callback(lap)

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

        if self._on_load_laps_callback:
            self._on_load_laps_callback(laps)

    def set_on_add_lap_callback(self, callback):
        """Register a callback to be called when a lap is added."""
        self._on_add_lap_callback = callback

    def set_on_load_laps_callback(self, callback):
        """Register a callback to be called when laps are loaded."""
        self._on_load_laps_callback = callback

    def delete_lap(self, lap_number):
        self.laps = [
            lap for lap in self.laps if getattr(lap, "number", None) != lap_number
        ]
        logger.info("gt7session delete lap %s", lap_number)
