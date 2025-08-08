import os
import logging
import time

from bokeh.plotting import curdoc
from bokeh.plotting import figure
from bokeh.layouts import row, column
from bokeh.models import (
    Div,
    Button,
    Select,
    CheckboxGroup,
    ColumnDataSource,
    Paragraph,
    ImportedStyleSheet,
)

from bokeh.models.dom import HTML

from gt7dashboard.gt7helper import (
    bokeh_tuple_for_list_of_laps,
    bokeh_tuple_for_list_of_lapfiles,
    get_last_reference_median_lap,
)

from gt7dashboard.gt7lap import Lap
from gt7dashboard.gt7diagrams import get_speed_peak_and_valley_diagram
from gt7dashboard.gt7help import (
    THROTTLE_DIAGRAM,
    SPEED_VARIANCE,
    RACE_LINE_MINI,
    SPEED_PEAKS_AND_VALLEYS,
    SPEED_DIAGRAM,
    TIME_DIFF,
    BRAKING_DIAGRAM,
    YAW_RATE_DIAGRAM,
    COASTING_DIAGRAM,
    TIRE_DIAGRAM,
)
from gt7dashboard.colors import (
    LAST_LAP_COLOR,
    REFERENCE_LAP_COLOR,
    MEDIAN_LAP_COLOR,
    TABLE_ROW_COLORS,
)
from .GT7Tab import GT7Tab
from gt7dashboard.gt7racediagram import RaceDiagram
from gt7dashboard.gt7car import car_name

from gt7dashboard.gt7lapstorage import (
    save_laps_to_json,
    load_laps_from_json,
    list_lap_files_from_path,
)
from gt7dashboard.datatable.deviance_laps import deviance_laps_datatable
from gt7dashboard.datatable.speed_peak_valley import SpeedPeakValleyDataTable
from .GT7Tab import GT7Tab
from gt7dashboard.gt7help import get_help_div

# Use LAST_LAP_COLOR wherever needed

logger = logging.getLogger("race_tab")
logger.setLevel(logging.DEBUG)


