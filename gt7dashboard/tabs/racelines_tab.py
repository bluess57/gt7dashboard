import logging
import itertools
import numpy as np
from typing import List, Dict, Tuple, Optional
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
from gt7dashboard.gt7settings import (
    get_log_level,
)

logger = logging.getLogger("racelines_tab")
logger.setLevel(get_log_level())  # This will now work correctly


class RaceLinesTab(GT7Tab):
    """Tab for displaying and comparing race lines from different laps"""

    def __init__(self, app_instance):
        """Initialize the race lines tab"""
        super().__init__("Race Lines")
        self.app = app_instance

        # Pre-generate color palette for better performance
        self._color_palette = list(palette)
        self._color_index = 0

        # Initialize color cycle for backward compatibility
        self.race_line_colors = itertools.cycle(self._color_palette)

        # Cache for frequently used components and data
        self._component_cache = {}
        self._lap_data_cache = {}  # Cache processed lap data
        self._segment_cache = {}  # Cache segment calculations

        # Pre-allocate data structures for better memory management
        self.race_lines: List = []
        self.race_lines_data: List[List[Dict]] = []
        self.selected_laps: List = []

        # Cache car names to avoid repeated lookups
        self._car_name_cache: Dict[Optional[int], str] = {}

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
        """Optimized figure creation with object pooling"""
        self.race_lines = []
        self.race_lines_data = []

        # Cache configurations to avoid repeated object creation
        if not hasattr(self, "_figure_config_cache"):
            self._figure_config_cache = {
                "tooltips": [
                    ("Lap", "@lap_name"),
                    ("Section", "@section"),
                    ("Start Speed", "@start_speed kph"),
                    ("End Speed", "@end_speed kph"),
                ],
                "figure_kwargs": {
                    "title": "Race Line",
                    "x_axis_label": "X",
                    "y_axis_label": "Z",
                    "match_aspect": True,
                    "width": 800,
                    "height": 600,
                    "active_drag": "box_zoom",
                },
            }

        config = self._figure_config_cache

        for i in range(number_of_figures):
            race_line_figure = figure(
                tooltips=config["tooltips"], **config["figure_kwargs"]
            )

            # Batch configuration
            race_line_figure.y_range.flipped = True
            race_line_figure.toolbar.autohide = True

            # Pre-create placeholder to avoid warnings
            placeholder_source = ColumnDataSource(data={"x": [], "y": []})
            race_line_figure.line(
                x="x", y="y", source=placeholder_source, line_alpha=0, line_width=0
            )

            self.race_lines.append(race_line_figure)
            self.race_lines_data.append([])

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
        """Optimized race line data update with caching"""
        if figure_index >= len(self.race_lines_data):
            logger.error(f"Figure index {figure_index} out of range")
            return

        if line_index >= len(self.race_lines_data[figure_index]):
            logger.error(f"Line index {line_index} out of range")
            return

        # Check cache first
        lap_cache_key = f"{lap.title}_{id(lap)}"
        if lap_cache_key in self._lap_data_cache:
            cached_data = self._lap_data_cache[lap_cache_key]
            line_data = self.race_lines_data[figure_index][line_index]

            # Update sources with cached data
            line_data["throttle_source"].data = cached_data["throttle_segments"]
            line_data["braking_source"].data = cached_data["braking_segments"]
            line_data["coasting_source"].data = cached_data["coasting_segments"]
            return

        line_data = self.race_lines_data[figure_index][line_index]

        # Extract and process coordinates efficiently
        coords_data = self._extract_lap_coordinates(lap)
        if coords_data is None:
            return

        x_coords, z_coords, throttle, brake, speed = coords_data

        # Vectorized state determination
        throttle_mask = (throttle > 0) & (brake == 0)
        braking_mask = brake > 0
        coasting_mask = ~throttle_mask & ~braking_mask

        # Create segment data
        throttle_segments = self._create_segments_vectorized(
            x_coords, z_coords, speed, throttle_mask, lap.title, "Throttle"
        )
        braking_segments = self._create_segments_vectorized(
            x_coords, z_coords, speed, braking_mask, lap.title, "Braking"
        )
        coasting_segments = self._create_segments_vectorized(
            x_coords, z_coords, speed, coasting_mask, lap.title, "Coasting"
        )

        # Cache the results
        self._lap_data_cache[lap_cache_key] = {
            "throttle_segments": throttle_segments,
            "braking_segments": braking_segments,
            "coasting_segments": coasting_segments,
        }

        # Update data sources
        line_data["throttle_source"].data = throttle_segments
        line_data["braking_source"].data = braking_segments
        line_data["coasting_source"].data = coasting_segments

    def _extract_lap_coordinates(self, lap: Lap) -> Optional[Tuple[np.ndarray, ...]]:
        """Extract and validate lap coordinates efficiently"""
        try:
            x_coords = (
                np.asarray(lap.data_position_x, dtype=np.float32)
                if lap.data_position_x
                else np.array([])
            )
            z_coords = (
                np.asarray(lap.data_position_z, dtype=np.float32)
                if lap.data_position_z
                else np.array([])
            )

            if len(x_coords) == 0:
                logger.warning(f"Lap {lap.title} has no position data")
                return None

            # Extract other data with same length
            data_length = len(x_coords)
            throttle = (
                np.asarray(lap.data_throttle[:data_length], dtype=np.float32)
                if hasattr(lap, "data_throttle") and lap.data_throttle
                else np.zeros(data_length, dtype=np.float32)
            )
            brake = (
                np.asarray(lap.data_braking[:data_length], dtype=np.float32)
                if hasattr(lap, "data_braking") and lap.data_braking
                else np.zeros(data_length, dtype=np.float32)
            )
            speed = (
                np.asarray(lap.data_speed[:data_length], dtype=np.float32)
                if hasattr(lap, "data_speed") and lap.data_speed
                else np.zeros(data_length, dtype=np.float32)
            )

            return x_coords, z_coords, throttle, brake, speed

        except Exception as e:
            logger.error(f"Error extracting coordinates for lap {lap.title}: {e}")
            return None

    def _create_segments_vectorized(
        self,
        x_coords: np.ndarray,
        z_coords: np.ndarray,
        speed: np.ndarray,
        mask: np.ndarray,
        lap_title: str,
        section_name: str,
    ) -> Dict[str, List]:
        """Highly optimized segment creation using vectorized operations"""
        if not np.any(mask):
            return {
                "xs": [],
                "ys": [],
                "lap_name": [],
                "section": [],
                "start_speed": [],
                "end_speed": [],
            }

        # Use efficient boundary detection
        mask_padded = np.concatenate(([False], mask, [False]))
        diff = np.diff(mask_padded.astype(np.int8))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]

        # Pre-allocate lists with estimated size for better performance
        estimated_segments = len(starts)
        xs = []
        ys = []
        start_speeds = np.empty(estimated_segments, dtype=np.float32)
        end_speeds = np.empty(estimated_segments, dtype=np.float32)

        valid_segments = 0

        for i, (start, end) in enumerate(zip(starts, ends)):
            if end - start >= 2:  # Need at least 2 points
                xs.append(x_coords[start:end].astype(np.float32).tolist())
                ys.append(z_coords[start:end].astype(np.float32).tolist())
                start_speeds[valid_segments] = speed[start]
                end_speeds[valid_segments] = speed[end - 1]
                valid_segments += 1

        # Trim arrays to actual size
        start_speeds = start_speeds[:valid_segments].tolist()
        end_speeds = end_speeds[:valid_segments].tolist()

        return {
            "xs": xs,
            "ys": ys,
            "lap_name": [lap_title] * len(xs),
            "section": [section_name] * len(xs),
            "start_speed": start_speeds,
            "end_speed": end_speeds,
        }

    def update_lap_options(self, laps=None):
        """Optimized lap options update with caching"""
        if laps is None:
            laps = self.app.gt7comm.session.get_laps()

        options = []
        for i, lap in enumerate(laps):
            # Use cached car name lookup
            car_id = getattr(lap, "car_id", None)
            if car_id not in self._car_name_cache:
                self._car_name_cache[car_id] = car_name(car_id)

            car_display_name = self._car_name_cache[car_id]
            options.append((str(i), f"{lap.title} - {car_display_name}"))

        # Only update if options actually changed
        if self.lap_select.options != options:
            self.lap_select.options = options

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
        """Optimized race line data update with caching"""
        if figure_index >= len(self.race_lines_data):
            logger.error(f"Figure index {figure_index} out of range")
            return

        if line_index >= len(self.race_lines_data[figure_index]):
            logger.error(f"Line index {line_index} out of range")
            return

        # Check cache first
        lap_cache_key = f"{lap.title}_{id(lap)}"
        if lap_cache_key in self._lap_data_cache:
            cached_data = self._lap_data_cache[lap_cache_key]
            line_data = self.race_lines_data[figure_index][line_index]

            # Update sources with cached data
            line_data["throttle_source"].data = cached_data["throttle_segments"]
            line_data["braking_source"].data = cached_data["braking_segments"]
            line_data["coasting_source"].data = cached_data["coasting_segments"]
            return

        line_data = self.race_lines_data[figure_index][line_index]

        # Extract and process coordinates efficiently
        coords_data = self._extract_lap_coordinates(lap)
        if coords_data is None:
            return

        x_coords, z_coords, throttle, brake, speed = coords_data

        # Vectorized state determination
        throttle_mask = (throttle > 0) & (brake == 0)
        braking_mask = brake > 0
        coasting_mask = ~throttle_mask & ~braking_mask

        # Create segment data
        throttle_segments = self._create_segments_vectorized(
            x_coords, z_coords, speed, throttle_mask, lap.title, "Throttle"
        )
        braking_segments = self._create_segments_vectorized(
            x_coords, z_coords, speed, braking_mask, lap.title, "Braking"
        )
        coasting_segments = self._create_segments_vectorized(
            x_coords, z_coords, speed, coasting_mask, lap.title, "Coasting"
        )

        # Cache the results
        self._lap_data_cache[lap_cache_key] = {
            "throttle_segments": throttle_segments,
            "braking_segments": braking_segments,
            "coasting_segments": coasting_segments,
        }

        # Update data sources
        line_data["throttle_source"].data = throttle_segments
        line_data["braking_source"].data = braking_segments
        line_data["coasting_source"].data = coasting_segments

    def _extract_lap_coordinates(self, lap: Lap) -> Optional[Tuple[np.ndarray, ...]]:
        """Extract and validate lap coordinates efficiently"""
        try:
            x_coords = (
                np.asarray(lap.data_position_x, dtype=np.float32)
                if lap.data_position_x
                else np.array([])
            )
            z_coords = (
                np.asarray(lap.data_position_z, dtype=np.float32)
                if lap.data_position_z
                else np.array([])
            )

            if len(x_coords) == 0:
                logger.warning(f"Lap {lap.title} has no position data")
                return None

            # Extract other data with same length
            data_length = len(x_coords)
            throttle = (
                np.asarray(lap.data_throttle[:data_length], dtype=np.float32)
                if hasattr(lap, "data_throttle") and lap.data_throttle
                else np.zeros(data_length, dtype=np.float32)
            )
            brake = (
                np.asarray(lap.data_braking[:data_length], dtype=np.float32)
                if hasattr(lap, "data_braking") and lap.data_braking
                else np.zeros(data_length, dtype=np.float32)
            )
            speed = (
                np.asarray(lap.data_speed[:data_length], dtype=np.float32)
                if hasattr(lap, "data_speed") and lap.data_speed
                else np.zeros(data_length, dtype=np.float32)
            )

            return x_coords, z_coords, throttle, brake, speed

        except Exception as e:
            logger.error(f"Error extracting coordinates for lap {lap.title}: {e}")
            return None

    def _create_segments_vectorized(
        self,
        x_coords: np.ndarray,
        z_coords: np.ndarray,
        speed: np.ndarray,
        mask: np.ndarray,
        lap_title: str,
        section_name: str,
    ) -> Dict[str, List]:
        """Highly optimized segment creation using vectorized operations"""
        if not np.any(mask):
            return {
                "xs": [],
                "ys": [],
                "lap_name": [],
                "section": [],
                "start_speed": [],
                "end_speed": [],
            }

        # Use efficient boundary detection
        mask_padded = np.concatenate(([False], mask, [False]))
        diff = np.diff(mask_padded.astype(np.int8))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]

        # Pre-allocate lists with estimated size for better performance
        estimated_segments = len(starts)
        xs = []
        ys = []
        start_speeds = np.empty(estimated_segments, dtype=np.float32)
        end_speeds = np.empty(estimated_segments, dtype=np.float32)

        valid_segments = 0

        for i, (start, end) in enumerate(zip(starts, ends)):
            if end - start >= 2:  # Need at least 2 points
                xs.append(x_coords[start:end].astype(np.float32).tolist())
                ys.append(z_coords[start:end].astype(np.float32).tolist())
                start_speeds[valid_segments] = speed[start]
                end_speeds[valid_segments] = speed[end - 1]
                valid_segments += 1

        # Trim arrays to actual size
        start_speeds = start_speeds[:valid_segments].tolist()
        end_speeds = end_speeds[:valid_segments].tolist()

        return {
            "xs": xs,
            "ys": ys,
            "lap_name": [lap_title] * len(xs),
            "section": [section_name] * len(xs),
            "start_speed": start_speeds,
            "end_speed": end_speeds,
        }

    def update_lap_options(self, laps=None):
        """Optimized lap options update with caching"""
        if laps is None:
            laps = self.app.gt7comm.session.get_laps()

        options = []
        for i, lap in enumerate(laps):
            # Use cached car name lookup
            car_id = getattr(lap, "car_id", None)
            if car_id not in self._car_name_cache:
                self._car_name_cache[car_id] = car_name(car_id)

            car_display_name = self._car_name_cache[car_id]
            options.append((str(i), f"{lap.title} - {car_display_name}"))

        # Only update if options actually changed
        if self.lap_select.options != options:
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
        # Use the optimized color method instead of itertools.cycle
        color = self.get_next_color()

        # Check if lap is already displayed
        for line_data in self.race_lines_data[0]:
            if line_data["lap"].title == lap.title:
                logger.warning(f"Lap {lap.title} already displayed")
                return

        # Add the lap to the race lines
        self.add_race_line(lap, color)
        self.selected_laps.append(lap)

    def clear_lines_handler(self, event):
        """Highly optimized race lines clearing with minimal operations"""
        if not any(self.race_lines_data):  # Early exit if no data
            return

        # Collect all operations to minimize figure updates
        for figure_index, (figure, figure_data) in enumerate(
            zip(self.race_lines, self.race_lines_data)
        ):
            if not figure_data:
                continue

            # Collect all renderers to remove in one pass
            renderers_to_remove = set()  # Use set for O(1) lookup
            for line_data in figure_data:
                renderers_to_remove.update(
                    [
                        line_data["throttle_line"],
                        line_data["braking_line"],
                        line_data["coasting_line"],
                    ]
                )

            # Single batch operation to remove renderers
            figure.renderers = [
                r for r in figure.renderers if r not in renderers_to_remove
            ]

            # Clear legend in single operation
            if hasattr(figure, "legend") and figure.legend:
                figure.legend.items.clear()

            # Reset title
            figure.title.text = "Race Line"

        # Clear data structures efficiently
        self.race_lines_data.clear()
        self.race_lines_data.extend([[] for _ in range(len(self.race_lines))])
        self.selected_laps.clear()

        # Clear caches
        self._lap_data_cache.clear()
        self._segment_cache.clear()

        logger.info("All race lines cleared efficiently")

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
            # Use the optimized color method instead of itertools.cycle
            color = self.get_next_color()
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

    def get_next_color(self):
        """Get next color from palette with better performance"""
        color = self._color_palette[self._color_index % len(self._color_palette)]
        self._color_index += 1
        return color
