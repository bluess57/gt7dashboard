import logging
from typing import List
from bokeh.models import ColumnDataSource, TableColumn, DataTable, ImportedStyleSheet
from gt7dashboard import gt7helper
from gt7dashboard.gt7lap import Lap
from gt7dashboard.gt7performance_monitor import performance_monitor
from gt7dashboard.gt7settings import get_log_level
import numpy as np

logger = logging.getLogger(__name__)
logger.setLevel(get_log_level())


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
            TableColumn(field="tyrespinning", title="Tyre Spin"),
            TableColumn(field="tyreoverheated", title="Tyre Overheat"),
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

    def add_lap(self, lap, doc=None):
        def do_add():
            logger.debug("RaceTimeDataTable Adding lap: %s", lap)
            lap_dict = lap.lap_to_dict()
            logger.debug("lap_dict: %s", lap_dict)

            data = self.lap_times_source.data
            for key in data.keys():
                if key == "index":
                    logger.debug("Skipping 'index' key")
                    continue
                if lap_dict.get(key, None) == None:
                    logger.warning("Lap data missing at key: %s", key)
                    break
                data[key] = np.append(data[key], lap_dict.get(key, None))

            self.lap_times_source.data = dict(data)
            self.dt_lap_times.source = self.lap_times_source
            logger.info("Finished Lap added")

        if doc is not None:
            doc.add_next_tick_callback(do_add)
        else:
            logger.debug("No document provided, adding lap immediately.")
            do_add()

    @performance_monitor
    def show_laps(self, laps: List[Lap]):
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
