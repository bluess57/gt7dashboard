from bokeh.models import Panel, Tabs, Div, TabPanel
from bokeh.layouts import column
from gt7dashboard.race_time_datatable import RaceTimeDataTable

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
        self.race_time_table.show_laps(laps)

    def get_tab_panel(self):
        """Create a TabPanel for this tab"""
        return TabPanel(child=self.layout, title="Lap Times Table")