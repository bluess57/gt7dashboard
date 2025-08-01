import logging
from bokeh.models import Panel, Tabs, Div, TabPanel, Button
from bokeh.layouts import column, row
from gt7dashboard.race_time_datatable import RaceTimeDataTable

logger = logging.getLogger("racetime_datatable_tab")
logger.setLevel(logging.DEBUG)


class RaceTimeDataTableTab:
    def __init__(self, app):
        self.app = app
        self.race_time_datatable = RaceTimeDataTable(app)
        self.header = Div(text="<h2>Lap Times</h2>", css_classes=["header"])
        deleteLapButton = Button(label="Delete lap", width=100, button_type="danger")
        deleteLapButton.on_click(
            lambda: self.race_time_datatable.delete_selected_laps()
        )

        self.layout = row(
            column(deleteLapButton),
            column(
                self.header,
                self.race_time_datatable.dt_lap_times,
                sizing_mode="stretch_both",
            ),
        )
        self.app.gt7comm.session.set_on_load_laps_callback(self.show_laps)

    def show_laps(self, laps):
        """
        Display all laps data in the race time table.
        """
        logger.debug("Showing laps in RaceTimeDataTableTab")
        self.race_time_datatable.show_laps(laps)

    def get_tab_panel(self):
        """Create a TabPanel for this tab"""
        return TabPanel(child=self.layout, title="Lap Times Table")
