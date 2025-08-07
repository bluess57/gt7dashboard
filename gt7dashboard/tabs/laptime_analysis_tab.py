import csv
import os
import logging
import html
from typing import List, Dict

from bokeh.layouts import layout, column, row
from bokeh.models import (
    Div,
    Button,
    TabPanel,
    ColumnDataSource,
    DataTable,
    TableColumn,
    NumberFormatter,
    HTMLTemplateFormatter,
    HoverTool,
)

from ..gt7help import TIME_TABLE
from ..gt7lap import Lap
from .GT7Tab import GT7Tab

logger = logging.getLogger("laptime_analysis_tab")
logger.setLevel(logging.DEBUG)


class LapTimeAnalysisTab(GT7Tab):
    """Race Time Table tab for displaying and analyzing lap times"""

    def __init__(self, app_instance):
        """Initialize the race time table tab"""
        super().__init__("Analyze Lap Times")
        self.app = app_instance
        self.create_components()
        self.layout = self.create_layout()

    def create_components(self):
        """Create all UI components for this tab"""
        # Create header and info components
        self.title_div = Div(text="<h3>Lap Time Analysis</h3>", width=400)
        self.description_div = Div(
            text="""
            <p>This tab shows detailed lap time information and analysis.</p>
            <p>Select rows in the table to highlight those laps in the charts.</p>
        """,
            width=600,
        )

        # Create help tooltip - use a div with HTML title attribute instead
        self.help_div = Div(
            text=f'<div style="width:20px; height:20px; border-radius:50%; background:#f5f5f5; border:1px solid #ddd; text-align:center; line-height:20px;" title="{html.escape(TIME_TABLE)}">?</div>',
            width=20,
        )

        # Create control buttons
        self.export_button = Button(
            label="Export Times", button_type="success", width=120
        )
        self.clear_selection_button = Button(
            label="Clear Selection", button_type="warning", width=120
        )

        # Create the lap times table
        self.create_lap_times_table()

        # Create statistics components
        self.stats_div = Div(text="<h4>Lap Statistics</h4>", width=400)
        self.lap_count_div = Div(text="Total Laps: 0", width=200)
        self.best_lap_div = Div(text="Best Lap: --:--:---", width=200)
        self.avg_lap_div = Div(text="Average: --:--:---", width=200)

        # Connect event handlers
        self.export_button.on_click(self.export_handler)
        self.clear_selection_button.on_click(self.clear_selection_handler)
        self.lap_times_source.selected.on_change(
            "indices", self.table_row_selection_callback
        )

    def create_lap_times_table(self):
        """Create the lap times data table"""
        # Create data source for lap times
        self.lap_times_source = ColumnDataSource(
            data={
                "index": [],
                "car": [],
                "time": [],
                "number": [],
                "title": [],
                "diff_to_best": [],
                "diff_to_prev": [],
                "sector1": [],
                "sector2": [],
                "sector3": [],
            }
        )

        # Create table columns
        time_formatter = HTMLTemplateFormatter(
            template='<div style="color: <%= value < 0 ? "red" : "green" %>"><%= value %></div>'
        )

        columns = [
            TableColumn(field="number", title="Lap", width=40),
            TableColumn(field="title", title="Title", width=120),
            TableColumn(field="time", title="Time", width=80),
            TableColumn(field="car", title="Car", width=100),
            TableColumn(
                field="diff_to_best", title="Δ Best", formatter=time_formatter, width=60
            ),
            TableColumn(
                field="diff_to_prev", title="Δ Prev", formatter=time_formatter, width=60
            ),
        ]

        # Add sector columns if available in the data
        sector_columns = [
            TableColumn(field="sector1", title="S1", width=60),
            TableColumn(field="sector2", title="S2", width=60),
            TableColumn(field="sector3", title="S3", width=60),
        ]

        # Create the data table
        self.lap_times_table = DataTable(
            source=self.lap_times_source,
            columns=columns + sector_columns,
            width=600,
            height=400,
            sortable=True,
            selectable=True,
            index_position=None,
        )

    def create_layout(self):
        """Create layout for this tab"""
        # Statistics row
        stats_row = row(
            self.lap_count_div,
            self.best_lap_div,
            self.avg_lap_div,
            sizing_mode="stretch_width",
        )

        # Button row
        button_row = row(
            self.export_button, self.clear_selection_button, sizing_mode="stretch_width"
        )

        # Create the layout
        return layout(
            [
                [self.title_div],
                [self.description_div],
                [button_row],
                [self.lap_times_table, self.help_div],
                [stats_row],
            ],
            sizing_mode="stretch_width",
        )

    def show_laps(self, laps: List[Lap]):
        """Update the lap times table with current lap data"""
        if not laps:
            return

        # Process lap data
        processed_data = self._process_lap_data(laps)

        # Update the data source
        self.lap_times_source.data = processed_data

        # Update statistics
        self._update_statistics(laps)

    def _format_time(self, time_value):
        """Format time value as MM:SS.mmm"""
        if time_value is None:
            return "--:--:---"

        # If time is a list, use the first element
        if isinstance(time_value, list):
            if not time_value:  # Empty list
                return "--:--:---"
            time_value = time_value[0]  # Use first element

        try:
            # Convert to milliseconds if in seconds
            if time_value < 1000:  # Likely in seconds
                time_value = int(time_value * 1000)

            # Calculate components using regular division instead of floor division
            milliseconds = int(time_value % 1000)
            total_seconds = int(time_value / 1000)
            minutes = int(total_seconds / 60)
            seconds = int(total_seconds % 60)

            return f"{minutes}:{seconds:02d}.{milliseconds:03d}"
        except Exception as e:
            logger.error(f"Error formatting time {time_value}: {e}")
            return "--:--:---"

    def _process_lap_data(self, laps: List[Lap]) -> Dict:
        """Process lap data for display in the table"""
        data = {
            "index": [],
            "car": [],
            "time": [],
            "number": [],
            "title": [],
            "diff_to_best": [],
            "diff_to_prev": [],
            "sector1": [],
            "sector2": [],
            "sector3": [],
        }

        if not laps:
            return data

        # Find best lap time for comparisons
        valid_lap_times = []
        for lap in laps:
            try:
                # Get lap_time attribute safely
                lap_time = getattr(lap, "lap_time", None)
                if lap_time is None:
                    lap_time = getattr(lap, "time", 0)

                # Handle list case
                if isinstance(lap_time, list):
                    if lap_time:  # Non-empty list
                        lap_time = lap_time[0]  # Use first element
                    else:
                        lap_time = 0

                if lap_time > 0:
                    valid_lap_times.append(lap_time)
            except Exception as e:
                logger.error(f"Error processing lap time: {e}")

        best_lap_time = min(valid_lap_times) if valid_lap_times else 0

        # Process each lap with error handling
        for i, lap in enumerate(laps):
            try:
                # Get lap attributes safely
                lap_time = getattr(lap, "lap_time", None)
                if lap_time is None:
                    lap_time = getattr(lap, "time", 0)

                # Handle list case
                if isinstance(lap_time, list):
                    if lap_time:  # Non-empty list
                        lap_time = lap_time[0]  # Use first element
                    else:
                        lap_time = 0

                # Get car name safely
                car_name = ""
                try:
                    car_name = (
                        car_name(lap.car_id)
                        if callable(getattr(lap, "car_name", None))
                        else str(getattr(lap, "car", ""))
                    )
                except Exception:
                    car_name = "Unknown"

                # Format lap time using our custom method
                formatted_time = self._format_time(lap_time)

                # Add basic lap data
                data["index"].append(i)
                data["car"].append(car_name)
                data["time"].append(formatted_time)
                data["number"].append(getattr(lap, "number", i + 1))
                data["title"].append(getattr(lap, "title", f"Lap {i+1}"))

                # Calculate difference to best lap
                if best_lap_time > 0 and lap_time > 0:
                    diff_to_best = lap_time - best_lap_time
                    data["diff_to_best"].append(
                        f"{'+' if diff_to_best > 0 else ''}{diff_to_best/1000:.3f}"
                    )
                else:
                    data["diff_to_best"].append("")

                # Calculate difference to previous lap - safely handle list case
                if i > 0 and lap_time > 0:
                    prev_lap_time = getattr(laps[i - 1], "lap_time", 0)
                    if isinstance(prev_lap_time, list) and prev_lap_time:
                        prev_lap_time = prev_lap_time[0]

                    if prev_lap_time > 0:
                        diff_to_prev = lap_time - prev_lap_time
                        data["diff_to_prev"].append(
                            f"{'+' if diff_to_prev > 0 else ''}{diff_to_prev/1000:.3f}"
                        )
                    else:
                        data["diff_to_prev"].append("")
                else:
                    data["diff_to_prev"].append("")

                # Add sector times if available - with format_sector_time fallback
                for sector_num in range(1, 4):
                    sector_key = f"sector{sector_num}"
                    try:
                        sector_time = "--:--"
                        if hasattr(lap, sector_key):
                            sector_value = getattr(lap, sector_key)
                            if sector_value:
                                sector_time = self._format_time(sector_value)
                        data[sector_key].append(sector_time)
                    except Exception:
                        data[sector_key].append("--:--")
            except Exception as e:
                logger.error(f"Error processing lap {i}: {e}")
                # Add placeholder values on error
                for key in data:
                    if key == "index":
                        data[key].append(i)
                    elif key == "number":
                        data[key].append(i + 1)
                    elif key == "time":
                        data[key].append("--:--:---")
                    else:
                        data[key].append("")

        return data

    def _update_statistics(self, laps: List[Lap]):
        """Update lap statistics displays"""
        if not laps:
            self.lap_count_div.text = "Total Laps: 0"
            self.best_lap_div.text = "Best Lap: --:--:---"
            self.avg_lap_div.text = "Average: --:--:---"
            return

        # Process lap times safely
        valid_lap_times = []
        for lap in laps:
            try:
                lap_time = getattr(lap, "lap_time", None)
                if lap_time is None:
                    lap_time = getattr(lap, "time", 0)

                # Handle list case
                if isinstance(lap_time, list):
                    if lap_time:  # Non-empty list
                        lap_time = lap_time[0]  # Use first element
                    else:
                        lap_time = 0

                if lap_time > 0:
                    valid_lap_times.append(lap_time)
            except Exception as e:
                logger.error(f"Error extracting lap time: {e}")

        valid_count = len(valid_lap_times)

        # Find best lap
        if valid_count > 0:
            best_lap_time = min(valid_lap_times)
            best_lap_time_formatted = self._format_time(best_lap_time)

            # Calculate average lap time
            avg_time = sum(valid_lap_times) / valid_count
            avg_time_formatted = self._format_time(avg_time)
        else:
            best_lap_time_formatted = "--:--:---"
            avg_time_formatted = "--:--:---"

        # Update display
        self.lap_count_div.text = f"Total Laps: {len(laps)}"
        self.best_lap_div.text = f"Best Lap: {best_lap_time_formatted}"
        self.avg_lap_div.text = f"Average: {avg_time_formatted}"

    def export_handler(self, event):
        """Export lap times to CSV"""
        from datetime import datetime

        if not self.lap_times_source.data["time"]:
            return

        # Create filename with timestamp
        filename = f"lap_times_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(os.getcwd(), "data", filename)

        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Write CSV file
        with open(filepath, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(
                [
                    "Lap",
                    "Title",
                    "Time",
                    "Car",
                    "Diff to Best",
                    "Diff to Prev",
                    "S1",
                    "S2",
                    "S3",
                ]
            )

            # Write data rows
            for i in range(len(self.lap_times_source.data["time"])):
                writer.writerow(
                    [
                        self.lap_times_source.data["number"][i],
                        self.lap_times_source.data["title"][i],
                        self.lap_times_source.data["time"][i],
                        self.lap_times_source.data["car"][i],
                        self.lap_times_source.data["diff_to_best"][i],
                        self.lap_times_source.data["diff_to_prev"][i],
                        self.lap_times_source.data["sector1"][i],
                        self.lap_times_source.data["sector2"][i],
                        self.lap_times_source.data["sector3"][i],
                    ]
                )

        logger.info(f"Exported lap times to {filepath}")

    def clear_selection_handler(self, event):
        """Clear table selection"""
        self.lap_times_source.selected.indices = []

    def table_row_selection_callback(self, attrname, old, new):
        """Handle selecting rows in the lap times table"""
        selection_indices = self.lap_times_source.selected.indices
        if not selection_indices:
            return

        logger.info(f"Selected rows: {selection_indices}")

        # Notify the race tab to highlight selected laps
        # This will require integration with the main app
        if hasattr(self.app, "tab_manager") and hasattr(
            self.app.tab_manager, "race_tab"
        ):
            self.app.tab_manager.race_tab.highlight_selected_laps(selection_indices)

    def update_lap_data(self, step=None):
        """Periodic update of lap data"""
        laps = self.app.gt7comm.session.get_laps()
        self.show_laps(laps)
