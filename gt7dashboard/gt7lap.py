import math
import logging
import pandas as pd
from scipy.signal import find_peaks
from datetime import datetime
from typing import List
from pandas import DataFrame

from gt7dashboard.gt7car import car_name
from .gt7settings import get_log_level

import numpy as np

RACE_LINE_BRAKING_MODE = "RACE_LINE_BRAKING_MODE"
RACE_LINE_THROTTLE_MODE = "RACE_LINE_THROTTLE_MODE"
RACE_LINE_COASTING_MODE = "RACE_LINE_COASTING_MODE"

# Set up logging
logger = logging.getLogger("gt7lap.py")
logger.setLevel(get_log_level())


class Lap:
    def __init__(self):
        # Nice title for lap
        self.title = ""
        # Number of all lap ticks
        self.lap_ticks = 1
        # Lap time after crossing the finish line
        self.lap_finish_time = 0
        # Live time during a live lap
        self.lap_live_time = 0
        # Total number of laps
        self.total_laps = 0
        # Number of current lap
        self.number = 0
        # Aggregated number of instances where condition is true
        self.throttle_and_brake_ticks = 0
        self.no_throttle_and_no_brake_ticks = 0
        self.full_brake_ticks = 0
        self.full_throttle_ticks = 0
        self.tyres_overheated_ticks = 0
        self.tyres_spinning_ticks = 0
        # Data points with value for every tick
        self.data_throttle = []
        self.data_braking = []
        self.data_coasting = []
        self.data_speed = []
        self.data_time = []
        self.data_rpm = []
        self.data_gear = []
        self.data_tyres = []
        # Positions on x,y,z
        self.data_position_x = []
        self.data_position_y = []
        self.data_position_z = []
        # Fuel
        self.fuel_at_start = 0
        self.fuel_at_end = -1
        self.fuel_consumed = -1
        # Boost
        self.data_boost = []
        # Yaw Rate
        self.data_rotation_yaw = []
        self.data_absolute_yaw_rate_per_second = []
        # Car
        self.car_id = 0

        # Always record was set when recording the lap, likely a replay
        self.is_replay = False
        self.is_manual = False

        self.lap_start_timestamp = datetime.now()
        self.lap_end_timestamp = -1

    @staticmethod
    def seconds_to_lap_time(seconds):
        prefix = ""
        if seconds < 0:
            prefix = "-"
            seconds *= -1

        minutes = seconds // 60
        remaining = seconds % 60
        return prefix + "{:01.0f}:{:06.3f}".format(minutes, remaining)

    def pct(self, val):
        lap_ticks = getattr(self, "lap_ticks", 1) or 1
        return "%d" % (getattr(self, val, 0) / lap_ticks * 1000)

    def lap_to_dict(self) -> dict:
        """
        Convert a Lap object to a dictionary suitable for the DataTable.
        """
        replay = "Y" if getattr(self, "is_replay", False) else "N"

        return {
            "number": getattr(self, "number", None),
            "time": self.seconds_to_lap_time(
                getattr(self, "lap_finish_time", 0) / 1000
            ),
            "diff": "",
            "timestamp": (
                getattr(self, "lap_start_timestamp", "").strftime("%Y-%m-%d %H:%M:%S")
                if getattr(self, "lap_start_timestamp", None)
                else ""
            ),
            "replay": replay,
            "car_name": car_name(getattr(self, "car_id", None)),
            "fuelconsumed": "%d" % getattr(self, "fuel_consumed", 0),
            "fullthrottle": self.pct("full_throttle_ticks"),
            "throttleandbrake": self.pct("throttle_and_brake_ticks"),
            "fullbrake": self.pct("full_brake_ticks"),
            "nothrottle": self.pct("no_throttle_and_no_brake_ticks"),
            "tyrespinning": self.pct("tyres_spinning_ticks"),
        }

    def __str__(self):
        return "\n %s, %2d, %1.f, %4d, %4d, %4d" % (
            self.title,
            self.number,
            self.fuel_at_end,
            self.full_throttle_ticks,
            self.full_brake_ticks,
            self.no_throttle_and_no_brake_ticks,
        )

    def format(self):
        return "Lap %2d, %s (%d Ticks)" % (
            self.number,
            self.title,
            len(self.data_speed),
        )

    def format_time(self):
        # Format the lap time appropriately
        minutes = int(self.data_time // 60)
        seconds = int(self.data_time % 60)
        milliseconds = int((self.data_time % 1) * 1000)
        return f"{minutes}:{seconds:02d}.{milliseconds:03d}"

    def find_speed_peaks_and_valleys(
        self, width: int = 100
    ) -> tuple[list[int], list[int]]:
        inv_data_speed = [i * -1 for i in self.data_speed]
        peaks, whatisthis = find_peaks(self.data_speed, width=width)
        valleys, whatisthis = find_peaks(inv_data_speed, width=width)
        return list(peaks), list(valleys)

    def mget_speed_peaks_and_valleys(self):
        peaks, valleys = self.find_speed_peaks_and_valleys(width=100)

        peak_speed_data_x = []
        peak_speed_data_y = []

        valley_speed_data_x = []
        valley_speed_data_y = []

        for p in peaks:
            peak_speed_data_x.append(self.data_speed[p])
            peak_speed_data_y.append(p)

        for v in valleys:
            valley_speed_data_x.append(self.data_speed[v])
            valley_speed_data_y.append(v)

        return (
            peak_speed_data_x,
            peak_speed_data_y,
            valley_speed_data_x,
            valley_speed_data_y,
        )

    def get_speed_peaks_and_valleys(self):
        (
            peak_speed_data_x,
            peak_speed_data_y,
            valley_speed_data_x,
            valley_speed_data_y,
        ) = self.mget_speed_peaks_and_valleys()

        return (
            peak_speed_data_x,
            peak_speed_data_y,
            valley_speed_data_x,
            valley_speed_data_y,
        )

    def get_x_axis_for_distance(self) -> List:
        x_axis = [0.0]
        tick_time = 16.668  # https://www.gtplanet.net/forum/threads/gt7-is-compatible-with-motion-rig.410728/post-13806131
        for i in range(1, len(self.data_speed)):
            if self.data_speed[i] is None or self.data_speed[i] == 0:
                # If speed is None or 0, we cannot calculate distance
                x_axis.append(x_axis[i - 1])
                continue
            increment = (float(self.data_speed[i]) / 3.6 / 1000) * tick_time
            x_axis.append(x_axis[i - 1] + increment)

        return x_axis

    def get_race_line_coordinates_when_mode_is_active(self, mode: str):
        return_y = []
        return_x = []
        return_z = []

        for i, _ in enumerate(self.data_braking):

            if mode == RACE_LINE_BRAKING_MODE:
                if self.data_braking[i] > self.data_throttle[i]:
                    return_y.append(self.data_position_y[i])
                    return_x.append(self.data_position_x[i])
                    return_z.append(self.data_position_z[i])
                else:
                    return_y.append("NaN")
                    return_x.append("NaN")
                    return_z.append("NaN")

            if mode == RACE_LINE_THROTTLE_MODE:
                if self.data_braking[i] < self.data_throttle[i]:
                    return_y.append(self.data_position_y[i])
                    return_x.append(self.data_position_x[i])
                    return_z.append(self.data_position_z[i])
                else:
                    return_y.append("NaN")
                    return_x.append("NaN")
                    return_z.append("NaN")

            if mode == RACE_LINE_COASTING_MODE:
                if self.data_braking[i] == 0 and self.data_throttle[i] == 0:
                    return_y.append(self.data_position_y[i])
                    return_x.append(self.data_position_x[i])
                    return_z.append(self.data_position_z[i])
                else:
                    return_y.append("NaN")
                    return_x.append("NaN")
                    return_z.append("NaN")

        return return_y, return_x, return_z

    def get_x_axis_depending_on_mode(self, distance_mode: bool):
        if distance_mode:
            # Calculate distance for x axis
            return self.get_x_axis_for_distance()
        else:
            # Use ticks as length, which is the length of any given data list
            return list(range(len(self.data_speed)))

    def get_data_dict(self, distance_mode=True) -> dict[str, list]:
        raceline_y_throttle, raceline_x_throttle, raceline_z_throttle = (
            self.get_race_line_coordinates_when_mode_is_active(
                mode=RACE_LINE_THROTTLE_MODE
            )
        )
        raceline_y_braking, raceline_x_braking, raceline_z_braking = (
            self.get_race_line_coordinates_when_mode_is_active(
                mode=RACE_LINE_BRAKING_MODE
            )
        )
        raceline_y_coasting, raceline_x_coasting, raceline_z_coasting = (
            self.get_race_line_coordinates_when_mode_is_active(
                mode=RACE_LINE_COASTING_MODE
            )
        )

        if not self.data_throttle:
            distance = []
        else:
            distance = self.get_x_axis_depending_on_mode(distance_mode)

        data = {
            "throttle": self.data_throttle,
            "brake": self.data_braking,
            "speed": self.data_speed,
            "time": self.data_time,
            "tyres": self.data_tyres,
            "rpm": self.data_rpm,
            "boost": self.data_boost,
            "yaw_rate": self.data_absolute_yaw_rate_per_second,
            "gear": self.data_gear,
            "ticks": list(range(len(self.data_speed))),
            "coast": self.data_coasting,
            "raceline_y": self.data_position_y,
            "raceline_x": self.data_position_x,
            "raceline_z": self.data_position_z,
            # For a raceline when throttle is engaged
            "raceline_y_throttle": raceline_y_throttle,
            "raceline_x_throttle": raceline_x_throttle,
            "raceline_z_throttle": raceline_z_throttle,
            # For a raceline when braking is engaged
            "raceline_y_braking": raceline_y_braking,
            "raceline_x_braking": raceline_x_braking,
            "raceline_z_braking": raceline_z_braking,
            # For a raceline when neither throttle nor brake is engaged
            "raceline_y_coasting": raceline_y_coasting,
            "raceline_x_coasting": raceline_x_coasting,
            "raceline_z_coasting": raceline_z_coasting,
            "distance": distance,
        }

        return data

    def calculate_total_distance_traveled(self) -> float:
        """Calculate cumulative distance between 3D positions"""
        if len(self.data_position_x) < 2:
            return 0.0

        total_distance = 0.0

        # Cache references to avoid attribute lookups
        pos_x = self.data_position_x
        pos_y = self.data_position_y
        pos_z = self.data_position_z

        # Vectorized approach using list comprehension and zip
        for i in range(1, len(pos_x)):
            # Skip if any coordinate is None
            if None in (
                pos_x[i],
                pos_y[i],
                pos_z[i],
                pos_x[i - 1],
                pos_y[i - 1],
                pos_z[i - 1],
            ):
                continue

            dx = pos_x[i] - pos_x[i - 1]
            dy = pos_y[i] - pos_y[i - 1]
            dz = pos_z[i] - pos_z[i - 1]

            total_distance += math.sqrt(dx * dx + dy * dy + dz * dz)

        return total_distance

    def calculate_total_distance_traveled_numpy(self) -> float:
        """Calculate cumulative distance using NumPy for maximum performance"""
        if len(self.data_position_x) < 2:
            return 0.0

        # Convert to numpy arrays (handles None values automatically)
        try:
            pos_x = np.array(self.data_position_x, dtype=float)
            pos_y = np.array(self.data_position_y, dtype=float)
            pos_z = np.array(self.data_position_z, dtype=float)

            # Calculate differences
            dx = np.diff(pos_x)
            dy = np.diff(pos_y)
            dz = np.diff(pos_z)

            # Calculate distances and sum (ignoring NaN values)
            distances = np.sqrt(dx * dx + dy * dy + dz * dz)
            return float(np.nansum(distances))

        except (ValueError, TypeError):
            # Fallback to optimized pure Python version
            return self.calculate_total_distance_traveled()

    @staticmethod
    def calculate_time_diff_by_distance(
        reference_lap: "Lap", comparison_lap: "Lap"
    ) -> DataFrame:
        df1 = Lap.get_time_delta_dataframe_for_lap(reference_lap, "reference")
        df2 = Lap.get_time_delta_dataframe_for_lap(comparison_lap, "comparison")

        df = df1.join(df2, how="outer").sort_index().interpolate()

        # After interpolation, we can make the index a normal field and rename it
        df.reset_index(inplace=True)
        df = df.rename(columns={"index": "distance"})

        # Convert integer timestamps back to timestamp format
        s_reference_timestamped = pd.to_timedelta(getattr(df, "reference"))
        s_comparison_timestamped = pd.to_timedelta(getattr(df, "comparison"))

        df["reference"] = s_reference_timestamped
        df["comparison"] = s_comparison_timestamped

        df["timedelta"] = df["comparison"] - df["reference"]
        return df

    def get_brake_points(self):
        """Get brake points with optimized performance using NumPy"""
        if len(self.data_braking) < 2:
            return [], []

        try:
            # Convert to numpy arrays for vectorized operations
            braking = np.array(self.data_braking, dtype=float)
            pos_x = np.array(self.data_position_x, dtype=float)
            pos_z = np.array(self.data_position_z, dtype=float)

            # Vectorized brake point detection: prev==0 and curr>0
            brake_start_mask = (braking[:-1] == 0) & (braking[1:] > 0)
            brake_indices = np.where(brake_start_mask)[0] + 1

            # Extract coordinates at brake points
            x = pos_x[brake_indices].tolist()
            y = pos_z[brake_indices].tolist()

            return x, y

        except (ValueError, TypeError) as e:
            logger.warning(f"NumPy brake point detection failed: {e}, using fallback")
            return self._get_brake_points_fallback()

    def _get_brake_points_fallback(self):
        """Fallback optimized Python version"""
        if len(self.data_braking) < 2:
            return [], []

        # Cache attribute references
        braking = self.data_braking
        pos_x = self.data_position_x
        pos_z = self.data_position_z

        x = []
        y = []
        prev_brake = braking[0]

        for i in range(1, len(braking)):
            curr_brake = braking[i]
            if prev_brake == 0 and curr_brake > 0:
                x.append(pos_x[i])
                y.append(pos_z[i])
            prev_brake = curr_brake

        return x, y

    @staticmethod
    def get_time_delta_dataframe_for_lap(lap: "Lap", name: str) -> DataFrame:
        lap_distance = lap.get_x_axis_for_distance()
        lap_time = lap.data_time

        # Multiply to match datatype which is nanoseconds?
        lap_time_ms = [lap.convert_seconds_to_milliseconds(item) for item in lap_time]

        series = pd.Series(lap_distance, index=pd.to_timedelta(lap_time_ms, unit="ms"))

        upsample = series.resample("10ms").asfreq()
        interpolated_upsample = upsample.interpolate()

        # Make distance to index and time to value, because we want to join on distance
        inverted = pd.Series(
            interpolated_upsample.index.values, index=interpolated_upsample
        )

        # Flip around, we have to convert timedelta back to integer to do this
        s1 = pd.Series(inverted.values.astype("int64"), name=name, index=inverted.index)

        df1 = DataFrame(data=s1)
        # returns a dataframe where index is distance travelled and first data field is time passed
        return df1

    @staticmethod
    def convert_seconds_to_milliseconds(seconds: int):
        minutes = seconds // 60
        remaining = seconds % 60

        return minutes * 60000 + remaining * 1000
