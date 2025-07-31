import unittest
import os
from unittest.mock import patch

from gt7dashboard.gt7helper import calculate_remaining_fuel, format_laps_to_table, \
    get_n_fastest_laps_within_percent_threshold_ignoring_replays, get_fuel_on_consumption_by_relative_fuel_levels, \
    seconds_to_lap_time, get_variance_for_laps, \
    get_median_lap, get_last_reference_median_lap, filter_max_min_laps, \
    get_peaks_and_valleys_sorted_tuple_list, calculate_laps_left_on_fuel

from gt7dashboard.gt7lap import Lap
from gt7dashboard.gt7car import get_car_name_for_car_id
from gt7dashboard.gt7lapstorage import get_safe_filename, save_laps_to_json, load_laps_from_json

class TestHelper(unittest.TestCase):
    def test_calculate_remaining_fuel(self):
        fuel_consumed_per_lap, laps_remaining, time_remaining = calculate_remaining_fuel(100, 80, 10000)
        self.assertEqual(fuel_consumed_per_lap, 20)
        self.assertEqual(laps_remaining, 4)
        self.assertEqual(time_remaining, 40000)

        fuel_consumed_per_lap, laps_remaining, time_remaining = calculate_remaining_fuel(20, 5, 100)
        self.assertEqual(fuel_consumed_per_lap, 15)
        self.assertLess(laps_remaining, 1)
        self.assertLess(time_remaining, 34)

        fuel_consumed_per_lap, laps_remaining, time_remaining = calculate_remaining_fuel(100, 100, 10000)
        self.assertEqual(fuel_consumed_per_lap, 0)
        self.assertEqual(laps_remaining, -1)
        self.assertEqual(time_remaining, -1)

    def test_get_fuel_on_consumption_by_relative_fuel_levels(self):
        fuel_lap = Lap()
        fuel_lap.fuel_at_start = 100
        fuel_lap.fuel_at_end = 50
        fuel_lap.lap_finish_time = 1000
        fuel_maps = get_fuel_on_consumption_by_relative_fuel_levels(fuel_lap)
        self.assertEqual(11, len(fuel_maps))
        print("\nFuelLvl	 Power%		    Fuel% Consum. LapsRem 	Time Rem Exp. Lap Time\n")
        for fuel_map in fuel_maps:
            print(fuel_map)

    def test_format_laps_to_table(self):
        lap1 = Lap()
        lap1.number = 1
        lap1.lap_finish_time = 11311000 / 1000
        lap1.fuel_at_end = 90
        lap1.full_throttle_ticks = 10000
        lap1.throttle_and_brake_ticks = 500
        lap1.full_brake_ticks = 10000
        lap1.no_throttle_and_no_brake_ticks = 50
        lap1.lap_ticks = 33333
        lap1.tyres_spinning_ticks = 260

        lap2 = Lap()
        lap2.number = 2
        lap2.lap_finish_time = 11110000 / 1000
        lap2.fuel_at_end = 44
        lap2.full_throttle_ticks = 100
        lap2.throttle_and_brake_ticks = 750
        lap2.full_brake_ticks = 1000
        lap2.no_throttle_and_no_brake_ticks = 40
        lap2.lap_ticks = 33333
        lap2.tyres_spinning_ticks = 240

        lap3 = Lap()
        lap3.number = 3
        lap3.lap_finish_time = 12114000 / 1000
        lap3.fuel_at_end = 34
        lap3.full_throttle_ticks = 100
        lap3.throttle_and_brake_ticks = 10
        lap3.full_brake_ticks = 1000
        lap3.no_throttle_and_no_brake_ticks = 100
        lap3.lap_ticks = 33333
        lap3.tyres_spinning_ticks = 120

        laps = [lap3, lap2, lap1]

        result = format_laps_to_table(laps, 11110000 / 1000)
        print("\n")
        print(result)
        self.assertEqual(len(result.split("\n")), len(laps) + 2)  # +2 for header and last line

    def test_calculate_time_diff_by_distance_from_pickle(self):
        path = os.path.join(os.getcwd(), 'test_data', 'broad_bean_raceway_time_trial_4laps.json')
        laps = load_laps_from_json(path)

        df = Lap.calculate_time_diff_by_distance(laps[0], laps[1])

        # Check for common length but also for columns to exist
        self.assertEqual(len(df.distance), len(df.comparison))
        self.assertEqual(len(df.distance), len(df.reference))

    def test_calculate_time_diff_by_distance(self):
        best_lap = Lap()
        best_lap.data_time = [0, 2, 6, 12, 22, 45, 60, 70]
        best_lap.data_speed = [0, 50, 55, 100, 120, 30, 20, 50]

        second_best_lap = Lap()
        second_best_lap.data_time = [0, 1, 4, 5, 20, 30, 70, 75]
        second_best_lap.data_speed = [0, 40, 35, 90, 85, 50, 20, 5]

        df = Lap.calculate_time_diff_by_distance(best_lap, second_best_lap)

        print(len(df))

    def test_convert_seconds_to_milliseconds(self):
        seconds = 10000
        ms = Lap.convert_seconds_to_milliseconds(seconds)
        s_s = seconds_to_lap_time(seconds / 1000)
        print(ms, s_s)


