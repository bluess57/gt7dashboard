from typing import List

from gt7dashboard.gt7lap import Lap

class GT7Session:
    def __init__(self):
        self._on_load_laps_callback = None

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

    def get_laps(self) -> List[Lap]:
        return self.laps

    def load_laps(self, laps: List[Lap], to_last_position = False, to_first_position = False, replace_other_laps = False):
        if to_last_position:
            self.laps = self.laps + laps
        elif to_first_position:
            self.laps = laps + self.laps
        elif replace_other_laps:
            self.laps = laps
        
        if self._on_load_laps_callback:
            self._on_load_laps_callback(laps)

    def set_on_load_laps_callback(self, callback):
        """Register a callback to be called when laps are loaded."""
        self._on_load_laps_callback = callback


    def delete_lap(self, lap_number):
        original_count = len(self.laps)
        self.laps = [lap for lap in self.laps if getattr(lap, 'number', None) != lap_number]
        new_count = len(self.laps)
