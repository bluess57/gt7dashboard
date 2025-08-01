import logging
from typing import List
from bokeh.models import ColumnDataSource, TableColumn, DataTable, ImportedStyleSheet
from gt7dashboard import gt7helper
from gt7dashboard.gt7lap import Lap
import numpy as np

logger = logging.getLogger("RaceTimeDataTable")
logger.setLevel(logging.DEBUG)


class RaceTimeDataTable(object):
    def __init__(self, app):
        self.app = app
        self.columns = [
            TableColumn(field="number", title="#"),
            TableColumn(field="time", title="Time"),
            TableColumn(field="diff", title="Delta"),
            TableColumn(field="timestamp", title="Timestamp"),
            TableColumn(field="fullthrottle", title="Full Throt."),
            TableColumn(field="fullbrake", title="Full Brake"),
            TableColumn(field="nothrottle", title="Coast"),
            TableColumn(field="tyrespinning", title="Tire Spin"),
            TableColumn(field="fuelconsumed", title="Fuel Cons."),
            TableColumn(field="replay", title="Replay"),
            TableColumn(field="car_name", title="Car"),
        ]

        self.lap_times_source = ColumnDataSource(
            gt7helper.pd_data_frame_from_lap([], best_lap_time=0)
        )

        dtstylesheet = ImportedStyleSheet(url="gt7dashboard/static/css/styles.css")

        self.dt_lap_times = DataTable(
            source=self.lap_times_source,
            columns=self.columns,
            index_position=None,
            width=1000,
            autosize_mode="fit_columns",
            stylesheets=[dtstylesheet],
        )

    def show_laps(self, laps: List[Lap]):
        logger.info("show_laps")
        best_lap = gt7helper.get_best_lap(laps)
        if best_lap is None:
            empty_df = gt7helper.pd_data_frame_from_lap([], best_lap_time=0)
            self.lap_times_source.data = ColumnDataSource.from_df(empty_df)
            return

        new_df = gt7helper.pd_data_frame_from_lap(
            laps, best_lap_time=best_lap.lap_finish_time
        )
        self.lap_times_source.data = ColumnDataSource.from_df(new_df)

        self.dt_lap_times.source = self.lap_times_source

    def delete_selected_laps(self):
        """
        Delete any selected lap from the loaded laps.
        Update table of display lap data.
        """
        selected_indices = self.lap_times_source.selected.indices
        if not selected_indices:
            logger.info("No laps selected for deletion.")
            return

        data = dict(self.lap_times_source.data)
        for idx in sorted(selected_indices, reverse=True):
            lap_number = self.lap_times_source.data["number"][idx]
            logger.info("Deleting lap number: %d", lap_number)
            self.app.gt7comm.session.delete_lap(lap_number)

            for key in data.keys():
                data[key] = np.delete(data[key], idx)

            logger.info(f"Deleted lap {lap_number}.")

        self.lap_times_source.data = data
        self.lap_times_source.selected.indices = []  # Clear selection
