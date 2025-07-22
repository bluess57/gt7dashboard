import os
import logging
import copy
import time
import html
import itertools
from typing import List

from bokeh.layouts import layout, row
from bokeh.models import (
    Div, Button, Select, CheckboxGroup, ColumnDataSource,
    Paragraph, TabPanel,
    InlineStyleSheet
)
from bokeh.palettes import Plasma11 as palette

from gt7dashboard.gt7helper import (
    bokeh_tuple_for_list_of_laps,
    bokeh_tuple_for_list_of_lapfiles,
    save_laps_to_json,
    load_laps_from_json,
    list_lap_files_from_path,
    get_brake_points,
    get_last_reference_median_lap,
    get_brake_points,
    calculate_time_diff_by_distance
    )

from gt7dashboard.gt7lap import Lap
from gt7dashboard.gt7diagrams import get_speed_peak_and_valley_diagram
from gt7dashboard.colors import LAST_LAP_COLOR, REFERENCE_LAP_COLOR, MEDIAN_LAP_COLOR

# Use LAST_LAP_COLOR wherever needed

logger = logging.getLogger('race_tab')
logger.setLevel(logging.DEBUG)

class RaceTab:
    """Main telemetry tab (Get Faster) for GT7 Dashboard"""
    
    def __init__(self, app_instance):
        """Initialize the race telemetry tab"""
        self.app = app_instance
        self.race_diagram = None  # Will be set by tab_manager
        #self.race_time_table = None  # Will be set by tab_manager
        self.s_race_line = None  # Will be set by tab_manager
        
        # State variables
        self.laps_stored = []
        self.reference_lap_selected = None
        self.telemetry_update_needed = False
        
        self.tyre_temp_display = self.create_tyre_temp_display()

        # Create components and layout
        self.create_components()
        self.layout = self.create_layout()
        
    def set_diagrams(self, race_diagram, s_race_line):
        """Set diagram components that are shared across tabs"""
        self.race_diagram = race_diagram
        self.s_race_line = s_race_line
        
        # Connect race time table selection callback
        # TODO:
        # self.race_time_table.lap_times_source.selected.on_change('indices', self.table_row_selection_callback)
        
    def create_components(self):
        """Create all UI components for this tab"""
        # Create all static elements
        #self.div_tuning_info = Div(width=200, height=100)
        self.div_speed_peak_valley_diagram = Div(width=200, height=125)
        self.div_header_line = Div(width=400, height=30)
        
        # Create buttons
        self.manual_log_button = Button(label="Log Lap Now")
        self.save_button = Button(label="Save Laps", button_type="success")
        self.reset_button = Button(label="Reset Laps", button_type="danger")
        
        # Create selects
        self.select_title = Paragraph(text="Load Laps:", align="center")
        self.select = Select(value="laps", options=[])
        self.reference_lap_select = Select(value="-1")
        
        # Create checkbox for recording replays
        self.checkbox_group = CheckboxGroup(labels=["Record Replays"], active=[1])
        
        # Connect event handlers
        self.manual_log_button.on_click(self.log_lap_button_handler)
        self.save_button.on_click(self.save_button_handler)
        self.reset_button.on_click(self.reset_button_handler)
        self.select.on_change("value", self.load_laps_handler)
        self.reference_lap_select.on_change("value", self.load_reference_lap_handler)
        self.checkbox_group.on_change("active", self.always_record_checkbox_handler)

        self.app.gt7comm.set_lap_callback (self.on_lap_finished)
        
    def create_layout(self):
        """Create layout for this tab"""
        # This layout will be populated after diagrams are set
        # For now, create a placeholder layout
        return layout([])
        
    def finalize_layout(self):
        """Create the final layout after all diagrams are set"""
        if not self.race_diagram:
            logger.error("Can't finalize layout - diagrams not set")
            return
            
        # Create help tooltip for race time table
        # from ..gt7help import TIME_TABLE
        # self.race_time_table_help = Div(text=f'<i class="fa fa-question-circle" title="{html.escape(TIME_TABLE)}"></i>', width=20)
        
        # Create and get diviance laps div
        self.div_deviance_laps_on_display = Div(width=200, height=self.race_diagram.f_speed_variance.height)
            
        # Create the complete layout
        self.layout = layout(
            children=[
                [self.div_header_line, self.reset_button, self.save_button, self.select_title, self.select],
                [self.race_diagram.f_time_diff, layout(children=[self.manual_log_button, self.checkbox_group, self.reference_lap_select])],
                [self.race_diagram.f_speed, self.s_race_line],
                [self.race_diagram.f_speed_variance, self.div_deviance_laps_on_display],
                [self.race_diagram.f_throttle, self.div_speed_peak_valley_diagram],
                [self.race_diagram.f_braking],
                [self.race_diagram.f_yaw_rate],
                [self.race_diagram.f_coasting],
                [self.race_diagram.f_gear],
                [self.race_diagram.f_rpm],
                [self.race_diagram.f_boost],
                [self.race_diagram.f_tyres],
                #[self.race_time_table.t_lap_times, self.race_time_table_help],
                #[self.div_tuning_info],
            ]
        )
        
        return self.layout
        
    def update_reference_lap_select(self, laps):
        """Update the reference lap selection dropdown"""
        self.reference_lap_select.options = [
            tuple(("-1", "Best Lap"))
        ] + bokeh_tuple_for_list_of_laps(laps)
            
    def update_header_line(self, last_lap, reference_lap):
        """Update the header line with lap information"""
        self.div_header_line.text = f"<p><b>Last Lap: {last_lap.title} ({last_lap.car_name()})<b></p>" \
                   f"<p><b>Reference Lap: {reference_lap.title} ({reference_lap.car_name()})<b></p>"
                   
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
        self.race_diagram.source_last_lap.data = {"distance": [], "speed": [], "throttle": [], "brake": [], "time": []}
        self.race_diagram.source_reference_lap.data = {"distance": [], "speed": [], "throttle": [], "brake": [], "time": []}
        self.race_diagram.source_median_lap.data = {"distance": [], "speed": [], "throttle": [], "brake": [], "time": []}
        self.race_diagram.source_time_diff.data = {"distance": [], "time_diff": []}
        
        # Clear race line visualization
        if hasattr(self, 'last_lap_race_line') and self.last_lap_race_line:
            self.last_lap_race_line.data_source.data = {"raceline_x": [], "raceline_z": []}
        if hasattr(self, 'reference_lap_race_line') and self.reference_lap_race_line:
            self.reference_lap_race_line.data_source.data = {"raceline_x": [], "raceline_z": []}
        
        # Reset race time table
        # self.race_time_table.lap_times_source.data = {"index": [], "car": [], "time": [], "number": [], "title": []}
        # self.race_time_table.lap_times_source.selected.indices = []
        
        # Clear information displays
        self.div_header_line.text = "<p><b>Last Lap: None</b></p><p><b>Reference Lap: None</b></p>"
        self.div_speed_peak_valley_diagram.text = ""
        self.div_deviance_laps_on_display.text = ""
        
        # Reset reference lap selection
        self.reference_lap_selected = None
        self.reference_lap_select.value = "-1"  # Best Lap option
        
        # Reset stored data
        self.laps_stored = []
        
        # Clear GT7 communication data
        self.app.gt7comm.session.load_laps([], replace_other_laps=True)
        self.app.gt7comm.reset()
        
        # Force full UI update
        self.telemetry_update_needed = True
        
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
        logger.info("Added a lap manually to the list of laps: %s" % self.app.gt7comm.session.laps[0])

    def save_button_handler(self, event):
        """Handle saving laps"""
        if len(self.app.gt7comm.session.laps) > 0:
            
            path = save_laps_to_json(self.app.gt7comm.session.laps)
            logger.info("Saved %d laps as %s" % (len(self.app.gt7comm.session.laps), path))

    def load_laps_handler(self, attr, old, new):
        """Handle loading laps from file"""
        logger.info("Loading %s" % new)
        
        self.race_diagram.delete_all_additional_laps()
        self.app.gt7comm.session.load_laps(load_laps_from_json(new), replace_other_laps=True)

    def load_reference_lap_handler(self, attr, old, new):
        """Handle changing the reference lap"""
        if int(new) == -1:
            # Set no reference lap
            self.reference_lap_selected = None
        else:
            self.reference_lap_selected = self.laps_stored[int(new)]
            logger.info("Loading %s as reference" % self.laps_stored[int(new)].format())

        self.telemetry_update_needed = True
        self.update_lap_change()
        
    def table_row_selection_callback(self, attrname, old, new):
        """Handle selecting rows in the lap times table"""
        #selectionIndex = self.race_time_table.lap_times_source.selected.indices
        logger.info("You have selected the row nr " + str(selectionIndex))

        colors_index = len(self.race_diagram.sources_additional_laps) + self.race_diagram.number_of_default_laps

        for index in selectionIndex:
            if index >= len(TABLE_ROW_COLORS):
                colors_index = 0

            color = TABLE_ROW_COLORS[colors_index]
            colors_index += 1
            lap_to_add = self.laps_stored[index]
            new_lap_data_source = self.race_diagram.add_lap_to_race_diagram(color, legend=self.laps_stored[index].title, visible=True)
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
                self.race_diagram.source_time_diff.data = calculate_time_diff_by_distance(reference_lap, last_lap)
                self.race_diagram.source_reference_lap.data = reference_lap_data
                self.reference_lap_race_line.data_source.data = reference_lap_data

        if median_lap:
            self.race_diagram.source_median_lap.data = median_lap.get_data_dict()

        self.s_race_line.legend.visible = False
        self.s_race_line.axis.visible = False

        fastest_laps = self.race_diagram.update_fastest_laps_variance(laps)
        logger.info("Updating Speed Deviance with %d fastest laps" % len(fastest_laps))
        self.div_deviance_laps_on_display.text = ""
        for fastest_lap in fastest_laps:
            self.div_deviance_laps_on_display.text += f"<b>Lap {fastest_lap.number}:</b> {fastest_lap.title}<br>"

        # Update brakepoints
        brake_points_enabled = os.environ.get("GT7_ADD_BRAKEPOINTS") == "true"

        if brake_points_enabled and len(last_lap.data_braking) > 0:
            self.update_brake_points(last_lap, self.s_race_line, LAST_LAP_COLOR)

        if brake_points_enabled and len(reference_lap.data_braking) > 0:
            self.update_brake_points(reference_lap, self.s_race_line, REFERENCE_LAP_COLOR)
    
    def update_brake_points(self, lap, race_line, color):
        """Update brake points on race line"""
        
        
        brake_points_x, brake_points_y = get_brake_points(lap)

        for i, _ in enumerate(brake_points_x):
            race_line.scatter(
                brake_points_x[i],
                brake_points_y[i],
                marker="circle",
                size=10,
                fill_color=color,
            )
            
    def update_lap_change(self, step=None):
        """Update the display when laps change"""
        
        update_start_time = time.time()

        laps = self.app.gt7comm.session.get_laps()

        # Check for session change
        if hasattr(self, 'session_stored') and self.app.gt7comm.session != self.session_stored:
            #self.update_tuning_info()
            self.session_stored = copy.copy(self.app.gt7comm.session)

        # This saves on cpu time, 99.9% of the time this is true
        if laps == self.laps_stored and not self.telemetry_update_needed:
            return

        logger.debug("Rerendering laps")

        reference_lap = Lap()

        if len(laps) > 0:
            last_lap = laps[0]

            if len(laps) > 1:
                reference_lap = get_last_reference_median_lap(
                    laps, reference_lap_selected=self.reference_lap_selected
                )[1]

                self.div_speed_peak_valley_diagram.text = get_speed_peak_and_valley_diagram(last_lap, reference_lap)

            self.update_header_line(last_lap, reference_lap)

        logger.debug("Updating of %d laps" % len(laps))

        start_time = time.time()
        #self.race_time_table.show_laps(laps)
        if hasattr(self.app, "race_time_data_table_tab"):
          self.app.race_time_data_table_tab.show_laps(laps)
        logger.debug("Updating time table took %dms" % ((time.time() - start_time) * 1000))

        start_time = time.time()
        self.update_reference_lap_select(laps)
        logger.debug("Updating reference lap select took %dms" % ((time.time() - start_time) * 1000))

        start_time = time.time()
        self.update_speed_velocity_graph(laps)
        logger.debug("Updating speed velocity graph took %dms" % ((time.time() - start_time) * 1000))

        logger.debug("End of updating laps, whole Update took %dms" % ((time.time() - update_start_time) * 1000))

        self.laps_stored = laps.copy()
        self.telemetry_update_needed = False
        
    def initialize(self):
        """Initialize race lines and setup available lap files"""

        # Set up race line components if they haven't been created yet
        if self.s_race_line and not hasattr(self, 'last_lap_race_line'):
            # Create race lines if needed
            self.last_lap_race_line = self.s_race_line.line(
                x="raceline_x",
                y="raceline_z",
                legend_label="Last Lap",
                line_width=1,
                color="cyan",
                source=ColumnDataSource(data={"raceline_x": [], "raceline_z": []})
            )
            
            self.reference_lap_race_line = self.s_race_line.line(
                x="raceline_x",
                y="raceline_z",
                legend_label="Reference Lap",
                line_width=1,
                color="magenta",
                source=ColumnDataSource(data={"raceline_x": [], "raceline_z": []})
            )
        
        # Initialize available lap files
        stored_lap_files = bokeh_tuple_for_list_of_lapfiles(
            list_lap_files_from_path(os.path.join(os.getcwd(), "data"))
        )
        self.select.options = stored_lap_files
        
        # Track session data
        self.session_stored = None
        self.connection_status_stored = None

    def get_tab_panel(self):
        """Create a TabPanel for this tab"""
        return TabPanel(child=self.layout, title="Get Faster")

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
            css_classes=["tyre-temp-row"]
        )

    def update_tyre_temp_display(self, lap):
        """Update the tyre temperature display with values from the finished lap."""
        self.tyre_temp_FL.text = f"FL: {getattr(lap, 'tyre_temp_FL', '--'):.1f} °C"
        self.tyre_temp_FR.text = f"FR: {getattr(lap, 'tyre_temp_FR', '--'):.1f} °C"
        self.tyre_temp_RL.text = f"RL: {getattr(lap, 'tyre_temp_RL', '--'):.1f} °C"
        self.tyre_temp_RR.text = f"RR: {getattr(lap, 'tyre_temp_RR', '--'):.1f} °C"

    # In your lap finish callback (e.g., in RaceTab or wherever you handle lap completion):
    def on_lap_finished(self, lap):
        self.update_tyre_temp_display(lap)