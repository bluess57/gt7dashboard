import itertools
import statistics

from datetime import datetime, timezone
from pathlib import Path
from statistics import StatisticsError
from typing import Tuple, List

import pandas as pd
from pandas import DataFrame
from tabulate import tabulate

from gt7dashboard.gt7lap import Lap
from gt7dashboard.gt7lapfile import LapFile
from gt7dashboard.gt7fuelmap import FuelMap
from gt7dashboard.gt7car import car_name


def calculate_remaining_fuel(
    fuel_start_lap: int, fuel_end_lap: int, lap_time: int
) -> Tuple[int, float, float]:
    # no fuel consumed
    if fuel_start_lap == fuel_end_lap:
        return 0, -1, -1

    # fuel consumed, calculate
    fuel_consumed_per_lap = fuel_start_lap - fuel_end_lap
    laps_remaining = fuel_end_lap / fuel_consumed_per_lap
    time_remaining = laps_remaining * lap_time

    return fuel_consumed_per_lap, laps_remaining, time_remaining


def mark_if_matches_highest_or_lowest(
    value: float, highest: List[int], lowest: List[int], order: int, high_is_best=True
) -> str:
    green = 32
    red = 31
    reset = 0

    high = green
    low = red

    if not high_is_best:
        low = green
        high = red

    if value == highest[order]:
        return "\x1b[1;%dm%0.f\x1b[1;%dm" % (high, value, reset)

    if value == lowest[order]:
        return "\x1b[1;%dm%0.f\x1b[1;%dm" % (low, value, reset)

    return "%0.f" % value


def format_laps_to_table(laps: List[Lap], best_lap: float) -> str:
    highest = [0, 0, 0, 0, 0]
    lowest = [999999, 999999, 999999, 999999, 999999]

    # Display lap times
    table = []
    for idx, lap in enumerate(laps):
        lap_color = 39  # normal color
        time_diff = ""

        if best_lap == lap.lap_finish_time:
            lap_color = 35  # magenta
        elif lap.lap_finish_time < best_lap:
            # lap_finish_time cannot be smaller than last_lap, last_lap is always the smallest.
            # This can only mean that lap.lap_finish_time is from an earlier race on a different track
            time_diff = "-"
        elif best_lap > 0:
            time_diff = seconds_to_lap_time(
                -1 * (best_lap / 1000 - lap.lap_finish_time / 1000)
            )

        ft_ticks = lap.full_throttle_ticks / lap.lap_ticks * 1000
        tb_ticks = lap.throttle_and_brake_ticks / lap.lap_ticks * 1000
        fb_ticks = lap.full_brake_ticks / lap.lap_ticks * 1000
        nt_ticks = lap.no_throttle_and_no_brake_ticks / lap.lap_ticks * 1000
        ti_ticks = lap.tyres_spinning_ticks / lap.lap_ticks * 1000

        list_of_ticks = [ft_ticks, tb_ticks, fb_ticks, nt_ticks, ti_ticks]

        for i, value in enumerate(list_of_ticks):
            if list_of_ticks[i] > highest[i]:
                highest[i] = list_of_ticks[i]

            if list_of_ticks[i] <= lowest[i]:
                lowest[i] = list_of_ticks[i]

        table.append(
            [
                # number
                "\x1b[1;%dm%d" % (lap_color, lap.number),
                # Timing
                seconds_to_lap_time(lap.lap_finish_time / 1000),
                time_diff,
                lap.fuel_at_end,
                lap.fuel_consumed,
                # Ticks
                ft_ticks,
                tb_ticks,
                fb_ticks,
                nt_ticks,
                ti_ticks,
            ]
        )

    for i, entry in enumerate(table):
        for k, val in enumerate(table[i]):
            if k == 5:
                table[i][k] = mark_if_matches_highest_or_lowest(
                    table[i][k], highest, lowest, 0, high_is_best=True
                )
            elif k == 6:
                table[i][k] = mark_if_matches_highest_or_lowest(
                    table[i][k], highest, lowest, 1, high_is_best=False
                )
            elif k == 7:
                table[i][k] = mark_if_matches_highest_or_lowest(
                    table[i][k], highest, lowest, 2, high_is_best=True
                )
            elif k == 8:
                table[i][k] = mark_if_matches_highest_or_lowest(
                    table[i][k], highest, lowest, 3, high_is_best=False
                )
            elif k == 9:
                table[i][k] = mark_if_matches_highest_or_lowest(
                    table[i][k], highest, lowest, 4, high_is_best=False
                )

    return tabulate(
        table,
        headers=["#", "Time", "Diff", "Fuel", "FuCo", "fT", "T+B", "fB", "0T", "Spin"],
        floatfmt=".0f",
    )


