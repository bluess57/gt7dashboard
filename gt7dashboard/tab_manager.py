from bokeh.models import Tabs
from bokeh.plotting import figure
from .tabs.racelines_tab import RaceLinesTab
from .tabs.race_tab import RaceTab
from .tabs.config_tab import ConfigTab
from .tabs.fuel_tab import FuelTab
from .tabs.time_table_tab import RaceTimeTableTab
from . import gt7diagrams

class TabManager:
    """Manages all tabs in the GT7 Dashboard"""

    def __init__(self, app_instance):
        self.app = app_instance

        # Create shared components
        self.race_diagram = gt7diagrams.RaceDiagram(width=1000)
        self.race_time_table = gt7diagrams.RaceTimeTable()

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

        # Create tabs
        self.race_lines_tab = RaceLinesTab(app_instance)
        self.race_tab = RaceTab(app_instance)
        self.race_tab.set_diagrams(self.race_diagram, self.race_time_table, self.s_race_line)
        self.race_tab.initialize()
        self.race_tab.finalize_layout()

        self.config_tab = ConfigTab(app_instance)
        self.fuel_tab = FuelTab(app_instance)
        self.time_table_tab = RaceTimeTableTab(app_instance)

    def create_tabs(self):
        """Create and return the Tabs widget with all tab panels"""
        tabs = [
            self.race_tab.get_tab_panel(),
            self.fuel_tab.get_tab_panel(),
            self.config_tab.get_tab_panel(),
            self.race_lines_tab.get_tab_panel(),
            self.time_table_tab.get_tab_panel(),
        ]
        return Tabs(tabs=tabs)

    def update_all(self):
        """Update all tab displays"""
        self.config_tab.update_connection_status()
        # Add other tab updates as needed