import logging
from bokeh.models import Panel, Tabs, Div, TabPanel
from bokeh.layouts import column
from gt7dashboard.race_time_datatable import RaceTimeDataTable

logger = logging.getLogger('racetime_datatable_tab')
logger.setLevel(logging.DEBUG)

class RaceTimeDataTableTab:
    def __init__(self, app):
        self.app = app
        self.race_time_table = RaceTimeDataTable()
        self.header = Div(text="<h2>Lap Times</h2>", css_classes=["header"])
        self.layout = column(
            self.header,
            self.race_time_table.t_lap_times,
            sizing_mode="stretch_both"
        )

    def show_laps(self, laps):
        """
        Display all laps data in the race time table.
        """
        logger.info("Showing laps in RaceTimeDataTableTab")
        
        if hasattr(self.race_time_table, "update_lap_times"):
            self.race_time_table.update_lap_times(laps)
        elif hasattr(self.race_time_table.t_lap_times, "data_source"):
            # Fallback: update the data source directly if update_lap_times is not available
            self.race_time_table.t_lap_times.data_source.data = {
                key: [getattr(lap, key, None) for lap in laps]
                for key in self.race_time_table.t_lap_times.data_source.data.keys()
            }

    def get_tab_panel(self):
        """Create a TabPanel for this tab"""
        return TabPanel(child=self.layout, title="Lap Times Table")