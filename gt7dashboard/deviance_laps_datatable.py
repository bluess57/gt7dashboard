from bokeh.models import TableColumn, DataTable, ColumnDataSource, ImportedStyleSheet


class deviance_laps_datatable:
    def __init__(self):
        self.columns = [
            TableColumn(field="number", title="Lap"),
            TableColumn(field="title", title="Time"),
        ]

        dtstylesheet = ImportedStyleSheet(url="gt7dashboard/static/css/styles.css")
        self.lap_times_source = ColumnDataSource(data=dict(number=[], title=[]))
        self.dt_lap_times = DataTable(
            name="3 Fastest Lap Times",
            header_row=True,
            source=self.lap_times_source,
            columns=self.columns,
            index_position=None,
            width=200,
            autosize_mode="fit_columns",
            stylesheets=[dtstylesheet],
            selectable=False,
        )
