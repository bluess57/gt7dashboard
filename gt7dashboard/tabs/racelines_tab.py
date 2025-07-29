import logging
import itertools
from typing import List, Tuple

import numpy as np
from bokeh.layouts import layout, column, row
from bokeh.models import (
    ColumnDataSource, TabPanel, Div, Button, CheckboxGroup,
    Select, HelpButton, Tooltip
)
from bokeh.palettes import Plasma11 as palette
from bokeh.plotting import figure

from ..gt7lap import Lap
from ..gt7help import add_help_tooltip
from .base_tab import GT7Tab

logger = logging.getLogger('racelines_tab')
logger.setLevel(logging.DEBUG)

class RaceLinesTab(GT7Tab):
    """Tab for displaying and comparing race lines from different laps"""
    
    def __init__(self, app_instance):
        """Initialize the race lines tab"""
        super().__init__("Race Lines")
        self.app = app_instance
        self.race_lines = []
        self.race_lines_data = []
        self.selected_laps = []
        self.race_line_colors = itertools.cycle(palette)
        self.create_components()
        self.layout = self.create_layout()
        
    def create_components(self):
        """Create all UI components for this tab"""
        # Create header and info components
        self.div_title = Div(text="<h3>Race Lines Comparison</h3>", width=400)
        # self.div_info = Div(text="""
        # <p>This tab allows you to compare racing lines across different laps.</p>
        # <p>Select laps from the dropdown to visualize their racing lines on the track map.</p>
        # <p>Color coding: <span style="color:green">Green</span> = Throttle, 
        # <span style="color:red">Red</span> = Braking, 
        # <span style="color:blue">Blue</span> = Coasting</p>
        # """, width=600)

        # Lap selection components
        self.lap_select_title = Div(text="<b>Select Laps to Display:</b>", width=200)
        self.lap_select = Select(title="Available Laps:", value="", options=[], width=200)
        self.add_lap_button = Button(label="Add Lap to Comparison", button_type="primary", width=200)
        self.clear_button = Button(label="Clear All Lines", button_type="warning", width=200)
        
        help_tooltip = Tooltip(
          content="""
            This diagram shows the racing line on the track.
            Green segments indicate throttle application.
            Red segments indicate braking.
            Cyan segments indicate coasting (neither throttle nor brake).
            """,
          position="right",
          css_classes=["custom-tooltip"]
        )
        self.help = HelpButton(label="?", tooltip=help_tooltip)

        # Display options
        self.display_options_title = Div(text="<b>Display Options:</b>", width=200)
        self.display_options = CheckboxGroup(
            labels=["Show Throttle Segments", "Show Brake Segments", "Show Coasting Segments"], 
            active=[0, 1, 2]
        )
        
        # Create race lines figures
        self.create_race_line_figures()
        
        # Connect event handlers
        self.add_lap_button.on_click(self.add_lap_handler)
        self.clear_button.on_click(self.clear_lines_handler)
        self.display_options.on_change("active", self.display_options_handler)
        
    def create_race_line_figures(self, number_of_figures=1):
        """Create figures for displaying race lines"""
        self.race_lines = []
        self.race_lines_data = []
        
        tooltips = [
            ("Lap", "@lap_name"),
            ("Section", "@section"),
            ("Speed", "@speed kph"),
        ]
        
        for i in range(number_of_figures):
            race_line_figure = figure(
                title="Race Line",
                x_axis_label="X",
                y_axis_label="Z",
                match_aspect=True,
                width=800,
                height=600,
                active_drag="box_zoom",
                tooltips=tooltips,
            )
            
            # Flip Y axis to match game coordinates
            race_line_figure.y_range.flipped = True
            race_line_figure.toolbar.autohide = True
                       
            self.race_lines.append(race_line_figure)
            
            # Create data sources for this figure
            figure_data_sources = []
            self.race_lines_data.append(figure_data_sources)
    
    def add_race_line(self, lap: Lap, color: str, figure_index=0):
        """Add a race line for the given lap to the specified figure"""
        if figure_index >= len(self.race_lines):
            logger.error(f"Figure index {figure_index} out of range")
            return
            
        # Create data sources for throttle, braking, and coasting segments
        throttle_source = ColumnDataSource(data={
            "raceline_x_throttle": [], 
            "raceline_z_throttle": [],
            "lap_name": [],
            "section": [],
            "speed": []
        })
        
        braking_source = ColumnDataSource(data={
            "raceline_x_braking": [], 
            "raceline_z_braking": [],
            "lap_name": [],
            "section": [],
            "speed": []
        })
        
        coasting_source = ColumnDataSource(data={
            "raceline_x_coasting": [], 
            "raceline_z_coasting": [],
            "lap_name": [],
            "section": [],
            "speed": []
        })
        
        # Add renderers to the figure
        throttle_line = self.race_lines[figure_index].line(
            x="raceline_x_throttle",
            y="raceline_z_throttle",
            line_width=2,
            color="green",
            legend_label=f"{lap.title} (Throttle)",
            source=throttle_source
        )
        
        braking_line = self.race_lines[figure_index].line(
            x="raceline_x_braking",
            y="raceline_z_braking",
            line_width=2,
            color="red",
            legend_label=f"{lap.title} (Braking)",
            source=braking_source
        )
        
        coasting_line = self.race_lines[figure_index].line(
            x="raceline_x_coasting",
            y="raceline_z_coasting",
            line_width=2,
            color="cyan",
            legend_label=f"{lap.title} (Coasting)",
            source=coasting_source
        )
        
        # Store data sources
        line_data = {
            "lap": lap,
            "color": color,
            "throttle_line": throttle_line,
            "braking_line": braking_line,
            "coasting_line": coasting_line,
            "throttle_source": throttle_source,
            "braking_source": braking_source,
            "coasting_source": coasting_source
        }
        
        self.race_lines_data[figure_index].append(line_data)
        
        # Update the figure title
        self.race_lines[figure_index].title.text = f"Race Lines - {len(self.race_lines_data[figure_index])} laps"
        
        # Update the race line data
        self.update_race_line_data(lap, figure_index, len(self.race_lines_data[figure_index]) - 1)
        
        return line_data
        
    def update_race_line_data(self, lap: Lap, figure_index: int, line_index: int):
        """Update race line data for the given lap"""
        if not lap.has_data():
            logger.warning(f"Lap {lap.title} has no data")
            return
            
        if figure_index >= len(self.race_lines_data) or line_index >= len(self.race_lines_data[figure_index]):
            logger.error(f"Invalid figure/line index: {figure_index}/{line_index}")
            return
            
        line_data = self.race_lines_data[figure_index][line_index]
        
        # Extract coordinates
        x_coords = lap.data_position_x
        z_coords = lap.data_position_z
        throttle = lap.data_throttle
        brake = lap.data_braking
        speed = lap.data_speed
        
        if len(x_coords) == 0:
            logger.warning(f"Lap {lap.title} has no position data")
            return
            
        # Segment data based on driving inputs
        x_throttle, z_throttle, speed_throttle = [], [], []
        x_braking, z_braking, speed_braking = [], [], []
        x_coasting, z_coasting, speed_coasting = [], [], []
        
        for i in range(len(x_coords)):
            if i < len(throttle) and i < len(brake):
                if throttle[i] > 0 and brake[i] == 0:
                    # Throttle segment
                    x_throttle.append(x_coords[i])
                    z_throttle.append(z_coords[i])
                    speed_throttle.append(speed[i] if i < len(speed) else 0)
                elif brake[i] > 0:
                    # Braking segment
                    x_braking.append(x_coords[i])
                    z_braking.append(z_coords[i])
                    speed_braking.append(speed[i] if i < len(speed) else 0)
                else:
                    # Coasting segment (neither throttle nor brake)
                    x_coasting.append(x_coords[i])
                    z_coasting.append(z_coords[i])
                    speed_coasting.append(speed[i] if i < len(speed) else 0)
                    
        # Update data sources
        line_data["throttle_source"].data = {
            "raceline_x_throttle": x_throttle,
            "raceline_z_throttle": z_throttle,
            "lap_name": [lap.title] * len(x_throttle),
            "section": ["Throttle"] * len(x_throttle),
            "speed": speed_throttle
        }
        
        line_data["braking_source"].data = {
            "raceline_x_braking": x_braking,
            "raceline_z_braking": z_braking,
            "lap_name": [lap.title] * len(x_braking),
            "section": ["Braking"] * len(x_braking),
            "speed": speed_braking
        }
        
        line_data["coasting_source"].data = {
            "raceline_x_coasting": x_coasting,
            "raceline_z_coasting": z_coasting,
            "lap_name": [lap.title] * len(x_coasting),
            "section": ["Coasting"] * len(x_coasting),
            "speed": speed_coasting
        }
        
    def update_lap_options(self):
        """Update available laps in the dropdown"""
        laps = self.app.gt7comm.session.get_laps()
        options = [(str(i), f"{lap.title} - {lap.car_name()}") for i, lap in enumerate(laps)]
        self.lap_select.options = options
        
    def add_lap_handler(self, event):
        """Handler for adding a lap to the comparison"""
        if not self.lap_select.value:
            logger.warning("No lap selected")
            return
            
        lap_index = int(self.lap_select.value)
        laps = self.app.gt7comm.session.get_laps()
        
        if lap_index >= len(laps):
            logger.error(f"Invalid lap index: {lap_index}")
            return
            
        lap = laps[lap_index]
        color = next(self.race_line_colors)
        
        # Check if lap is already displayed
        for line_data in self.race_lines_data[0]:
            if line_data["lap"].title == lap.title:
                logger.warning(f"Lap {lap.title} already displayed")
                return
                
        # Add the lap to the race lines
        self.add_race_line(lap, color)
        self.selected_laps.append(lap)
        
    def clear_lines_handler(self, event):
        """Handler for clearing all race lines"""
        # Clear all race lines data
        for figure_index, figure_data in enumerate(self.race_lines_data):
            for line_data in figure_data:
                line_data["throttle_source"].data = {"raceline_x_throttle": [], "raceline_z_throttle": [], 
                                                    "lap_name": [], "section": [], "speed": []}
                line_data["braking_source"].data = {"raceline_x_braking": [], "raceline_z_braking": [],
                                                   "lap_name": [], "section": [], "speed": []}
                line_data["coasting_source"].data = {"raceline_x_coasting": [], "raceline_z_coasting": [],
                                                    "lap_name": [], "section": [], "speed": []}
                
            # Reset figure title
            self.race_lines[figure_index].title.text = "Race Line"
            
        # Clear selected laps
        self.race_lines_data = [[] for _ in range(len(self.race_lines))]
        self.selected_laps = []
        
    def display_options_handler(self, attr, old, new):
        """Handler for display options changes"""
        show_throttle = 0 in new
        show_braking = 1 in new
        show_coasting = 2 in new
        
        # Update visibility of all race lines
        for figure_data in self.race_lines_data:
            for line_data in figure_data:
                line_data["throttle_line"].visible = show_throttle
                line_data["braking_line"].visible = show_braking
                line_data["coasting_line"].visible = show_coasting
                
    def create_layout(self):
        """Create layout for this tab"""
        controls = column(
            self.lap_select_title,
            self.lap_select,
            self.add_lap_button,
            self.clear_button,
            self.display_options_title,
            self.display_options,
            self.help,
            width=250
        )
        
        main_content = column(
            self.div_title,
            row(controls, self.race_lines[0]),
        )
        
        return layout(
            [
                [main_content],
            ],
            sizing_mode="stretch_width",
        )
        
    def initialize(self):
        """Initialize the race lines tab"""
        # Update available laps
        self.update_lap_options()
        
    def get_tab_panel(self):
        """Create a TabPanel for this tab"""
        return TabPanel(child=self.layout, title="Race Lines")