class RaceTab(GT7Tab):
    """Main telemetry tab (Get Faster) for GT7 Dashboard"""

    def __init__(self, app_instance):
        """Initialize the race telemetry tab"""
        super().__init__("Get Faster")
        self.app = app_instance

        # Create race line figure
        race_line_tooltips = [("index", "$index"), ("Brakepoint", "")]
        race_line_width = 250

        self.s_race_line = figure(
            title="Race Line",
            x_axis_label="x",
            y_axis_label="z",
            match_aspect=True,
            width=race_line_width,
            height=race_line_width,
            active_drag="box_zoom",
            tooltips=race_line_tooltips,
        )
        # We set this to true, since maps appear flipped in the game
        # compared to their actual coordinates
        self.s_race_line.y_range.flipped = True
        self.s_race_line.toolbar.autohide = True

        # State variables
        # self.laps_stored = []
        self.reference_lap_selected = None
        self.telemetry_update_needed = False

        # self.tyre_temp_display = self.create_tyre_temp_display()

        self.race_diagram = RaceDiagram(width=1000)

        # Create components and layout
        self.create_components()
        self.finalize_layout()

        # Initialize available lap files
        stored_lap_files = bokeh_tuple_for_list_of_lapfiles(
            list_lap_files_from_path(os.path.join(os.getcwd(), "data"))
        )
        self.selectLoadLaps.options = stored_lap_files

    def create_components(self):
        """Create all UI components for this tab"""

        dtstylesheet = ImportedStyleSheet(url="gt7dashboard/static/css/styles.css")

        self.speed_peak_valley_datatable = SpeedPeakValleyDataTable(self.app)

        # Create buttons
        self.manual_log_button = Button(
            label="Log Lap Now", width=150, button_type="primary"
        )

        self.header_line = Div(
            text="Last Lap: None<br>Reference Lap: None",
            width=400,
            height=50,
        )

        self.save_button = Button(label="Save Laps", width=150, button_type="success")
        self.reset_button = Button(label="Reset Laps", width=150, button_type="danger")

        # Create selects
        self.selectLoadLapsTitle = Paragraph(text="Load Laps:")
        self.selectLoadLaps = Select(value="laps", options=[], width=150)
        self.selectreferenceLapTitle = Paragraph(text="Reference Lap:")
        self.reference_lap_select = Select(value="-1", width=150)

        # Create checkbox for recording replays
        self.checkbox_group = CheckboxGroup(labels=["Record Replays"], active=[1])

        # Connect event handlers
        self.manual_log_button.on_click(self.log_lap_button_handler)
        self.save_button.on_click(self.save_button_handler)
        self.reset_button.on_click(self.reset_button_handler)
        self.selectLoadLaps.on_change("value", self.load_laps_handler)
        self.reference_lap_select.on_change("value", self.load_reference_lap_handler)
        self.checkbox_group.on_change("active", self.always_record_checkbox_handler)

        self.app.gt7comm.set_lap_callback(self.on_lap_finished)

        self.deviance_laps_datatable = deviance_laps_datatable()

        # Set up race line components if they haven't been created yet
        if self.s_race_line and not hasattr(self, "last_lap_race_line"):
            # Create race lines if needed
            self.last_lap_race_line = self.s_race_line.line(
                x="raceline_x",
                y="raceline_z",
                legend_label="Last Lap",
                line_width=1,
                color="cyan",
                source=ColumnDataSource(data={"raceline_x": [], "raceline_z": []}),
            )

            self.reference_lap_race_line = self.s_race_line.line(
                x="raceline_x",
                y="raceline_z",
                legend_label="Reference Lap",
                line_width=1,
                color="magenta",
                source=ColumnDataSource(data={"raceline_x": [], "raceline_z": []}),
            )

    def connect_callbacks(self):
        """Connect callbacks after all tabs are initialized"""
        if hasattr(self.app.tab_manager, "racetime_datatable_tab"):
            self.app.tab_manager.racetime_datatable_tab.race_time_datatable.lap_times_source.selected.on_change(
                "indices", self.table_row_selection_callback
            )
        else:
            logger.warning(
                "racetime_datatable_tab not available for callback connection"
            )

    def finalize_layout(self):
        """Create the final layout after all diagrams are set"""
        if not self.race_diagram:
            logger.error("Can't finalize layout - diagrams not set")
            return

        # Create and get diviance laps div
        self.div_deviance_laps_on_display = Div(width=200, text="3 Fastest Lap Times")
        speedpeaksandvalleys_help_button = get_help_div(SPEED_PEAKS_AND_VALLEYS)

        left_column = column(
            [
                self.save_button,
                self.reset_button,
                self.manual_log_button,
                self.checkbox_group,
                self.selectLoadLapsTitle,
                self.selectLoadLaps,
                self.selectreferenceLapTitle,
                self.reference_lap_select,
                self.div_deviance_laps_on_display,
                self.deviance_laps_datatable.dt_lap_times,
                speedpeaksandvalleys_help_button,
                self.speed_peak_valley_datatable.datatable,
                self.s_race_line,
            ],
        )
        speed_help = get_help_div(SPEED_DIAGRAM)
        throttle_help = get_help_div(THROTTLE_DIAGRAM)
        speedvar_help = get_help_div(SPEED_VARIANCE)
        timediff_help = get_help_div(TIME_DIFF)
        braking_help = get_help_div(BRAKING_DIAGRAM)
        yawrate_help = get_help_div(YAW_RATE_DIAGRAM)
        coasting_help = get_help_div(COASTING_DIAGRAM)
        tyre_help = get_help_div(TIRE_DIAGRAM)

        main_diagrams_column = column(
            row([self.header_line]),
            row([self.race_diagram.f_time_diff, timediff_help]),
            row([self.race_diagram.f_speed, speed_help]),
            row([self.race_diagram.f_speed_variance, speedvar_help]),
            row([self.race_diagram.f_throttle, throttle_help]),
            row([self.race_diagram.f_braking, braking_help]),
            row([self.race_diagram.f_yaw_rate, yawrate_help]),
            row([self.race_diagram.f_coasting, coasting_help]),
            row([self.race_diagram.f_gear]),
            row([self.race_diagram.f_rpm]),
            row([self.race_diagram.f_boost]),
            row([self.race_diagram.f_tyres, tyre_help]),
        )

        self.layout = row(left_column, main_diagrams_column)
        return self.layout

    def update_reference_lap_select(self, laps):
        """Update the reference lap selection dropdown"""
        self.reference_lap_select.options = [
            tuple(("-1", "Best Lap"))
        ] + bokeh_tuple_for_list_of_laps(laps)

    def update_header_line(self, last_lap, reference_lap):
        """Update the header line with lap information"""
        if not last_lap:
            new_text = "Last Lap: None<br>Reference Lap: None"
        else:
            last_lap_info = f"{last_lap.title} ({car_name(last_lap.car_id)})"

            if reference_lap:
                reference_lap_info = (
                    f"{reference_lap.title} ({car_name(reference_lap.car_id)})"
                )
            else:
                reference_lap_info = "None"

            new_text = (
                f"Last Lap: {last_lap_info}<br>Reference Lap: {reference_lap_info}"
            )

        # Use callback to ensure update happens in correct context
        def _update_text():
            self.header_line.text = new_text
            logger.debug(f"Header line updated via callback: [{new_text}]")

        curdoc().add_next_tick_callback(_update_text)

    # def update_tuning_info(self):
    #     """Update tuning information display"""
    #     self.div_tuning_info.text = """<h4>Tuning Info</h4>
    #     <p>Max Speed: <b>%d</b> kph</p>
    #     <p>Min Body Height: <b>%d</b> mm</p>""" % (
    #         self.app.gt7comm.session.max_speed,
    #         self.app.gt7comm.session.min_body_height,
    #     )

    def reset_button_handler(self, event):
        """Reset all data and graphs"""
        logger.info("Reset button clicked - clearing all data and graphs")

        # Clear race diagram data
        self.race_diagram.delete_all_additional_laps()

        # Clear data sources for main graphs
        self.race_diagram.source_last_lap.data = {
            "distance": [],
            "speed": [],
            "throttle": [],
            "brake": [],
            "time": [],
        }
        self.race_diagram.source_reference_lap.data = {
            "distance": [],
            "speed": [],
            "throttle": [],
            "brake": [],
            "time": [],
        }
        self.race_diagram.source_median_lap.data = {
            "distance": [],
            "speed": [],
            "throttle": [],
            "brake": [],
            "time": [],
        }
        self.race_diagram.source_time_diff.data = {"distance": [], "time_diff": []}

        # Clear race line visualization
        if hasattr(self, "last_lap_race_line") and self.last_lap_race_line:
            self.last_lap_race_line.data_source.data = {
                "raceline_x": [],
                "raceline_z": [],
            }
        if hasattr(self, "reference_lap_race_line") and self.reference_lap_race_line:
            self.reference_lap_race_line.data_source.data = {
                "raceline_x": [],
                "raceline_z": [],
            }

        # Reset race time table
        # self.race_time_table.lap_times_source.data = {"index": [], "car": [], "time": [], "number": [], "title": []}
        # self.race_time_table.lap_times_source.selected.indices = []

        # Clear information displays
        self.update_header_line(None, None)
        self.div_speed_peak_valley_diagram.text = ""

        # Reset reference lap selection
        self.reference_lap_selected = None
        self.reference_lap_select.value = "-1"  # Best Lap option
        self.reference_lap_select.options = []

        # Clear GT7 communication data
        self.app.gt7comm.reset()

        # Force full UI update
        self.telemetry_update_needed = True

        self.speed_peak_valley_datatable.update_speed_peak_valley_data(None, None)

        logger.info("Reset complete - all graphs and data cleared")

    def always_record_checkbox_handler(self, event, old, new):
        """Handle record replays checkbox change"""
        if len(new) == 2:
            logger.info("Set always record data to True")
            self.app.gt7comm.always_record_data = True
        else:
            logger.info("Set always record data to False")
            self.app.gt7comm.always_record_data = False

    def log_lap_button_handler(self, event):
        """Handle manual lap logging"""
        self.app.gt7comm.finish_lap(manual=True)
        logger.info(
            "Added a lap manually to the list of laps: %s"
            % self.app.gt7comm.session.laps[0]
        )

    def save_button_handler(self, event):
        """Handle saving laps"""
        if len(self.app.gt7comm.session.laps) > 0:
            path = save_laps_to_json(self.app.gt7comm.session.laps)
            logger.info(
                "Saved %d laps as %s" % (len(self.app.gt7comm.session.laps), path)
            )

    def load_laps_handler(self, attr, old, new):
        """Handle loading laps from file"""
        if new == "":
            return

        logger.info("Loading laps from file %s" % new)
        self.race_diagram.delete_all_additional_laps()
        self.app.gt7comm.session.load_laps(
            load_laps_from_json(new), replace_other_laps=True
        )
        self.update_reference_lap_select(self.app.gt7comm.session.get_laps())

    def load_reference_lap_handler(self, attr, old, new):
        """Handle changing the reference lap"""
        if int(new) == -1:
            # Set no reference lap
            self.reference_lap_selected = None
            logger.info("No reference lap selected new is -1")
        else:
            self.reference_lap_selected = self.app.gt7comm.session.laps[int(new)]
            logger.info(
                "Loading %s as reference"
                % self.app.gt7comm.session.laps[int(new)].format()
            )

        self.telemetry_update_needed = True
        self.update_lap_change()

    def table_row_selection_callback(self, attrname, old, new):
        """Handle selecting rows in the lap times table"""
        selectionIndex = (
            self.app.tab_manager.racetime_datatable_tab.race_time_datatable.lap_times_source.selected.indices
        )
        logger.info("You have selected the row nr " + str(selectionIndex))

        colors_index = (
            len(self.race_diagram.sources_additional_laps)
            + self.race_diagram.number_of_default_laps
        )

        for index in selectionIndex:
            if index >= len(TABLE_ROW_COLORS):
                colors_index = 0

            color = TABLE_ROW_COLORS[colors_index]
            colors_index += 1
            lap_to_add = self.app.gt7comm.session.laps[index]
            new_lap_data_source = self.race_diagram.add_lap_to_race_diagram(
                color, legend=self.app.gt7comm.session.laps[index].title, visible=True
            )
            new_lap_data_source.data = lap_to_add.get_data_dict()

    def update_speed_velocity_graph(self, laps):
        """Update the speed velocity graphs"""

        last_lap, reference_lap, median_lap = get_last_reference_median_lap(
            laps, reference_lap_selected=self.reference_lap_selected
        )

        if last_lap:
            last_lap_data = last_lap.get_data_dict()
            self.race_diagram.source_last_lap.data = last_lap_data
            self.last_lap_race_line.data_source.data = last_lap_data

            if reference_lap and len(reference_lap.data_speed) > 0:
                reference_lap_data = reference_lap.get_data_dict()
                self.race_diagram.source_time_diff.data = (
                    Lap.calculate_time_diff_by_distance(reference_lap, last_lap)
                )
                self.race_diagram.source_reference_lap.data = reference_lap_data
                self.reference_lap_race_line.data_source.data = reference_lap_data

        if median_lap:
            self.race_diagram.source_median_lap.data = median_lap.get_data_dict()

        self.s_race_line.legend.visible = False
        self.s_race_line.axis.visible = False

        fastest_laps = self.race_diagram.update_fastest_laps_variance(laps)
        logger.info("Updating Speed Deviance with %d fastest laps" % len(fastest_laps))

        self.deviance_laps_datatable.lap_times_source.data = {
            "number": [lap.number for lap in fastest_laps],
            "title": [lap.title for lap in fastest_laps],
        }

        # Update brakepoints
        brake_points_enabled = os.environ.get("GT7_ADD_BRAKEPOINTS") == "true"

        if brake_points_enabled and len(last_lap.data_braking) > 0:
            self.update_brake_points(last_lap, self.s_race_line, LAST_LAP_COLOR)

        if brake_points_enabled and len(reference_lap.data_braking) > 0:
            self.update_brake_points(
                reference_lap, self.s_race_line, REFERENCE_LAP_COLOR
            )

    def update_brake_points(self, lap, race_line, color):
        """Update brake points on race line"""
        brake_points_x, brake_points_y = lap.get_brake_points()

        for i, _ in enumerate(brake_points_x):
            race_line.scatter(
                brake_points_x[i],
                brake_points_y[i],
                marker="circle",
                size=10,
                fill_color=color,
            )

    def update_lap_change(self):
        """Update the display when laps change"""

        update_start_time = time.time()
        laps = self.app.gt7comm.session.get_laps()

        if not self.telemetry_update_needed:
            return

        logger.info("update_lap_change laps")

        if laps is not None and len(laps) > 0:
            # Get all three laps (last, reference, median) at once
            last_lap, reference_lap, median_lap = get_last_reference_median_lap(
                laps, reference_lap_selected=self.reference_lap_selected
            )

            if len(laps) > 1 and reference_lap:
                self.speed_peak_valley_datatable.update_speed_peak_valley_data(
                    last_lap, reference_lap
                )
            else:
                self.speed_peak_valley_datatable.update_speed_peak_valley_data(
                    last_lap, None
                )

            logger.info("Updating of %d laps" % len(laps))

            start_time = time.time()
            self.update_speed_velocity_graph(laps)
            logger.debug(
                "Updating speed velocity graph took %dms"
                % ((time.time() - start_time) * 1000)
            )

            logger.debug(
                "End of updating laps, whole Update took %dms"
                % ((time.time() - update_start_time) * 1000)
            )
            self.update_header_line(last_lap, reference_lap)
            self.telemetry_update_needed = False
        else:
            # Handle case when no laps exist
            self.update_header_line(None, None)
            self.speed_peak_valley_datatable.update_speed_peak_valley_data(None, None)

        self.app.tab_manager.race_lines_tab.update_race_lines(laps, reference_lap)

    def create_tyre_temp_display(self):
        """Create a display for tyre temperatures."""
        self.tyre_temp_FL = Div(text="FL: -- °C", width=80)
        self.tyre_temp_FR = Div(text="FR: -- °C", width=80)
        self.tyre_temp_RL = Div(text="RL: -- °C", width=80)
        self.tyre_temp_RR = Div(text="RR: -- °C", width=80)
        return row(
            Div(text="<b>Tyre Temps:</b>", width=100),
            self.tyre_temp_FL,
            self.tyre_temp_FR,
            self.tyre_temp_RL,
            self.tyre_temp_RR,
            css_classes=["tyre-temp-row"],
        )

    def update_tyre_temp_display(self, lap):
        """Update the tyre temperature display with values from the finished lap."""
        self.tyre_temp_FL.text = f"FL: {getattr(lap, 'tyre_temp_FL', '--'):.1f} °C"
        self.tyre_temp_FR.text = f"FR: {getattr(lap, 'tyre_temp_FR', '--'):.1f} °C"
        self.tyre_temp_RL.text = f"RL: {getattr(lap, 'tyre_temp_RL', '--'):.1f} °C"
        self.tyre_temp_RR.text = f"RR: {getattr(lap, 'tyre_temp_RR', '--'):.1f} °C"

    def on_lap_finished(self, lap):
        self.update_tyre_temp_display(lap)
        self.update_lap_change(lap)
        self.update_reference_lap_select(self.app.gt7comm.session.get_laps())
