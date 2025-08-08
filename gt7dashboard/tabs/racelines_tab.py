import logging
import itertools
import numpy as np
from typing import List
from bokeh.layouts import layout, column, row
from bokeh.models import (
    ColumnDataSource,
    Div,
    Button,
    CheckboxGroup,
    Select,
)
from bokeh.palettes import Plasma11 as palette
from bokeh.plotting import figure

from gt7dashboard.gt7lap import Lap
from .GT7Tab import GT7Tab
from gt7dashboard.gt7helper import car_name
from gt7dashboard.gt7help import get_help_div
from gt7dashboard.gt7diagrams import (
    get_throttle_braking_race_line_diagram,
    add_annotations_to_race_line,
)

logger = logging.getLogger("racelines_tab")
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
        self.lap_select_title = Div(text="<b>Select lap to display:</b>", width=200)
        self.lap_select = Select(
            title="Available Laps:", value="", options=[], width=200
        )
        self.add_lap_button = Button(
            label="Add Lap to Comparison", button_type="primary", width=200
        )
        self.clear_button = Button(
            label="Clear All Lines", button_type="warning", width=200
        )

        self.help = get_help_div(
            """
            This diagram shows the racing line on the track.
            Green segments indicate throttle application.
            Red segments indicate braking.
            Cyan segments indicate coasting (neither throttle nor brake).
            """
        )

        # Display options
        self.display_options_title = Div(text="<b>Display Options:</b>", width=200)
        self.display_options = CheckboxGroup(
            labels=[
                "Show Throttle Segments",
                "Show Brake Segments",
                "Show Coasting Segments",
            ],
            active=[0, 1, 2],
        )

        # Create race lines figures
        self.create_race_line_figures()

        # Connect event handlers
        self.add_lap_button.on_click(self.add_lap_handler)
        self.clear_button.on_click(self.clear_lines_handler)
        self.display_options.on_change("active", self.display_options_handler)

        self.app.gt7comm.session.set_on_load_laps_callback(self.update_lap_options)

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
        """Add a race line using multi_line for better continuity"""
        if figure_index >= len(self.race_lines):
            logger.error(f"Figure index {figure_index} out of range")
            return

        # Debug lap data
        self.debug_lap_data(lap)

        # Create data sources for segments
        throttle_source = ColumnDataSource(data={"xs": [], "ys": []})
        braking_source = ColumnDataSource(data={"xs": [], "ys": []})
        coasting_source = ColumnDataSource(data={"xs": [], "ys": []})

        # Add multi-line renderers to the figure
        throttle_line = self.race_lines[figure_index].multi_line(
            xs="xs",
            ys="ys",
            line_width=3,
            color="green",
            legend_label=f"{lap.title} (Throttle)",
            source=throttle_source,
        )

        braking_line = self.race_lines[figure_index].multi_line(
            xs="xs",
            ys="ys",
            line_width=3,
            color="red",
            legend_label=f"{lap.title} (Braking)",
            source=braking_source,
        )

        coasting_line = self.race_lines[figure_index].multi_line(
            xs="xs",
            ys="ys",
            line_width=3,
            color="cyan",
            legend_label=f"{lap.title} (Coasting)",
            source=coasting_source,
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
            "coasting_source": coasting_source,
        }

        self.race_lines_data[figure_index].append(line_data)

        # Update the figure title
        self.race_lines[figure_index].title.text = (
            f"Race Lines - {len(self.race_lines_data[figure_index])} laps"
        )

        # Update the race line data
        self.update_race_line_data(
            lap, figure_index, len(self.race_lines_data[figure_index]) - 1
        )

        return line_data

    def update_race_line_data(self, lap: Lap, figure_index: int, line_index: int):
        """Update race line data for the given lap - CORRECTED VERSION"""
        if figure_index >= len(self.race_lines_data):
            logger.error(f"Figure index {figure_index} out of range")
            return

        if line_index >= len(self.race_lines_data[figure_index]):
            logger.error(f"Line index {line_index} out of range")
            return

        line_data = self.race_lines_data[figure_index][line_index]

        # Extract coordinates
        x_coords = lap.data_position_x
        z_coords = lap.data_position_z
        throttle = lap.data_throttle if hasattr(lap, "data_throttle") else []
        brake = lap.data_braking if hasattr(lap, "data_braking") else []
        speed = lap.data_speed if hasattr(lap, "data_speed") else []

        if len(x_coords) == 0:
            logger.warning(f"Lap {lap.title} has no position data")
            return

        logger.debug(
            f"Processing lap {lap.title}: {len(x_coords)} position points, {len(throttle)} throttle points, {len(brake)} brake points"
        )

        # Create lists to hold line segments for multi_line
        throttle_xs, throttle_ys = [], []
        braking_xs, braking_ys = [], []
        coasting_xs, coasting_ys = [], []

        # Current segment being built
        current_state = None
        segment_x, segment_z = [], []

        def finalize_segment(state):
            """Add completed segment to appropriate lists"""
            if len(segment_x) < 2:  # Need at least 2 points for a line
                return

            if state == "throttle":
                throttle_xs.append(list(segment_x))
                throttle_ys.append(list(segment_z))
            elif state == "braking":
                braking_xs.append(list(segment_x))
                braking_ys.append(list(segment_z))
            elif state == "coasting":
                coasting_xs.append(list(segment_x))
                coasting_ys.append(list(segment_z))

        # Process each data point
        for i in range(len(x_coords)):
            # Determine current driving state
            throttle_val = throttle[i] if i < len(throttle) else 0
            brake_val = brake[i] if i < len(brake) else 0

            if throttle_val > 0 and brake_val == 0:
                new_state = "throttle"
            elif brake_val > 0:
                new_state = "braking"
            else:
                new_state = "coasting"

            # If state changed, finalize previous segment and start new one
            if new_state != current_state:
                if current_state is not None:
                    finalize_segment(current_state)

                # Start new segment
                current_state = new_state
                segment_x, segment_z = [], []

            # Add point to current segment
            segment_x.append(x_coords[i])
            segment_z.append(z_coords[i])

        # Don't forget the last segment
        if current_state is not None:
            finalize_segment(current_state)

        # Update data sources with proper multi_line format
        line_data["throttle_source"].data = {
            "xs": throttle_xs,
            "ys": throttle_ys,
            "lap_name": [lap.title] * len(throttle_xs),
            "section": ["Throttle"] * len(throttle_xs),
        }

        line_data["braking_source"].data = {
            "xs": braking_xs,
            "ys": braking_ys,
            "lap_name": [lap.title] * len(braking_xs),
            "section": ["Braking"] * len(braking_xs),
        }

        line_data["coasting_source"].data = {
            "xs": coasting_xs,
            "ys": coasting_ys,
            "lap_name": [lap.title] * len(coasting_xs),
            "section": ["Coasting"] * len(coasting_xs),
        }

        logger.info(
            f"Updated race line data for {lap.title}: {len(throttle_xs)} throttle segments, {len(braking_xs)} braking segments, {len(coasting_xs)} coasting segments"
        )

    def update_lap_options(self, laps=None):
        """Update available laps in the dropdown"""
        if laps is None:
            laps = self.app.gt7comm.session.get_laps()

        options = [
            (str(i), f"{lap.title} - {car_name(lap.car_id)}")
            for i, lap in enumerate(laps)
        ]
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
        # Clear each figure completely
        for figure_index, figure_data in enumerate(self.race_lines_data):
            figure = self.race_lines[figure_index]

            # Remove all renderers associated with race lines
            for line_data in figure_data:
                # Remove the line renderers from the figure
                renderers_to_remove = [
                    line_data["throttle_line"],
                    line_data["braking_line"],
                    line_data["coasting_line"],
                ]

                for renderer in renderers_to_remove:
                    if renderer in figure.renderers:
                        figure.renderers.remove(renderer)

            # Explicitly clear the legend after removing renderers
            if hasattr(figure, "legend") and figure.legend:
                try:
                    # Method 1: Clear legend items
                    if hasattr(figure.legend, "items"):
                        figure.legend.items = []

                    # Method 2: Force legend update by creating new legend
                    figure.legend.items = []

                    # Method 3: Remove and recreate legend (most reliable)
                    if hasattr(figure, "legend") and figure.legend in figure.renderers:
                        figure.renderers.remove(figure.legend)

                except (AttributeError, ValueError) as e:
                    logger.debug(f"Legend clearing failed: {e}")

            # Reset figure title
            figure.title.text = "Race Line"

        # Clear data structures
        self.race_lines_data = [[] for _ in range(len(self.race_lines))]
        self.selected_laps = []

        logger.info("All race lines and legends cleared")

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
            width=250,
        )

        main_content = column(
            self.div_title,
            row(
                controls,
                self.race_lines[0],
                self.help,
            ),
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
        race_lines, race_lines_data = self.get_race_lines_layout(number_of_race_lines=1)

    def get_race_lines_layout(self, number_of_race_lines):  # Add 'self' parameter
        """
        This function returns the race lines layout.
        It returns a grid of race lines with throttle (green), braking (red), and coasting (cyan).
        """
        race_line_diagrams = []
        race_lines_data = []

        sizing_mode = "scale_height"

        for i in range(number_of_race_lines):
            (
                s_race_line,
                throttle_line,
                breaking_line,
                coasting_line,
                reference_throttle_line,
                reference_breaking_line,
                reference_coasting_line,
            ) = get_throttle_braking_race_line_diagram()

            s_race_line.sizing_mode = sizing_mode
            race_line_diagrams.append(s_race_line)
            race_lines_data.append(
                [
                    throttle_line,
                    breaking_line,
                    coasting_line,
                    reference_throttle_line,
                    reference_breaking_line,
                    reference_coasting_line,
                ]
            )

        return race_line_diagrams, race_lines_data

    def update_race_lines(self, laps: List[Lap], reference_lap: Lap = None):
        """
        Update the race lines display with the provided laps and reference lap
        """
        if not laps:
            logger.warning("No laps provided to update_race_lines")
            return

        if not reference_lap:
            logger.warning("No reference lap provided to update_race_lines")
            return

        # Clear existing race lines first
        self.clear_lines_handler(None)

        # Add race lines for the most recent laps (limit to available figures)
        max_laps_to_show = min(
            len(laps), len(self.race_lines), 5
        )  # Show max 5 recent laps

        for i, lap in enumerate(laps[-max_laps_to_show:]):
            color = next(self.race_line_colors)
            self.add_race_line(lap, color, figure_index=0)
            logger.info(f"Added race line for lap {lap.title}")

        # Add reference lap with special highlighting if it's different from the recent laps
        if reference_lap not in laps[-max_laps_to_show:]:
            self.add_race_line(reference_lap, "gold", figure_index=0)
            logger.info(f"Added reference lap race line for {reference_lap.title}")

        # Update the figure title to show current status
        if self.race_lines:
            self.race_lines[0].title.text = (
                f"Race Lines - {len(laps)} total laps, Reference: {reference_lap.title}"
            )

        logger.info(f"Updated race lines display with {len(laps)} laps")

    def debug_lap_data(self, lap: Lap):
        """Debug method to check lap data"""
        logger.debug(f"=== Debug info for lap {lap.title} ===")
        logger.debug(f"Position X points: {len(getattr(lap, 'data_position_x', []))}")
        logger.debug(f"Position Z points: {len(getattr(lap, 'data_position_z', []))}")
        logger.debug(f"Throttle points: {len(getattr(lap, 'data_throttle', []))}")
        logger.debug(f"Braking points: {len(getattr(lap, 'data_braking', []))}")

        if hasattr(lap, "data_throttle") and lap.data_throttle:
            throttle_active = sum(1 for t in lap.data_throttle if t > 0)
            logger.debug(f"Active throttle points: {throttle_active}")

        if hasattr(lap, "data_braking") and lap.data_braking:
            brake_active = sum(1 for b in lap.data_braking if b > 0)
            logger.debug(f"Active braking points: {brake_active}")
