import logging
from typing import List
from bokeh.models import ColumnDataSource, TableColumn, DataTable, ImportedStyleSheet
from gt7dashboard import gt7helper
from gt7dashboard.gt7lap import Lap

logger = logging.getLogger('RaceTimeDataTable')
logger.setLevel(logging.DEBUG)

class RaceTimeDataTable(object):
    def __init__(self):
        self.columns = [
            TableColumn(field="number", title="#"),
            TableColumn(field="time", title="Time"),
            TableColumn(field="diff", title="Diff"),
            TableColumn(field="timestamp", title="Timestamp"),
            TableColumn(field="info", title="Info"),
            TableColumn(field="fuelconsumed", title="Fuel Cons."),
            TableColumn(field="fullthrottle", title="Full Throt."),
            TableColumn(field="fullbrake", title="Full Brake"),
            TableColumn(field="nothrottle", title="Coast"),
            TableColumn(field="tyrespinning", title="Tire Spin"),
            TableColumn(field="car_name", title="Car"),
        ]

        self.lap_times_source = ColumnDataSource(
            gt7helper.pd_data_frame_from_lap([], best_lap_time=0)
        )
        self.t_lap_times: DataTable

        dtstylesheet = ImportedStyleSheet(url="gt7dashboard/static/css/styles.css")

        self.t_lap_times = DataTable(
            source=self.lap_times_source, columns=self.columns, index_position=None, 
            width=1000,
            autosize_mode ="fit_columns",
            stylesheets=[dtstylesheet]
        )

    def show_laps(self, laps: List[Lap]):
        logger.info("show_laps")
        best_lap = gt7helper.get_best_lap(laps)
        if best_lap is None:
            return

        new_df = gt7helper.pd_data_frame_from_lap(laps, best_lap_time=best_lap.lap_finish_time)
        self.lap_times_source.data = ColumnDataSource.from_df(new_df)

    def delete_lap(self, lap_number):
        """
        Delete a lap by its number from the loaded laps.
        Updates all tabs that display lap data.
        """
        if lap_number < 0 :
            return
        logger.info("Deleting lap number: %d", lap_number
                    )
        self.gt7comm.session.delete_lap(lap_number)

        # Update time table tab and other relevant tabs
        if hasattr(self.tab_manager, 'time_table_tab'):
            self.tab_manager.time_table_tab.show_laps(self.gt7comm.session.laps)
        if hasattr(self.tab_manager, 'race_tab'):
            self.tab_manager.race_tab.update_lap_change()

        logger.info(f"Deleted lap {lap_number}.")