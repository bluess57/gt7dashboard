from gt7dashboard import gt7helper


class FuelMap:
    """A Fuel Map with calculated attributes of the fuel setting

    Attributes:
            fuel_consumed_per_lap   The amount of fuel consumed per lap with this fuel map
    """

    def __init__(self, mixture_setting, power_percentage, consumption_percentage):
        """
        Create a Fuel Map that is relative to the base setting

        :param mixture_setting: Mixture Setting of the Fuel Map
        :param power_percentage: Percentage of available power to the car relative to the base setting
        :param consumption_percentage: Percentage of fuel consumption relative to the base setting
        """
        self.mixture_setting = mixture_setting
        self.power_percentage = power_percentage
        self.consumption_percentage = consumption_percentage

        self.fuel_consumed_per_lap = 0
        self.laps_remaining_on_current_fuel = 0
        self.time_remaining_on_current_fuel = 0
        self.lap_time_diff = 0
        self.lap_time_expected = 0

    def __str__(self):
        return "%d\t\t %d%%\t\t\t %d%%\t%d\t%.1f\t%s\t%s" % (
            self.mixture_setting,
            self.power_percentage * 100,
            self.consumption_percentage * 100,
            self.fuel_consumed_per_lap,
            self.laps_remaining_on_current_fuel,
            gt7helper.seconds_to_lap_time(self.time_remaining_on_current_fuel / 1000),
            gt7helper.seconds_to_lap_time(self.lap_time_diff / 1000),
        )