def seconds_to_lap_time(seconds):
    prefix = ""
    if seconds < 0:
        prefix = "-"
        seconds *= -1

    minutes = seconds // 60
    remaining = seconds % 60
    return prefix + "{:01.0f}:{:06.3f}".format(minutes, remaining)


def none_ignoring_median(data):
    """Return the median (middle value) of numeric data but ignore None values.

    When the number of data points is odd, return the middle data point.
    When the number of data points is even, the median is interpolated by
    taking the average of the two middle values:

    >>> none_ignoring_median([1, 3, None, 5])
    3
    >>> none_ignoring_median([1, 3, 5, None, 7])
    4.0

    """
    # FIXME improve me
    filtered_data = []
    for d in data:
        if d is not None:
            filtered_data.append(d)
    filtered_data = sorted(filtered_data)
    n = len(filtered_data)
    if n == 0:
        raise StatisticsError("no median for empty data")
    if n % 2 == 1:
        return filtered_data[n // 2]
    else:
        i = n // 2
        return (filtered_data[i - 1] + filtered_data[i]) / 2


def get_last_reference_median_lap(
    laps: List[Lap], reference_lap_selected: Lap
) -> Tuple[Lap, Lap, Lap]:
    last_lap = None
    reference_lap = None
    median_lap = None

    if len(laps) > 0:  # Only show last lap
        last_lap = laps[0]

    if len(laps) >= 2 and not reference_lap_selected:
        reference_lap = get_best_lap(laps)

    if len(laps) >= 3:
        median_lap = get_median_lap(laps)

    if reference_lap_selected:
        reference_lap = reference_lap_selected

    return last_lap, reference_lap, median_lap


def get_best_lap(laps: List[Lap]):
    if len(laps) == 0:
        return None

    return sorted(laps, key=lambda x: x.lap_finish_time, reverse=False)[0]


def get_median_lap(laps: List[Lap]) -> Lap:
    if len(laps) == 0:
        raise Exception("Lap list does not contain any laps")

    # Filter out too long laps, like box laps etc. use 10 Seconds of the best lap as a threshold
    best_lap = get_best_lap(laps)
    ten_seconds = 10000
    laps = filter_max_min_laps(
        laps,
        best_lap.lap_finish_time + ten_seconds,
        best_lap.lap_finish_time - ten_seconds,
    )

    median_lap = Lap()
    if len(laps) == 0:
        return median_lap

    for val in vars(laps[0]):
        attributes = []
        for lap in laps:
            if val == "options":
                continue
            attr = getattr(lap, val)
            # FIXME why is it sometimes string AND int?
            if not isinstance(attr, str) and attr != "" and attr != []:
                attributes.append(getattr(lap, val))

        if len(attributes) == 0:
            continue
        if isinstance(getattr(laps[0], val), datetime):
            continue

        if isinstance(getattr(laps[0], val), list):
            median_attribute = [
                none_ignoring_median(k)
                for k in itertools.zip_longest(*attributes, fillvalue=None)
            ]
        else:
            median_attribute = statistics.median(attributes)
        setattr(median_lap, val, median_attribute)

    median_lap.title = "Median (%d Laps): %s" % (
        len(laps),
        seconds_to_lap_time(median_lap.lap_finish_time / 1000),
    )

    return median_lap


def filter_max_min_laps(laps: List[Lap], max_lap_time=-1, min_lap_time=-1) -> List[Lap]:
    if max_lap_time > 0:
        laps = list(filter(lambda l: l.lap_finish_time <= max_lap_time, laps))

    if min_lap_time > 0:
        laps = list(filter(lambda l: l.lap_finish_time >= min_lap_time, laps))

    return laps


def pd_data_frame_from_lap(laps: List[Lap], best_lap_time: int) -> pd.DataFrame:
    rows = []
    for i, lap in enumerate(laps):
        time_diff = ""
        replay = "N"

        if lap.is_replay:
            replay = "Y"

        if best_lap_time == lap.lap_finish_time:
            pass
        elif lap.lap_finish_time < best_lap_time:
            time_diff = "-"
        elif best_lap_time > 0:
            time_diff = "+" + seconds_to_lap_time(
                -1 * (best_lap_time / 1000 - lap.lap_finish_time / 1000)
            )

        rows.append(
            {
                "number": lap.number,
                "time": seconds_to_lap_time(lap.lap_finish_time / 1000),
                "diff": time_diff,
                "timestamp": lap.lap_start_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "replay": replay,
                "car_name": car_name(lap.car_id),
                "fuelconsumed": "%d" % lap.fuel_consumed,
                "fullthrottle": "%d" % (lap.full_throttle_ticks / lap.lap_ticks * 1000),
                "throttleandbreak": "%d"
                % (lap.throttle_and_brake_ticks / lap.lap_ticks * 1000),
                "fullbrake": "%d" % (lap.full_brake_ticks / lap.lap_ticks * 1000),
                "nothrottle": "%d"
                % (lap.no_throttle_and_no_brake_ticks / lap.lap_ticks * 1000),
                "tyrespinning": "%d"
                % (lap.tyres_spinning_ticks / lap.lap_ticks * 1000),
            }
        )

    df = pd.DataFrame(rows)
    return df


def bokeh_tuple_for_list_of_lapfiles(lapfiles: List[LapFile]):
    tuples = [""]  # Use empty first option which is default
    for lapfile in lapfiles:
        tuples.append(tuple((lapfile.path, lapfile.__str__())))
    return tuples


def bokeh_tuple_for_list_of_laps(laps: List[Lap]):
    tuples = []
    for i, lap in enumerate(laps):
        tuples.append(tuple((str(i), lap.format())))
    return tuples


def get_fuel_on_consumption_by_relative_fuel_levels(lap: Lap) -> List[FuelMap]:
    # Relative Setting, Laps to Go, Time to Go, Assumed Diff in Lap Times
    fuel_consumed_per_lap, laps_remaining, time_remaining = calculate_remaining_fuel(
        lap.fuel_at_start, lap.fuel_at_end, lap.lap_finish_time
    )
    i = -5

    # Source:
    # https://www.gtplanet.net/forum/threads/test-results-fuel-mixture-settings-and-other-fuel-saving-techniques.369387/
    fuel_consumption_per_level_change = 8
    power_per_level_change = 4

    relative_fuel_maps = []

    while i <= 5:
        relative_fuel_map = FuelMap(
            mixture_setting=i,
            power_percentage=(100 - i * power_per_level_change) / 100,
            consumption_percentage=(100 - i * fuel_consumption_per_level_change) / 100,
        )

        relative_fuel_map.fuel_consumed_per_lap = (
            fuel_consumed_per_lap * relative_fuel_map.consumption_percentage
        )
        relative_fuel_map.laps_remaining_on_current_fuel = (
            laps_remaining
            + laps_remaining * (1 - relative_fuel_map.consumption_percentage)
        )

        relative_fuel_map.time_remaining_on_current_fuel = (
            time_remaining
            + time_remaining * (1 - relative_fuel_map.consumption_percentage)
        )
        relative_fuel_map.lap_time_diff = lap.lap_finish_time * (
            1 - relative_fuel_map.power_percentage
        )
        relative_fuel_map.lap_time_expected = (
            lap.lap_finish_time + relative_fuel_map.lap_time_diff
        )

        relative_fuel_maps.append(relative_fuel_map)
        i += 1

    return relative_fuel_maps


def get_n_fastest_laps_within_percent_threshold_ignoring_replays(
    laps: List[Lap], number_of_laps: int, percent_threshold: float
):
    # FIXME Replace later with this line
    # filtered_laps = [lap for lap in laps if not lap.is_replay]
    filtered_laps = [
        lap for lap in laps if not (len(lap.data_speed) == 0 or lap.is_replay)
    ]

    if len(filtered_laps) == 0:
        return []

    # sort laps by finish time
    filtered_laps.sort(key=lambda lap: lap.lap_finish_time)
    fastest_lap = filtered_laps[0]
    threshold_laps = [
        lap
        for lap in filtered_laps
        if lap.lap_finish_time <= fastest_lap.lap_finish_time * (1 + percent_threshold)
    ]
    return threshold_laps[:number_of_laps]


DEFAULT_FASTEST_LAPS_PERCENT_THRESHOLD = 0.05


def get_variance_for_fastest_laps(
    laps: List[Lap],
    number_of_laps: int = 3,
    percent_threshold: float = DEFAULT_FASTEST_LAPS_PERCENT_THRESHOLD,
) -> tuple[DataFrame, list[Lap]]:
    fastest_laps: list[Lap] = (
        get_n_fastest_laps_within_percent_threshold_ignoring_replays(
            laps, number_of_laps, percent_threshold
        )
    )
    variance: DataFrame = get_variance_for_laps(fastest_laps)
    return variance, fastest_laps


def get_variance_for_laps(laps: List[Lap]) -> DataFrame:

    dataframe_distance_columns = []
    merged_df = pd.DataFrame(columns=["distance"])
    for lap in laps:
        d = {"speed": lap.data_speed, "distance": lap.get_x_axis_for_distance()}
        df = pd.DataFrame(data=d)
        dataframe_distance_columns.append(df)
        merged_df = pd.merge(merged_df, df, on="distance", how="outer")

    merged_df = merged_df.sort_values(by="distance")
    merged_df = merged_df.set_index("distance")

    # Interpolate missing values
    merged_df = merged_df.interpolate()
    dbs_df = merged_df.std(axis=1).abs()
    dbs_df = dbs_df.reset_index().rename(columns={"index": "distance"})
    dbs_df.columns = ["distance", "speed_variance"]

    return dbs_df


PEAK = "PEAK"
VALLEY = "VALLEY"


def get_peaks_and_valleys_sorted_tuple_list(lap: Lap):
    (
        peak_speed_data_x,
        peak_speed_data_y,
        valley_speed_data_x,
        valley_speed_data_y,
    ) = lap.get_speed_peaks_and_valleys()

    tuple_list = []

    tuple_list += zip(
        peak_speed_data_x, peak_speed_data_y, [PEAK] * len(peak_speed_data_x)
    )
    tuple_list += zip(
        valley_speed_data_x, valley_speed_data_y, [VALLEY] * len(valley_speed_data_x)
    )

    tuple_list.sort(key=lambda a: a[1])

    return tuple_list


def calculate_laps_left_on_fuel(current_lap, last_lap) -> float:
    # TODO Like F1: A) Benzingemisch -0.72 Bunden
    laps_left: float
    fuel_consumed_last_lap = last_lap.fuel_at_start - last_lap.fuel_at_end
    laps_left = current_lap.fuel - (last_lap.laps_to_go * fuel_consumed_last_lap)
