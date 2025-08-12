import logging
from bokeh.models import Div, TabPanel, Button
from bokeh.layouts import column, row
from bokeh.plotting import curdoc
from gt7dashboard.datatable.race_time import RaceTimeDataTable
from .GT7Tab import GT7Tab
from gt7dashboard.gt7settings import get_log_level

logger = logging.getLogger("racetime_datatable_tab")
logger.setLevel(get_log_level())


class RaceTimeDataTableTab(GT7Tab):
    def __init__(self, app):
        super().__init__("Lap Times Table")
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
        self.app.gt7comm.session.set_on_add_lap_callback(self.lap_added)

    def lap_added(self, lap):
        """
        A lap was added to session so add to the data table
        """
        logger.debug("RaceTimeDataTableTab: Add a lap to RaceTimeDataTable")
        self.race_time_datatable.add_lap(lap, self.app.doc)

    def show_laps(self, laps):
        """
        Display all laps data in the race time table.
        """
        logger.debug("Showing laps in RaceTimeDataTable")
        self.race_time_datatable.show_laps(laps)
