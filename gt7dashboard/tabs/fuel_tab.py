import logging
from bokeh.layouts import layout
from bokeh.models import Div, TabPanel
from bokeh.driving import linear

from gt7dashboard import gt7diagrams

logger = logging.getLogger("fuel_tab")
logger.setLevel(logging.DEBUG)


class FuelTab:
    """Fuel consumption tab for GT7 Dashboard"""

    def __init__(self, app_instance):
        """Initialize the fuel tab"""
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
            width=600,
        )

        # Fuel map component
        self.div_fuel_map = Div(width=200, height=125, css_classes=["fuel_map"])

    def create_layout(self):
        """Create layout for this tab"""
        return layout(
            [
                [self.fuel_info_div],
                [self.div_fuel_map],
            ],
            sizing_mode="stretch_width",
        )

    @linear()
    def update_fuel_map(self, step=None):
        """Update the fuel map display with current data"""
        if len(self.app.gt7comm.session.laps) == 0:
            self.div_fuel_map.text = ""
            return

        last_lap = self.app.gt7comm.session.laps[0]

        if last_lap == self.stored_fuel_map:
            return
        else:
            self.stored_fuel_map = last_lap

        self.div_fuel_map.text = gt7diagrams.get_fuel_map_html_table(last_lap)

    def get_tab_panel(self):
        """Create a TabPanel for this tab"""
        return TabPanel(child=self.layout, title="Fuel")
