from typing import List
from bokeh.layouts import layout
from bokeh.models import ColumnDataSource, Range1d, Span
from bokeh.plotting import figure

from gt7dashboard import gt7helper
from gt7dashboard.gt7lap import Lap
from gt7dashboard.colors import LAST_LAP_COLOR, REFERENCE_LAP_COLOR, MEDIAN_LAP_COLOR

class RaceDiagram(object):
    def __init__(self, width=400):
        self.speed_lines = []
        self.braking_lines = []
        self.coasting_lines = []
        self.throttle_lines = []
        self.tyres_lines = []
        self.rpm_lines = []
        self.gears_lines = []
        self.boost_lines = []
        self.yaw_rate_lines = []

        self.source_time_diff = None
        self.source_speed_variance = None
        self.source_last_lap = None
        self.source_reference_lap = None
        self.source_median_lap = None
        self.sources_additional_laps = []

        self.additional_laps = List[Lap]
        self.number_of_default_laps = 3

        tooltips = [
            ("index", "$index"),
            ("value", "$y"),
            ("Speed", "@speed{0}"),
            ("Yaw Rate", "@yaw_rate{0.00}"),
            ("Throttle", "@throttle%"),
            ("Brake", "@brake%"),
            ("Coast", "@coast%"),
            ("Gear", "@gear"),
            ("Rev", "@rpm{0} RPM"),
            ("Distance", "@distance{0} m"),
            ("Boost", "@boost{0.00} x 100 kPa"),
        ]

        tooltips_timedelta = [
            ("index", "$index"),
            ("timedelta", "@timedelta{0} ms"),
            ("reference", "@reference{0} ms"),
            ("comparison", "@comparison{0} ms"),
        ]

        self.tooltips_speed_variance = [
            ("index", "$index"),
            ("Distance", "@distance{0} m"),
            ("Spd. Deviation", "@speed_variance{0}"),
        ]

        self.f_speed = figure(
            title="Last, Reference, Median",
            y_axis_label="Speed",
            width=width,
            height=250,
            tooltips=tooltips,
            active_drag="box_zoom",
        )

        self.f_speed_variance = figure(
            y_axis_label="Spd.Dev.",
            x_range=self.f_speed.x_range,
            y_range=Range1d(0, 50),
            width=width,
            height=int(self.f_speed.height / 4),
            tooltips=self.tooltips_speed_variance,
            active_drag="box_zoom",
        )

        self.f_time_diff = figure(
            title="Time Diff - Last, Reference",
            x_range=self.f_speed.x_range,
            y_axis_label="Time / Diff",
            width=width,
            height=int(self.f_speed.height / 2),
            tooltips=tooltips_timedelta,
            active_drag="box_zoom",
        )

        self.f_throttle = figure(
            x_range=self.f_speed.x_range,
            y_axis_label="Throttle",
            width=width,
            height=int(self.f_speed.height / 2),
            tooltips=tooltips,
            active_drag="box_zoom",
        )
        self.f_braking = figure(
            x_range=self.f_speed.x_range,
            y_axis_label="Braking",
            width=width,
            height=int(self.f_speed.height / 2),
            tooltips=tooltips,
            active_drag="box_zoom",
        )

        self.f_coasting = figure(
            x_range=self.f_speed.x_range,
            y_axis_label="Coasting",
            width=width,
            height=int(self.f_speed.height / 2),
            tooltips=tooltips,
            active_drag="box_zoom",
        )

        self.f_tyres = figure(
            x_range=self.f_speed.x_range,
            y_axis_label="Tire Spd / Car Spd",
            width=width,
            height=int(self.f_speed.height / 2),
            tooltips=tooltips,
            active_drag="box_zoom",
        )

        self.f_rpm = figure(
            x_range=self.f_speed.x_range,
            y_axis_label="RPM",
            width=width,
            height=int(self.f_speed.height / 2),
            tooltips=tooltips,
            active_drag="box_zoom",
        )

        self.f_gear = figure(
            x_range=self.f_speed.x_range,
            y_axis_label="Gear",
            width=width,
            height=int(self.f_speed.height / 2),
            tooltips=tooltips,
            active_drag="box_zoom",
        )

        self.f_boost = figure(
            x_range=self.f_speed.x_range,
            y_axis_label="Boost",
            width=width,
            height=int(self.f_speed.height / 2),
            tooltips=tooltips,
            active_drag="box_zoom",
        )

        self.f_yaw_rate = figure(
            x_range=self.f_speed.x_range,
            y_axis_label="Yaw Rate / s",
            width=width,
            height=int(self.f_speed.height / 2),
            tooltips=tooltips,
            active_drag="box_zoom",
        )

        self.f_speed.toolbar.autohide = True

        span_zero_time_diff = Span(
            location=0,
            dimension="width",
            line_color="white",
            line_dash="dashed",
            line_width=1,
        )
        self.f_time_diff.add_layout(span_zero_time_diff)

        self.f_time_diff.toolbar.autohide = True

        self.f_speed_variance.xaxis.visible = False
        self.f_speed_variance.toolbar.autohide = True

        self.f_throttle.xaxis.visible = False
        self.f_throttle.toolbar.autohide = True

        self.f_braking.xaxis.visible = False
        self.f_braking.toolbar.autohide = True

        self.f_coasting.xaxis.visible = False
        self.f_coasting.toolbar.autohide = True

        self.f_tyres.xaxis.visible = False
        self.f_tyres.toolbar.autohide = True

        self.f_gear.xaxis.visible = False
        self.f_gear.toolbar.autohide = True

        self.f_rpm.xaxis.visible = False
        self.f_rpm.toolbar.autohide = True

        self.f_boost.xaxis.visible = False
        self.f_boost.toolbar.autohide = True

        self.f_yaw_rate.xaxis.visible = False
        self.f_yaw_rate.toolbar.autohide = True

        self.source_time_diff = ColumnDataSource(data={"distance": [], "timedelta": []})
        self.f_time_diff.line(
            x="distance",
            y="timedelta",
            source=self.source_time_diff,
            line_width=1,
            color="cyan",
            line_alpha=1,
        )

        self.source_last_lap = self.add_lap_to_race_diagram(LAST_LAP_COLOR, "Last Lap", True)
        self.source_reference_lap = self.add_lap_to_race_diagram(REFERENCE_LAP_COLOR, "Reference Lap", True)
        self.source_median_lap = self.add_lap_to_race_diagram(MEDIAN_LAP_COLOR, "Median Lap", False)

        legend_click_policy = "hide"

        self.f_speed.legend.click_policy = legend_click_policy
        self.f_throttle.legend.click_policy = legend_click_policy
        self.f_braking.legend.click_policy = legend_click_policy
        self.f_coasting.legend.click_policy = legend_click_policy
        self.f_tyres.legend.click_policy = legend_click_policy
        self.f_gear.legend.click_policy = legend_click_policy
        self.f_rpm.legend.click_policy = legend_click_policy
        self.f_boost.legend.click_policy = legend_click_policy
        self.f_yaw_rate.legend.click_policy = legend_click_policy

        min_border_left = 60
        self.f_time_diff.min_border_left = min_border_left
        self.f_speed.min_border_left = min_border_left
        self.f_throttle.min_border_left = min_border_left
        self.f_braking.min_border_left = min_border_left
        self.f_coasting.min_border_left = min_border_left
        self.f_tyres.min_border_left = min_border_left
        self.f_gear.min_border_left = min_border_left
        self.f_rpm.min_border_left = min_border_left
        self.f_speed_variance.min_border_left = min_border_left
        self.f_boost.min_border_left = min_border_left
        self.f_yaw_rate.min_border_left = min_border_left

        self.layout = layout(
            self.f_time_diff, self.f_speed, self.f_speed_variance, self.f_throttle,
            self.f_yaw_rate, self.f_braking, self.f_coasting, self.f_tyres,
            self.f_gear, self.f_rpm, self.f_boost
        )

        self.source_speed_variance = ColumnDataSource(data={"distance": [], "speed_variance": []})

        self.f_speed_variance.line(
            x="distance",
            y="speed_variance",
            source=self.source_speed_variance,
            line_width=1,
            color="gray",
            line_alpha=1,
            visible=True
        )

    def add_additional_lap_to_race_diagram(self, color: str, lap: Lap, visible: bool = True):
        source = self.add_lap_to_race_diagram(color, lap.title, visible)
        source.data = lap.get_data_dict()
        self.sources_additional_laps.append(source)

    def update_fastest_laps_variance(self, laps):
        variance, fastest_laps = gt7helper.get_variance_for_fastest_laps(laps)
        self.source_speed_variance.data = variance
        return fastest_laps

    def add_lap_to_race_diagram(self, color: str, legend: str, visible: bool = True):
        dummy_data = Lap().get_data_dict()
        source = ColumnDataSource(data=dummy_data)

        self.speed_lines.append(self.f_speed.line(
            x="distance",
            y="speed",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
            visible=visible
        ))

        self.throttle_lines.append(self.f_throttle.line(
            x="distance",
            y="throttle",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
            visible=visible
        ))

        self.braking_lines.append(self.f_braking.line(
            x="distance",
            y="brake",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
            visible=visible
        ))

        self.coasting_lines.append(self.f_coasting.line(
            x="distance",
            y="coast",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
            visible=visible
        ))

        self.tyres_lines.append(self.f_tyres.line(
            x="distance",
            y="tyres",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
            visible=visible
        ))

        self.gears_lines.append(self.f_gear.line(
            x="distance",
            y="gear",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
            visible=visible
        ))

        self.rpm_lines.append(self.f_rpm.line(
            x="distance",
            y="rpm",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
            visible=visible
        ))

        self.boost_lines.append(self.f_boost.line(
            x="distance",
            y="boost",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
            visible=visible
        ))

        self.yaw_rate_lines.append(self.f_yaw_rate.line(
            x="distance",
            y="yaw_rate",
            source=source,
            legend_label=legend,
            line_width=1,
            color=color,
            line_alpha=1,
            visible=visible
        ))

        return source

    def get_layout(self):
        return self.layout

    def delete_all_additional_laps(self):
        self.sources_additional_laps = []
        for i, _ in enumerate(self.f_speed.renderers):
            if i >= self.number_of_default_laps:
                self.f_speed.renderers.remove(self.f_speed.renderers[i])
                self.f_throttle.renderers.remove(self.f_throttle.renderers[i])
                self.f_braking.renderers.remove(self.f_braking.renderers[i])
                self.f_coasting.renderers.remove(self.f_coasting.renderers[i])
                self.f_tyres.renderers.remove(self.f_tyres.renderers[i])
                self.f_boost.renderers.remove(self.f_boost.renderers[i])
                self.f_yaw_rate.renderers.remove(self.f_yaw_rate.renderers[i])
                self.f_speed.legend.items.pop(i)
                self.f_throttle.legend.items.pop(i)
                self.f_braking.legend.items.pop(i)
                self.f_coasting.legend.items.pop(i)
                self.f_tyres.legend.items.pop(i)
                self.f_yaw_rate.legend.items.pop(i)
                self.f_boost.legend.items.pop(i)