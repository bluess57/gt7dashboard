class Session:
    def __init__(self):
        # best lap overall
        self.special_packet_time = 0
        self.best_lap = -1
        self.min_body_height = 1000000  # deliberate high number to be counted down
        self.max_speed = 0

    def __eq__(self, other):
        return (
            other is not None
            and self.best_lap == other.best_lap
            and self.min_body_height == other.min_body_height
            and self.max_speed == other.max_speed
        )