import logging
import time
from functools import wraps
from typing import List
from bokeh.layouts import layout
from bokeh.models import ColumnDataSource, Range1d, Span
from bokeh.plotting import figure

from gt7dashboard import gt7helper
from gt7dashboard.gt7lap import Lap
from gt7dashboard.colors import (
    LAST_LAP_COLOR,
    REFERENCE_LAP_COLOR,
    MEDIAN_LAP_COLOR,
    SELECTED_LAP_COLOR,
)
from gt7dashboard.gt7settings import get_log_level
from gt7dashboard.gt7performance_monitor import performance_monitor

logger = logging.getLogger(__name__)
logger.setLevel(get_log_level())


class RaceDiagram:
    def __init__(self, width=400):
        # Initialize collections more efficiently
        self.selected_lap_source = None
        self.selected_lap_lines = []

        # Use dict comprehension for line collections
        self._line_collections = {
            "speed": [],
            "braking": [],
            "coasting": [],
            "throttle": [],
            "tyres": [],
            "rpm": [],
            "gears": [],
            "boost": [],
            "yaw_rate": [],
        }

        # Initialize sources list for additional laps
        self.sources_additional_laps = []
        self.number_of_default_laps = 3  # Last, Reference, Median

        # Cache frequently used values
        self._width = width
        self._height = 250
        self._sub_height = int(self._height / 2)
        self._variance_height = int(self._height / 4)

        # Initialize cache attributes FIRST - before any method calls
        self._layout_cache = None
        self._figures_initialized = False

        # Pre-create and cache dummy data attributes BEFORE _get_dummy_data() can be called
        self._dummy_data = None
        self._dummy_data_created = False

        # Pre-create tooltip configurations to avoid recreation
        self._tooltips = self._create_tooltip_configs()

        # Create figures FIRST
        self._init_figures()

        # Then initialize sources that depend on figures
        self._init_data_sources()

        # Setup layout last - use private attribute for caching
        self._setup_layout()

    def _create_tooltip_configs(self):
        """Pre-create tooltip configurations to avoid recreation"""
        return {
            "main": [
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
            ],
            "timedelta": [
                ("index", "$index"),
                ("timedelta", "@timedelta{0} ms"),
                ("reference", "@reference{0} ms"),
                ("comparison", "@comparison{0} ms"),
            ],
            "speed_variance": [
                ("index", "$index"),
                ("Distance", "@distance{0} m"),
                ("Spd. Deviation", "@speed_variance{0}"),
            ],
        }

    def _init_figures(self):
        """Create and configure the figures for the dashboard"""
        # Create main speed figure first
        self.f_speed = figure(
            title="Last, Reference, Median",
            y_axis_label="Speed",
            width=self._width,
            height=self._height,
            tooltips=self._tooltips["main"],
            active_drag="box_zoom",
            min_border_left=60,
        )

        # Create other figures with shared x_range
        self.f_speed_variance = figure(
            y_axis_label="Spd.Dev.",
            x_range=self.f_speed.x_range,
            y_range=Range1d(0, 50),
            width=self._width,
            height=self._variance_height,
            tooltips=self._tooltips["speed_variance"],
            active_drag="box_zoom",
            min_border_left=60,
        )

        self.f_time_diff = figure(
            title="Time Diff - Last, Reference",
            x_range=self.f_speed.x_range,
            y_axis_label="Time / Diff",
            width=self._width,
            height=self._sub_height,
            tooltips=self._tooltips["timedelta"],
            active_drag="box_zoom",
            min_border_left=60,
        )

        # Create sub-figures using a loop to reduce code duplication
        sub_figures = [
            ("f_throttle", "Throttle"),
            ("f_braking", "Braking"),
            ("f_coasting", "Coasting"),
            ("f_tyres", "Tire Spd / Car Spd"),
            ("f_gear", "Gear"),
            ("f_rpm", "RPM"),
            ("f_boost", "Boost"),
            ("f_yaw_rate", "Yaw Rate / s"),
        ]

        for fig_name, y_label in sub_figures:
            fig = figure(
                x_range=self.f_speed.x_range,
                y_axis_label=y_label,
                width=self._width,
                height=self._sub_height,
                tooltips=self._tooltips["main"],
                active_drag="box_zoom",
                min_border_left=60,
            )
            # Hide x-axis for all sub-figures
            fig.xaxis.visible = False
            fig.toolbar.autohide = True
            setattr(self, fig_name, fig)

        # Configure toolbar settings
        self.f_speed.toolbar.autohide = True
        self.f_speed_variance.toolbar.autohide = True
        self.f_time_diff.toolbar.autohide = True

        # Configure speed variance figure
        self.f_speed_variance.xaxis.visible = False

        # Add time diff line and span
        span_zero_time_diff = Span(
            location=0,
            dimension="width",
            line_color="white",
            line_dash="dashed",
            line_width=1,
        )
        self.f_time_diff.add_layout(span_zero_time_diff)

    def _init_data_sources(self):
        """Initialize data sources for the figures - AFTER figures are created"""
        # Initialize basic data sources
        self.source_time_diff = ColumnDataSource(data={"distance": [], "timedelta": []})
        self.source_speed_variance = ColumnDataSource(
            data={"distance": [], "speed_variance": []}
        )

        # Add time diff line
        self.f_time_diff.line(
            x="distance",
            y="timedelta",
            source=self.source_time_diff,
            line_width=1,
            color="cyan",
            line_alpha=1,
        )

        # Add speed variance line
        self.f_speed_variance.line(
            x="distance",
            y="speed_variance",
            source=self.source_speed_variance,
            line_width=1,
            color="gray",
            line_alpha=1,
            visible=True,
        )

        # Now create the default lap sources (figures exist now)
        self.source_last_lap = self.add_lap_to_race_diagram(
            LAST_LAP_COLOR, "Last Lap", True
        )
        self.source_reference_lap = self.add_lap_to_race_diagram(
            REFERENCE_LAP_COLOR, "Reference Lap", True
        )
        self.source_median_lap = self.add_lap_to_race_diagram(
            MEDIAN_LAP_COLOR, "Median Lap", True
        )

        # Set legend click policies AFTER renderers are added
        self._set_legend_policies_batch()

    def _set_legend_policies_batch(self):
        """Set legend policies in batch to avoid repeated operations"""
        figures_with_legends = [
            self.f_speed,
            self.f_throttle,
            self.f_braking,
            self.f_coasting,
            self.f_tyres,
            self.f_gear,
            self.f_rpm,
            self.f_boost,
            self.f_yaw_rate,
        ]

        # Batch operation
        for fig in figures_with_legends:
            if hasattr(fig, "legend") and fig.legend:
                fig.legend.click_policy = "hide"
                # Set common legend properties
                fig.legend.location = "top_left"
                fig.legend.label_text_font_size = "8pt"

    def _setup_layout(self):
        """Create the final layout and store in cache"""
        self._layout_cache = layout(
            self.f_time_diff,
            self.f_speed,
            self.f_speed_variance,
            self.f_throttle,
            self.f_yaw_rate,
            self.f_braking,
            self.f_coasting,
            self.f_tyres,
            self.f_gear,
            self.f_rpm,
            self.f_boost,
        )

    @property
    def layout(self):
        """Lazy layout creation with caching"""
        if self._layout_cache is None:
            self._setup_layout()
        return self._layout_cache

    def get_layout(self):
        return self.layout

    def _get_dummy_data(self):
        """Lazy creation and caching of dummy data"""
        if not self._dummy_data_created:
            self._dummy_data = Lap().get_data_dict()
            self._dummy_data_created = True
        return self._dummy_data.copy()  # Always return a copy to avoid mutations

    def add_lap_to_race_diagram(self, color: str, legend: str, visible: bool = True):
        """Optimized lap addition with improved data handling"""
        source = ColumnDataSource(data=self._get_dummy_data())

        # Batch line creation
        line_configs = [
            ("speed", self.f_speed, "speed"),
            ("throttle", self.f_throttle, "throttle"),
            ("braking", self.f_braking, "brake"),
            ("coasting", self.f_coasting, "coast"),
            ("tyres", self.f_tyres, "tyres"),
            ("gears", self.f_gear, "gear"),
            ("rpm", self.f_rpm, "rpm"),
            ("boost", self.f_boost, "boost"),
            ("yaw_rate", self.f_yaw_rate, "yaw_rate"),
        ]

        # Create lines in batch
        for line_type, figure, y_field in line_configs:
            line = figure.line(
                x="distance",
                y=y_field,
                source=source,
                legend_label=legend,
                line_width=1,
                color=color,
                line_alpha=1,
                visible=visible,
            )
            self._line_collections[line_type].append(line)

        return source

    @performance_monitor
    def add_additional_lap_to_race_diagram(
        self, color: str, lap: Lap, visible: bool = True
    ):
        """Optimized lap addition with memory-efficient data handling"""
        source = self.add_lap_to_race_diagram(color, lap.title, visible)

        # Get lap data efficiently
        lap_data = lap.get_data_dict()

        # Use streaming for large datasets to avoid memory spikes
        if len(lap_data.get("distance", [])) > 1000:
            # Stream data in chunks for very large datasets
            chunk_size = 500
            distance_data = lap_data.get("distance", [])

            for i in range(0, len(distance_data), chunk_size):
                chunk_data = {
                    key: values[i : i + chunk_size] for key, values in lap_data.items()
                }
                if i == 0:
                    source.data = chunk_data
                else:
                    source.stream(chunk_data)
        else:
            # Direct assignment for smaller datasets
            source.data = lap_data

        self.sources_additional_laps.append(source)

    def update_fastest_laps_variance(self, laps):
        variance, fastest_laps = gt7helper.get_variance_for_fastest_laps(laps)
        self.source_speed_variance.data = variance
        return fastest_laps

    def delete_all_additional_laps(self):
        """Optimized deletion with minimal DOM updates"""
        logger.debug("delete all additional laps")

        if not self.sources_additional_laps:
            return

        # Calculate how many renderers to keep per figure
        keep_count = self.number_of_default_laps

        # Use cached figure-line pairs
        if not hasattr(self, "_figure_line_pairs_cache"):
            self._create_figure_line_pairs_cache()

        # Batch all updates to minimize redraws
        for figure, collection_key in self._figure_line_pairs_cache:
            line_collection = self._line_collections[collection_key]

            if len(line_collection) <= keep_count:
                continue

            # Get renderers to remove
            renderers_to_remove = line_collection[keep_count:]

            # Batch remove from figure (more efficient than individual removes)
            figure.renderers = [
                r for r in figure.renderers if r not in renderers_to_remove
            ]

            # Update line collection
            line_collection[:] = line_collection[:keep_count]

            # Clean up legend items in batch
            if hasattr(figure, "legend") and figure.legend and figure.legend.items:
                figure.legend.items = figure.legend.items[:keep_count]

        # Clear additional lap sources
        self.sources_additional_laps.clear()

        logger.debug(f"Removed {len(self.sources_additional_laps)} additional laps")

    def debug_renderer_count(self):
        """Debug method to check renderer counts after initialization"""
        figures = [
            ("f_speed", self.f_speed),
            ("f_speed_variance", self.f_speed_variance),
            ("f_time_diff", self.f_time_diff),
            ("f_throttle", self.f_throttle),
            ("f_braking", self.f_braking),
            ("f_coasting", self.f_coasting),
            ("f_tyres", self.f_tyres),
            ("f_gear", self.f_gear),
            ("f_rpm", self.f_rpm),
            ("f_boost", self.f_boost),
            ("f_yaw_rate", self.f_yaw_rate),
        ]

        print("=== Renderer Count Debug ===")
        for name, fig in figures:
            renderer_count = len(fig.renderers)
            print(f"{name}: {renderer_count} renderers")
            if renderer_count == 0:
                print(f"  ⚠️  {name} HAS NO RENDERERS!")

        return True

    def set_selected_lap(self, lap, color=SELECTED_LAP_COLOR, legend="Selected Lap"):
        """Set a single selected lap, removing any previous selection"""
        # Remove previous selected lap if it exists
        self.clear_selected_lap()

        # Add the new selected lap
        self.selected_lap_source = self.add_lap_to_race_diagram(
            color=color,
            legend=legend,
            visible=True,
        )

        # Update with lap data
        if self.selected_lap_source and lap:
            lap_data = lap.get_data_dict()
            self.selected_lap_source.data = lap_data

            # Store reference to the selected lap lines for easy removal
            self.selected_lap_lines = [
                self._line_collections["speed"][-1],
                self._line_collections["throttle"][-1],
                self._line_collections["braking"][-1],
                self._line_collections["coasting"][-1],
                self._line_collections["tyres"][-1],
                self._line_collections["gears"][-1],
                self._line_collections["rpm"][-1],
                self._line_collections["boost"][-1],
                self._line_collections["yaw_rate"][-1],
            ]

            logger.debug(f"Set selected lap: {legend}")

    def clear_selected_lap(self):
        """Optimized selected lap clearing with batch operations"""
        if not self.selected_lap_lines:
            return

        # Use cached figure-line pairs
        if not hasattr(self, "_figure_line_pairs_cache"):
            self._create_figure_line_pairs_cache()

        # Batch remove operations
        lines_to_remove = set(self.selected_lap_lines)  # Use set for faster lookups

        for figure, collection_key in self._figure_line_pairs_cache:
            line_list = self._line_collections[collection_key]

            # Remove from line list (filter is more efficient than individual removes)
            self._line_collections[collection_key] = [
                line for line in line_list if line not in lines_to_remove
            ]

            # Remove from figure renderers in batch
            figure.renderers = [
                renderer
                for renderer in figure.renderers
                if renderer not in lines_to_remove
            ]

            # Clean legend items efficiently
            if hasattr(figure, "legend") and figure.legend and figure.legend.items:
                figure.legend.items = [
                    item
                    for item in figure.legend.items
                    if not item.label.value.startswith("Selected:")
                ]

        # Clear references
        self.selected_lap_lines.clear()
        self.selected_lap_source = None

        logger.debug("Cleared selected lap from diagrams")

    def _create_figure_line_pairs_cache(self):
        """Create cached figure-line pairs for reuse"""
        self._figure_line_pairs_cache = [
            (self.f_speed, "speed"),
            (self.f_throttle, "throttle"),
            (self.f_braking, "braking"),
            (self.f_coasting, "coasting"),
            (self.f_tyres, "tyres"),
            (self.f_gear, "gears"),
            (self.f_rpm, "rpm"),
            (self.f_boost, "boost"),
            (self.f_yaw_rate, "yaw_rate"),
        ]

    def set_median_lap_visibility(self, visible: bool):
        """Optimized median lap visibility with reduced iterations"""
        if len(self._line_collections["speed"]) >= 3:
            median_line_index = 2

            # Cache figure-line pairs to avoid repeated dict lookups
            if not hasattr(self, "_figure_line_pairs_cache"):
                self._figure_line_pairs_cache = [
                    (self.f_speed, "speed"),
                    (self.f_throttle, "throttle"),
                    (self.f_braking, "braking"),
                    (self.f_coasting, "coasting"),
                    (self.f_tyres, "tyres"),
                    (self.f_gear, "gears"),
                    (self.f_rpm, "rpm"),
                    (self.f_boost, "boost"),
                    (self.f_yaw_rate, "yaw_rate"),
                ]

            # Single loop to update all line visibilities
            for figure, collection_key in self._figure_line_pairs_cache:
                line_list = self._line_collections[collection_key]
                if len(line_list) > median_line_index:
                    line_list[median_line_index].visible = visible

            # Update legend visibility
            self._update_median_lap_legend_visibility(visible)

            logger.debug(f"Median lap visibility set to: {visible}")

    def _update_median_lap_legend_visibility(self, visible: bool):
        """Update legend visibility for median lap across all figures"""
        median_line_index = 2

        figures_with_legends = [
            self.f_speed,
            self.f_throttle,
            self.f_braking,
            self.f_coasting,
            self.f_tyres,
            self.f_gear,
            self.f_rpm,
            self.f_boost,
            self.f_yaw_rate,
        ]

        for figure in figures_with_legends:
            if (
                hasattr(figure, "legend")
                and figure.legend
                and hasattr(figure.legend, "items")
                and len(figure.legend.items) > median_line_index
            ):

                # Get the median lap legend item
                median_legend_item = figure.legend.items[median_line_index]

                # Set visibility of the legend item
                if hasattr(median_legend_item, "visible"):
                    median_legend_item.visible = visible
                else:
                    # Alternative approach: modify the legend label
                    if visible:
                        # Show the legend with original label
                        if not median_legend_item.label.value.startswith("Median Lap"):
                            median_legend_item.label.value = "Median Lap"
                    else:
                        # Hide by making label empty or adding invisible marker
                        median_legend_item.label.value = ""
