import logging
from bokeh.layouts import layout, column
from bokeh.models import (
    Div,
    DataTable,
    TableColumn,
    ColumnDataSource,
    ImportedStyleSheet,
)

from bokeh.driving import linear
from .GT7Tab import GT7Tab
from gt7dashboard import gt7diagrams
from gt7dashboard.gt7settings import get_log_level

logger = logging.getLogger("fuel_tab")
logger.setLevel(get_log_level())


class FuelTab(GT7Tab):
    """Fuel consumption tab for GT7 Dashboard"""

    def __init__(self, app_instance):
        """Initialize the fuel tab"""
        super().__init__("Fuel")
        self.app = app_instance
        self.stored_fuel_map = None
        self.create_components()
        self.layout = self.create_layout()

    def create_components(self):
        """Create all UI components for the fuel tab"""

        # Create fuel information div with detailed explanation
        self.fuel_info_div = Div(
            text="""
        <h3>Fuel Consumption</h3>
        <p>This panel shows detailed fuel consumption data for your laps.</p>
        <ul>
            <li><b>Lap Number:</b> Sequential lap identifier</li>
            <li><b>Lap Time:</b> Time taken to complete the lap</li>
            <li><b>Fuel Used:</b> Total fuel consumed during the lap</li>
            <li><b>Fuel per Minute:</b> Consumption rate over time</li>
            <li><b>Car:</b> Vehicle used for the lap</li>
        </ul>
        """,
            width=600,
        )

        # Create data source for fuel table with specific columns
        self.fuel_data_source = ColumnDataSource(
            data={
                "lap_number": [],
                "lap_time": [],
                "fuel_used": [],
                "fuel_per_minute": [],
                "car": [],
            }
        )

        # Define table columns with adjusted widths (total: ~450px)
        columns = [
            TableColumn(field="lap_number", title="Lap #", width=60),
            TableColumn(field="lap_time", title="Time", width=90),
            TableColumn(field="fuel_used", title="Fuel (L)", width=80),
            TableColumn(field="fuel_per_minute", title="L/min", width=70),
            TableColumn(field="car", title="Car", width=250),
        ]

        dtstylesheet = ImportedStyleSheet(url="gt7dashboard/static/css/styles.css")

        # Create fuel data table with reduced width
        self.fuel_data_table = DataTable(
            source=self.fuel_data_source,
            columns=columns,
            width=450,  # Reduced from 600
            height=300,
            selectable=False,
            index_position=None,
            sortable=True,
            autosize_mode="none",
            stylesheets=[dtstylesheet],
        )

    def create_layout(self):
        """Create layout for this tab"""
        return layout(
            [
                [self.fuel_info_div],
                [self.fuel_data_table],
            ],
            sizing_mode="stretch_width",
        )

    def extract_fuel_data(self, lap):
        """Extract fuel consumption data from a lap object for specific columns"""
        try:
            # Initialize data with default values
            lap_data = {
                "lap_number": "N/A",
                "lap_time": "N/A",
                "fuel_used": "N/A",
                "fuel_per_minute": "N/A",
                "car": "N/A",
            }

            # Lap Number
            if hasattr(lap, "number") and lap.number:
                lap_data["lap_number"] = str(lap.number)

            if (
                lap_data["lap_time"] == "N/A"
                and hasattr(lap, "lap_finish_time")
                and lap.lap_finish_time > 0
            ):
                total_seconds = lap.lap_finish_time / 1000.0
                minutes = int(total_seconds // 60)
                seconds = total_seconds % 60
                lap_data["lap_time"] = f"{minutes}:{seconds:06.3f}"

            # Get lap time in seconds for fuel calculations
            lap_time_seconds = None
            if hasattr(lap, "lap_finish_time") and lap.lap_finish_time > 0:
                lap_time_seconds = lap.lap_finish_time / 1000.0
            elif hasattr(lap, "data_time") and lap.data_time and len(lap.data_time) > 1:
                lap_time_seconds = lap.data_time[-1] - lap.data_time[0]

            # Fuel Used
            fuel_consumed = None
            if (
                hasattr(lap, "fuel_consumed")
                and lap.fuel_consumed is not None
                and lap.fuel_consumed > 0
            ):
                fuel_consumed = lap.fuel_consumed
                lap_data["fuel_used"] = f"{fuel_consumed:.2f}"
            elif (
                hasattr(lap, "data_fuel_capacity")
                and lap.data_fuel_capacity
                and len(lap.data_fuel_capacity) > 1
            ):
                # Calculate from telemetry data
                try:
                    start_fuel = float(lap.data_fuel_capacity[0])
                    end_fuel = float(lap.data_fuel_capacity[-1])
                    fuel_consumed = start_fuel - end_fuel
                    if fuel_consumed > 0:
                        lap_data["fuel_used"] = f"{fuel_consumed:.2f}"
                except (IndexError, ValueError, TypeError):
                    pass

            # Fuel per Minute
            if fuel_consumed and lap_time_seconds and lap_time_seconds > 0:
                fuel_per_minute = (fuel_consumed / lap_time_seconds) * 60
                lap_data["fuel_per_minute"] = f"{fuel_per_minute:.3f}"

            # Car
            if hasattr(lap, "car_id") and lap.car_id:
                try:
                    from gt7dashboard.gt7car import car_name

                    lap_data["car"] = car_name(lap.car_id)
                except:
                    lap_data["car"] = f"Car ID: {lap.car_id}"

            return lap_data

        except Exception as e:
            logger.error(f"Error extracting fuel data: {e}")
            return {
                "lap_number": "Error",
                "lap_time": "Error",
                "fuel_used": "Error",
                "fuel_per_minute": "Error",
                "car": str(e),
            }

    def update_fuel_map(self, step=None):
        """Update the fuel data table with current data (removed @linear decorator)"""
        logger.debug(
            f"update_fuel_map called with {len(self.app.gt7comm.session.laps)} laps"
        )

        if len(self.app.gt7comm.session.laps) == 0:
            # Clear the table when no laps are available
            self.fuel_data_source.data = {
                "lap_number": ["No Data"],
                "lap_time": ["No laps"],
                "fuel_used": ["available"],
                "fuel_per_minute": [""],
                "car": [""],
            }
            return

        # Get the most recent lap (last in the list)
        last_lap = self.app.gt7comm.session.laps[-1]

        # Add debug method if it doesn't exist
        if hasattr(self, "debug_lap_fuel_data"):
            self.debug_lap_fuel_data(last_lap)

        # Only update if the lap has changed
        if last_lap == self.stored_fuel_map:
            return
        else:
            self.stored_fuel_map = last_lap

        try:
            # Extract fuel data from the lap
            lap_data = self.extract_fuel_data(last_lap)

            # Update the data source with single row of data
            self.fuel_data_source.data = {
                "lap_number": [lap_data["lap_number"]],
                "lap_time": [lap_data["lap_time"]],
                "fuel_used": [lap_data["fuel_used"]],
                "fuel_per_minute": [lap_data["fuel_per_minute"]],
                "car": [lap_data["car"]],
            }

            logger.debug(
                f"Updated fuel table with data from lap: {getattr(last_lap, 'title', 'Unknown')}"
            )

        except Exception as e:
            logger.error(f"Error updating fuel table: {e}")
            self.fuel_data_source.data = {
                "lap_number": ["Error"],
                "lap_time": ["Error"],
                "fuel_used": ["Error"],
                "fuel_per_minute": ["Error"],
                "car": [str(e)],
            }

    def update_fuel_map_all_laps(self, step=None):
        """Update the fuel data table with all lap data"""
        logger.debug(
            f"update_fuel_map called with {len(self.app.gt7comm.session.laps)} laps"
        )

        if len(self.app.gt7comm.session.laps) == 0:
            self.fuel_data_source.data = {
                "lap_number": ["No Data"],
                "lap_time": ["No laps available"],
                "fuel_used": [""],
                "fuel_per_minute": [""],
                "car": [""],
            }
            return

        try:
            # Extract data for all laps
            all_lap_data = {
                "lap_number": [],
                "lap_time": [],
                "fuel_used": [],
                "fuel_per_minute": [],
                "car": [],
            }

            for lap in self.app.gt7comm.session.laps:
                lap_data = self.extract_fuel_data(lap)
                all_lap_data["lap_number"].append(lap_data["lap_number"])
                all_lap_data["lap_time"].append(lap_data["lap_time"])
                all_lap_data["fuel_used"].append(lap_data["fuel_used"])
                all_lap_data["fuel_per_minute"].append(lap_data["fuel_per_minute"])
                all_lap_data["car"].append(lap_data["car"])

            # Update the data source with all laps
            self.fuel_data_source.data = all_lap_data
            logger.info(
                f"Updated fuel table with {len(self.app.gt7comm.session.laps)} laps"
            )

        except Exception as e:
            logger.error(f"Error updating fuel table: {e}")
            self.fuel_data_source.data = {
                "lap_number": ["Error"],
                "lap_time": ["Error"],
                "fuel_used": ["Error"],
                "fuel_per_minute": ["Error"],
                "car": [str(e)],
            }

    def debug_lap_fuel_data(self, lap):
        """Debug method to check what fuel data is available in a lap"""
        logger.debug(
            f"=== Debugging lap fuel data for: {getattr(lap, 'title', 'Unknown')} ==="
        )

        # Check all attributes that might contain fuel data
        fuel_attributes = [
            "fuel_consumed",
            "data_fuel_capacity",
            "fuel_level",
            "fuel_remaining",
            "fuel_consumption_rate",
            "fuel_per_lap",
            "lap_finish_time",
            "data_time",
        ]

        for attr in fuel_attributes:
            if hasattr(lap, attr):
                value = getattr(lap, attr)
                value_type = type(value)
                if isinstance(value, list):
                    logger.debug(
                        f"  {attr}: {value_type} with {len(value)} items - first: {value[0] if value else 'N/A'}, last: {value[-1] if value else 'N/A'}"
                    )
                else:
                    logger.debug(f"  {attr}: {value} (type: {value_type})")
            else:
                logger.debug(f"  {attr}: NOT FOUND")

        # Check if there's any fuel-related telemetry data
        if hasattr(lap, "__dict__"):
            fuel_related = [k for k in lap.__dict__.keys() if "fuel" in k.lower()]
            logger.debug(f"  All fuel-related attributes: {fuel_related}")

    # Add a method for periodic updates if needed
    @linear()
    def periodic_fuel_update(self, step=None):
        """Periodic update method for use with Bokeh's periodic callback system"""
        self.update_fuel_map()

    # Also add a method to start periodic updates if your app uses them
    def start_periodic_updates(self, period=1000):
        """Start periodic updates for the fuel tab"""
        if hasattr(self.app, "doc") and self.app.doc:
            self.app.doc.add_periodic_callback(self.periodic_fuel_update, period)
