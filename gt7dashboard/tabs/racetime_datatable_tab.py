import logging
from bokeh.models import Panel, Tabs, Div, TabPanel, Button
from bokeh.layouts import column, row
from gt7dashboard.race_time_datatable import RaceTimeDataTable

logger = logging.getLogger("racetime_datatable_tab")
logger.setLevel(logging.DEBUG)


class RaceTimeDataTableTab:
    def __init__(self, app):
        self.app = app
        self.race_time_table = RaceTimeDataTable()
        self.header = Div(text="<h2>Lap Times</h2>", css_classes=["header"])
        deleteLapButton = Button(label="Delete lap", width=100, button_type="danger")
        deleteLapButton.on_click(
            lambda: self.race_time_table.delete_lap(
                self.race_time_table.lap_times_source.selected.indices
            )
        )
        self.layout = row(
            column(deleteLapButton),
            column(
                self.header,
                self.race_time_table.t_lap_times,
                sizing_mode="stretch_both",
            ),
        )
        self.app.gt7comm.session.set_on_load_laps_callback(self.show_laps)

    def show_laps(self, laps):
        """
        Display all laps data in the race time table.
        """
        logger.debug("Showing laps in RaceTimeDataTableTab")
        self.race_time_table.show_laps(laps)

    def get_tab_panel(self):
        """Create a TabPanel for this tab"""
        return TabPanel(child=self.layout, title="Lap Times Table")