class TestLastReferenceMedian(unittest.TestCase):

    def setUp(self):
        self.l_fast = Lap()
        self.l_fast.lap_finish_time = 100
        self.l_fast.data_speed = [200]

        self.l_middle = Lap()
        self.l_middle.lap_finish_time = 200
        self.l_middle.data_speed = [150]

        self.l_slow = Lap()
        self.l_slow.lap_finish_time = 300
        self.l_slow.data_speed = [100]

        self.l_reference = Lap()
        self.l_reference.lap_finish_time = 90
        self.l_reference.data_speed = [300]

    def test_one_lap(self):
        last, reference, median = get_last_reference_median_lap([self.l_slow], None)
        self.assertEqual(self.l_slow, last)
        self.assertIsNone(reference)
        self.assertIsNone(median)

    def test_one_lap_with_reference(self):
        last, reference, median = get_last_reference_median_lap([self.l_fast], self.l_reference)
        self.assertEqual(self.l_fast, last)
        self.assertEqual(self.l_reference, reference)
        self.assertIsNone(median)

    def test_two_laps(self):
        last, reference, median = get_last_reference_median_lap([self.l_slow, self.l_fast], None)
        self.assertEqual(self.l_slow, last)
        self.assertEqual(self.l_fast, reference)
        self.assertIsNone(median, Lap)

    def test_two_laps_with_reference(self):
        last, reference, median = get_last_reference_median_lap([self.l_slow, self.l_fast], self.l_reference)
        self.assertEqual(self.l_slow, last)
        self.assertEqual(self.l_reference, reference)
        self.assertIsNone(median, Lap)

    def test_three_laps(self):
        last, reference, median = get_last_reference_median_lap([self.l_slow, self.l_fast, self.l_middle],
                                                                          None)
        self.assertEqual(self.l_slow, last)
        self.assertEqual(self.l_fast, reference)
        self.assertIsInstance(median, Lap)

    def test_two_three_with_reference(self):
        last, reference, median = get_last_reference_median_lap([self.l_slow, self.l_fast, self.l_middle],
                                                                          self.l_reference)
        self.assertEqual(self.l_slow, last)
        self.assertEqual(self.l_reference, reference)
        self.assertIsInstance(median, Lap)

    def test_fastest_is_latest(self):
        last, reference, median = get_last_reference_median_lap([self.l_fast, self.l_slow, self.l_middle],
                                                                          None)
        self.assertEqual(self.l_fast, last)
        self.assertEqual(self.l_fast, reference)
        self.assertIsInstance(median, Lap)

    def test_reference_slower_than_latest(self):
        last, reference, median = get_last_reference_median_lap(
            [self.l_reference, self.l_slow, self.l_middle], self.l_fast)
        self.assertEqual(self.l_reference, last)
        self.assertEqual(self.l_fast, reference)
        self.assertIsInstance(median, Lap)


