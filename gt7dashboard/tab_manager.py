from bokeh.models import Tabs
from bokeh.plotting import figure
from .tabs.racelines_tab import RaceLinesTab
from .tabs.race_tab import RaceTab
from .tabs.config_tab import ConfigTab
from .tabs.fuel_tab import FuelTab
from .tabs.laptime_analysis_tab import LapTimeAnalysisTab
from .tabs.racetime_datatable_tab import RaceTimeDataTableTab

class TabManager:
    """Manages all tabs in the GT7 Dashboard"""

    def __init__(self, app_instance):
        self.app = app_instance

        # Create tabs
        self.race_lines_tab = RaceLinesTab(app_instance)
        self.race_tab = RaceTab(app_instance)
        self.config_tab = ConfigTab(app_instance)
        self.fuel_tab = FuelTab(app_instance)
        self.laptime_table_tab = LapTimeAnalysisTab(app_instance)
        self.racetime_datatable_tab = RaceTimeDataTableTab(app_instance)

    def create_tabs(self):
        """Create and return the Tabs widget with all tab panels"""
        tabs = [
            self.race_tab.get_tab_panel(),
            self.race_lines_tab.get_tab_panel(),
            self.racetime_datatable_tab.get_tab_panel(),
            self.laptime_table_tab.get_tab_panel(),
            self.fuel_tab.get_tab_panel(),
            self.config_tab.get_tab_panel(),
        ]
        return Tabs(tabs=tabs)

    def update_all(self):
        """Update all tab displays"""
        # self.config_tab.update_connection_status()
        # Add other tab updates as needed