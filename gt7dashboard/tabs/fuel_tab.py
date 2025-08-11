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
            <li><b>Fuel Used:</b> Total fuel consumed during the lap</li>
            <li><b>Fuel per Lap:</b> Average consumption rate</li>
            <li><b>Fuel per Minute:</b> Consumption rate over time</li>
            <li><b>Estimated Range:</b> Estimated laps/minutes remaining with current fuel level</li>
        </ul>
        """,
            width=450,
        )

        # Create data source for fuel table
        self.fuel_data_source = ColumnDataSource(
            data={"metric": [], "value": [], "unit": []}
        )

        # Define table columns
        columns = [
            TableColumn(field="metric", title="Metric", width=200),
            TableColumn(field="value", title="Value", width=100),
            TableColumn(field="unit", title="Unit", width=100),
        ]

        dtstylesheet = ImportedStyleSheet(url="gt7dashboard/static/css/styles.css")

        # Create fuel data table
        self.fuel_data_table = DataTable(
            source=self.fuel_data_source,
            columns=columns,
            width=450,
            height=300,
            selectable=False,
            index_position=None,
            sortable=False,
            autosize_mode="fit_columns",
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
        """Extract fuel consumption data from a lap object"""
        try:
            fuel_data = {"metrics": [], "values": [], "units": []}

            # Add lap identification
            if hasattr(lap, "number") and lap.number:
                fuel_data["metrics"].append("Lap Number")
                fuel_data["values"].append(str(lap.number))
                fuel_data["units"].append("")

            if hasattr(lap, "title") and lap.title:
                fuel_data["metrics"].append("Lap Title")
                fuel_data["values"].append(lap.title)
                fuel_data["units"].append("")

            # Lap time
            if hasattr(lap, "lap_time") and lap.lap_time > 0:
                fuel_data["metrics"].append("Lap Time")
                fuel_data["values"].append(f"{lap.lap_time:.3f}")
                fuel_data["units"].append("s")

            # Fuel consumed (if available)
            if hasattr(lap, "fuel_consumed") and lap.fuel_consumed is not None:
                fuel_data["metrics"].append("Fuel Used")
                fuel_data["values"].append(f"{lap.fuel_consumed:.2f}")
                fuel_data["units"].append("L")

                # Calculate fuel consumption rate if lap time is available
                if hasattr(lap, "lap_time") and lap.lap_time > 0:
                    fuel_per_minute = (lap.fuel_consumed / lap.lap_time) * 60
                    fuel_data["metrics"].append("Fuel per Minute")
                    fuel_data["values"].append(f"{fuel_per_minute:.3f}")
                    fuel_data["units"].append("L/min")

            # Current fuel level from telemetry data
            if hasattr(lap, "data_fuel_capacity") and lap.data_fuel_capacity:
                try:
                    # Get the last fuel reading from the lap
                    current_fuel = float(lap.data_fuel_capacity[-1])
                    fuel_data["metrics"].append("Fuel Level (End)")
                    fuel_data["values"].append(f"{current_fuel:.2f}")
                    fuel_data["units"].append("L")

                    # Get starting fuel level
                    start_fuel = float(lap.data_fuel_capacity[0])
                    fuel_data["metrics"].append("Fuel Level (Start)")
                    fuel_data["values"].append(f"{start_fuel:.2f}")
                    fuel_data["units"].append("L")

                    # Calculate fuel consumed from telemetry
                    fuel_consumed_calc = start_fuel - current_fuel
                    if fuel_consumed_calc > 0:
                        fuel_data["metrics"].append("Fuel Used (Calculated)")
                        fuel_data["values"].append(f"{fuel_consumed_calc:.2f}")
                        fuel_data["units"].append("L")

                        # Estimate remaining laps
                        if current_fuel > 0 and fuel_consumed_calc > 0:
                            estimated_laps = current_fuel / fuel_consumed_calc
                            fuel_data["metrics"].append("Estimated Laps Remaining")
                            fuel_data["values"].append(f"{estimated_laps:.1f}")
                            fuel_data["units"].append("laps")

                except (IndexError, ValueError, TypeError) as e:
                    logger.debug(f"Error processing fuel capacity data: {e}")

            # Car information
            if hasattr(lap, "car_id") and lap.car_id:
                from gt7dashboard.gt7car import car_name

                fuel_data["metrics"].append("Car")
                fuel_data["values"].append(car_name(lap.car_id))
                fuel_data["units"].append("")

            # If no fuel data was found, show a message
            if len(fuel_data["metrics"]) <= 2:  # Only lap number and title
                fuel_data["metrics"].append("Fuel Data")
                fuel_data["values"].append("No fuel data available")
                fuel_data["units"].append("")

            return fuel_data

        except Exception as e:
            logger.error(f"Error extracting fuel data: {e}")
            return {
                "metrics": ["Error"],
                "values": [f"Error extracting fuel data: {str(e)}"],
                "units": [""],
            }

    @linear()
    def update_fuel_map(self, step=None):
        """Update the fuel data table with current data"""
        logger.debug(
            f"update_fuel_map called with {len(self.app.gt7comm.session.laps)} laps"
        )

        if len(self.app.gt7comm.session.laps) == 0:
            # Clear the table when no laps are available
            self.fuel_data_source.data = {
                "metric": ["Status"],
                "value": ["No lap data available"],
                "unit": [""],
            }
            return

        # Get the most recent lap (last in the list)
        last_lap = self.app.gt7comm.session.laps[-1]

        # Only update if the lap has changed
        if last_lap == self.stored_fuel_map:
            return
        else:
            self.stored_fuel_map = last_lap

        try:
            # Extract fuel data from the lap
            fuel_data = self.extract_fuel_data(last_lap)

            # Update the data source
            self.fuel_data_source.data = {
                "metric": fuel_data["metrics"],
                "value": fuel_data["values"],
                "unit": fuel_data["units"],
            }

            logger.debug(
                f"Updated fuel table with {len(fuel_data['metrics'])} data points from lap: {getattr(last_lap, 'title', 'Unknown')}"
            )

        except Exception as e:
            logger.error(f"Error updating fuel table: {e}")
            self.fuel_data_source.data = {
                "metric": ["Error"],
                "value": [f"Error loading fuel data: {str(e)}"],
                "unit": [""],
            }

    def get_lap_fuel_summary(self):
        """Get a summary of fuel consumption across all laps"""
        laps = self.app.gt7comm.session.laps
        if not laps:
            return None

        try:
            total_fuel = sum(
                getattr(lap, "fuel_consumed", 0)
                for lap in laps
                if hasattr(lap, "fuel_consumed")
            )
            total_time = sum(
                getattr(lap, "lap_time", 0) for lap in laps if hasattr(lap, "lap_time")
            )
            avg_fuel_per_lap = total_fuel / len(laps) if laps else 0
            avg_fuel_per_minute = (
                (total_fuel / total_time) * 60 if total_time > 0 else 0
            )

            return {
                "total_fuel": total_fuel,
                "total_time": total_time,
                "avg_fuel_per_lap": avg_fuel_per_lap,
                "avg_fuel_per_minute": avg_fuel_per_minute,
                "lap_count": len(laps),
            }
        except Exception as e:
            logger.error(f"Error calculating fuel summary: {e}")
            return None

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
        ]

        for attr in fuel_attributes:
            if hasattr(lap, attr):
                value = getattr(lap, attr)
                logger.debug(f"  {attr}: {value} (type: {type(value)})")
            else:
                logger.debug(f"  {attr}: NOT FOUND")

        # Check if there's any fuel-related telemetry data
        if hasattr(lap, "__dict__"):
            fuel_related = [k for k in lap.__dict__.keys() if "fuel" in k.lower()]
            logger.debug(f"  All fuel-related attributes: {fuel_related}")

    def update_fuel_map(self):
        """Update the fuel data table with current data"""
        logger.debug(
            f"update_fuel_map called with {len(self.app.gt7comm.session.laps)} laps"
        )

        if len(self.app.gt7comm.session.laps) == 0:
            # Clear the table when no laps are available
            self.fuel_data_source.data = {
                "metric": ["Status"],
                "value": ["No lap data available"],
                "unit": [""],
            }
            return

        # Get the most recent lap (last in the list)
        last_lap = self.app.gt7comm.session.laps[-1]
        self.debug_lap_fuel_data(last_lap)  # Add this line for debugging

        # Only update if the lap has changed
        if last_lap == self.stored_fuel_map:
            return
        else:
            self.stored_fuel_map = last_lap

        try:
            # Extract fuel data from the lap
            fuel_data = self.extract_fuel_data(last_lap)

            # Update the data source
            self.fuel_data_source.data = {
                "metric": fuel_data["metrics"],
                "value": fuel_data["values"],
                "unit": fuel_data["units"],
            }

            logger.debug(
                f"Updated fuel table with {len(fuel_data['metrics'])} data points from lap: {getattr(last_lap, 'title', 'Unknown')}"
            )

        except Exception as e:
            logger.error(f"Error updating fuel table: {e}")
            self.fuel_data_source.data = {
                "metric": ["Error"],
                "value": [f"Error loading fuel data: {str(e)}"],
                "unit": [""],
            }
