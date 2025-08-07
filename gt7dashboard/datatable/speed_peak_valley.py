import logging
from bokeh.models import ColumnDataSource, TableColumn, DataTable, ImportedStyleSheet
from gt7dashboard.gt7lap import Lap


logger = logging.getLogger("SpeedPeakValleyDataTable")
logger.setLevel(logging.DEBUG)


class SpeedPeakValleyDataTable(object):
    def __init__(self, app):
        self.app = app

        dtstylesheet = ImportedStyleSheet(url="gt7dashboard/static/css/styles.css")

        self.speed_peak_valley_source = ColumnDataSource(
            data=dict(
                metric=["Peak Speed", "Valley Speed", "Speed Difference"],
                last_lap=[0, 0, 0],
                reference_lap=[0, 0, 0],
                difference=[0, 0, 0],
            )
        )

        self.datatable = DataTable(
            source=self.speed_peak_valley_source,
            columns=[
                TableColumn(field="metric", title="Metric", width=120),
                TableColumn(field="last_lap", title="Last Lap", width=80),
                TableColumn(field="reference_lap", title="Reference", width=80),
                TableColumn(field="difference", title="Diff", width=60),
            ],
            width=340,
            height=125,
            index_position=None,
            header_row=True,
            selectable=False,
            editable=False,
            sortable=False,
            css_classes=["speed-peak-valley-table"],
            stylesheets=[dtstylesheet],
        )

    def update_speed_peak_valley_data(self, last_lap: Lap, reference_lap: Lap):
        """Update the speed peak and valley data table"""
        if not last_lap:
            # No data available
            self.speed_peak_valley_source.data = dict(
                metric=["Peak Speed", "Valley Speed", "Speed Difference"],
                last_lap=["--", "--", "--"],
                reference_lap=["--", "--", "--"],
                difference=["--", "--", "--"],
            )
            return

        # Get peak and valley data for last lap
        last_peak = max(last_lap.data_speed) if last_lap.data_speed else 0
        last_valley = min(last_lap.data_speed) if last_lap.data_speed else 0
        last_diff = last_peak - last_valley

        if reference_lap and reference_lap.data_speed:
            # Get peak and valley data for reference lap
            ref_peak = max(reference_lap.data_speed)
            ref_valley = min(reference_lap.data_speed)
            ref_diff = ref_peak - ref_valley

            # Calculate differences
            peak_diff = last_peak - ref_peak
            valley_diff = last_valley - ref_valley
            speed_diff_diff = last_diff - ref_diff

            self.speed_peak_valley_source.data = dict(
                metric=["Peak Speed", "Valley Speed", "Speed Difference"],
                last_lap=[f"{last_peak:.1f}", f"{last_valley:.1f}", f"{last_diff:.1f}"],
                reference_lap=[
                    f"{ref_peak:.1f}",
                    f"{ref_valley:.1f}",
                    f"{ref_diff:.1f}",
                ],
                difference=[
                    f"{peak_diff:+.1f}" if peak_diff != 0 else "0.0",
                    f"{valley_diff:+.1f}" if valley_diff != 0 else "0.0",
                    f"{speed_diff_diff:+.1f}" if speed_diff_diff != 0 else "0.0",
                ],
            )
        else:
            # Only last lap data available
            self.speed_peak_valley_source.data = dict(
                metric=["Peak Speed", "Valley Speed", "Speed Difference"],
                last_lap=[f"{last_peak:.1f}", f"{last_valley:.1f}", f"{last_diff:.1f}"],
                reference_lap=["--", "--", "--"],
                difference=["--", "--", "--"],
            )