class TestLaps(unittest.TestCase):
    def setUp(self):
        # Single Lap
        self.Lap = Lap()  # P1            #P2
        self.Lap.data_position_z = [0, 1, 3, 4, 7, 8, 9]  # Brake points are stored for x,y in z,x
        self.Lap.data_position_x = [0, 2, 5, 8, 9, 18, 19]

        self.Lap.data_braking = [0, 50, 40, 50, 0, 10, 0]

        # Set of Laps
        self.Laps = [Lap(), Lap(), Lap(), Lap()]
        self.Laps[0].lap_finish_time = 1000
        self.Laps[1].lap_finish_time = 1200
        self.Laps[2].lap_finish_time = 1250
        self.Laps[3].lap_finish_time = 1250

        self.Laps[0].data_throttle = [0, 50, 75, 100, 100, 100, 55, 0]
        self.Laps[1].data_throttle = [0, 25, 75, 98, 100, 0, 0, 0]

        self.Laps[0].data_braking = [2, 4, 0, -75, 10]  # has one more than the others
        self.Laps[1].data_braking = [4, 8, 0, -25, 10]  # has one more than the others
        self.Laps[2].data_braking = [8, 16, 0, -10]
        self.Laps[3].data_braking = [100, 100, 0, -20]

    def test_list_eq(self):
        """Will fail"""
        brake_points_x, brake_points_y = self.Lap.get_brake_points()
        # A break point will be the point after a zero for breaking
        self.assertListEqual(brake_points_x, [2, 18])
        self.assertListEqual(brake_points_y, [1, 8])

    def test_get_median_lap(self):
        median_lap = get_median_lap(self.Laps)
        self.assertEqual(len(median_lap.data_throttle), len(self.Laps[0].data_throttle))
        self.assertEqual(1225, median_lap.lap_finish_time)
        self.assertListEqual([0, 37.5, 75, 99, 100, 50, 27.5, 0], median_lap.data_throttle)
        # should contain the last 10, even though the other laps do not contain it
        self.assertListEqual([6, 12, 0, -22.5, 10], median_lap.data_braking)

        # with self.assertRaises(Exception) as context:
        #     get_median_lap([])
        #
        # self.assertTrue('This is broken' in context.exception)

    def test_filter_max_min_laps(self):
        laps = [Lap(), Lap(), Lap(), Lap()]
        laps[0].lap_finish_time = 1000  # best lap, should be in
        laps[1].lap_finish_time = 1200  # should be in
        laps[2].lap_finish_time = 1250  # should be in
        laps[3].lap_finish_time = 1275  # should be out
        laps[3].lap_finish_time = 400  # odd lap, should be out
        filtered_laps = filter_max_min_laps(laps, max_lap_time=1270, min_lap_time=600)
        self.assertEqual(3, len(filtered_laps))

    def test_find_speed_peaks_and_valleys(self):
        valleyLap = Lap()
        valleyLap.data_speed = [0, 2, 3, 5, 5, 4.5, 3, 6, 7, 8, 7, 8, 3, 2]
        peaks, valleys = valleyLap.find_speed_peaks_and_valleys(width=1)
        self.assertEqual([3, 9, 11], peaks)

    def test_find_speed_peaks_and_valleys_real_data(self):
        path = os.path.join(os.getcwd(), 'test_data', 'broad_bean_raceway_time_trial_4laps.json')
        laps = load_laps_from_json(path)

        peaks, valleys = laps[1].find_speed_peaks_and_valleys(width=100)

        self.assertEqual([759, 1437], peaks)
        self.assertEqual([1132, 1625], valleys)

    def test_get_car_name_for_car_id(self):
        car_name = get_car_name_for_car_id(1448)
        self.assertEqual("SILVIA spec-R Aero (S15) '02", car_name)

        non_existing_car_name = get_car_name_for_car_id(89239843984983)
        self.assertEqual(non_existing_car_name, "CAR-ID-89239843984983")

    def test_get_car_name_for_car_id_when_csv_file_does_not_exist(self):
        with patch('gt7dashboard.gt7car.CARS_CSV_FILENAME', 'not_existing_file'):
            car_name = get_car_name_for_car_id(1448)
            self.assertEqual(car_name, "CAR-ID-1448")

    def test_get_safe_filename(self):
        self.assertEqual("Cio_123_98", get_safe_filename("Cio 123 '98"))

    def test_get_n_fastest_laps_within_percent_threshold_ignoring_replays(self):
        l1 = Lap()
        l1.lap_finish_time = 1005  # second best

        l2 = Lap()
        l2.lap_finish_time = 1100  # dead last, is cut off

        l3 = Lap()
        l3.lap_finish_time = 500
        l3.is_replay = True  # Super quick but replay

        l4 = Lap()
        l4.lap_finish_time = 1000  # best

        l5 = Lap()
        l5.lap_finish_time = 5000  # Super slow

        l6 = Lap()
        l6.lap_finish_time = 1010  # second to last

        number_of_laps_to_get = 3
        filtered_laps = get_n_fastest_laps_within_percent_threshold_ignoring_replays([l1, l2, l3, l4, l5, l6],
                                                                                               number_of_laps_to_get,
                                                                                               0.15)
        self.assertEqual(number_of_laps_to_get, len(filtered_laps))

        self.assertEqual(1000, filtered_laps[0].lap_finish_time)
        self.assertEqual(1005, filtered_laps[1].lap_finish_time)
        self.assertEqual(1010, filtered_laps[2].lap_finish_time)

        threshold_percentage = 0.006
        tighter_filtered_laps = get_n_fastest_laps_within_percent_threshold_ignoring_replays(
            [l1, l2, l3, l4, l5, l6], number_of_laps_to_get, percent_threshold=threshold_percentage)

        # Should only contain 1000 and 1005 within 0,6% difference
        self.assertEqual(2, len(tighter_filtered_laps))


    def test_get_variance_for_fastest_laps(self):
        l1 = Lap()
        l1.data_speed = [50, 100, 110, 120]
        l1.data_time =  [10, 100,200,300]

        l2 = Lap()
        l2.data_speed = [50, 200, 300, 400]
        l2.data_time =  [10, 100,200,300]

        l3 = Lap()
        l3.data_speed = [50, 150, 200, 200]
        l3.data_time =  [10, 100,200,300]

        variance = get_variance_for_laps([l1, l2, l3])
        print("")
        print(variance)

    def test_get_n_fastest_laps_within_percent_threshold_ignoring_replays(self):
        empty_lap = Lap()
        empty_lap.data_speed = []
        empty_lap.data_time =  []

        l3 = Lap()
        l3.data_speed = [50, 150, 200, 200]
        l3.data_time =  [10, 100,200,300]

        laps = [
            empty_lap, l3
        ]

        filtered_laps = get_n_fastest_laps_within_percent_threshold_ignoring_replays(laps, number_of_laps=999, percent_threshold=1)
        self.assertEqual(1, len(filtered_laps))
        self.assertEqual([l3], filtered_laps)

    def get_test_laps(self):
        path = os.path.join(
            os.getcwd(), "test_data", "broad_bean_raceway_time_trial_4laps.json"
        )
        test_laps = load_laps_from_json(path)

        return test_laps
    def test_get_peaks_and_valleys_sorted_tuple_list(self):
        test_laps = self.get_test_laps()

        tuple_list = get_peaks_and_valleys_sorted_tuple_list(test_laps[3])
        print(tuple_list)

    @unittest.skip("Not yet implemented")
    def test_calculate_fuel_left(self):
        lap = Lap()
        fuel_left = calculate_laps_left_on_fuel(lap, lap)
        print(fuel_left)

    def test_save_laps_to_json(self):
        l1 = Lap()
        l1.data_boost = [0.6, 0.7, 0.9]
        l2 = Lap()
        l2.data_boost = [2.6, 2.7, 3.9]

        laps = [l1, l2]
        json_path = save_laps_to_json(laps)
        print(json_path)

        laps_read = load_laps_from_json(json_path)

        self.assertEqual(len(laps), len(laps_read))
        for obj1, obj2 in zip(laps, laps_read):
            self.assertEqual(obj1.__dict__, obj2.__dict__)
