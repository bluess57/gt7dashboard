import logging
import os
from bokeh.plotting import curdoc
from bokeh.models import Div, GlobalImportedStyleSheet, ImportedStyleSheet
from bokeh.layouts import column

from gt7dashboard import gt7communication
from gt7dashboard.tab_manager import TabManager
from gt7dashboard.gt7helper import load_laps_from_pickle

# Set up logging
logger = logging.getLogger('main.py')
logger.setLevel(logging.DEBUG)

# Create the application
class GT7Application:
    def __init__(self):
                # Set up tabs
        # Set up GT7 communication
        playstation_ip = os.environ.get("GT7_PLAYSTATION_IP", "255.255.255.255")
        self.gt7comm = gt7communication.GT7Communication(playstation_ip)
        self.gt7comm.set_on_connected_callback(self.update_header)
        self.gt7comm.set_lap_callback(self.on_laps_loaded)

        # Load laps if specified
        load_laps_path = os.environ.get("GT7_LOAD_LAPS_PATH")
        if load_laps_path:
            
            laps = load_laps_from_pickle(load_laps_path)
            self.gt7comm.session.load_laps(
                laps, replace_other_laps=True
            )

        self.tab_manager = TabManager(self)
        self.tabs = self.tab_manager.create_tabs()


        # Initialize time table tab with laps if any were loaded
        if load_laps_path and hasattr(self.tab_manager, 'time_table_tab'):
            laps = self.gt7comm.session.get_laps()
            if laps:
                self.tab_manager.time_table_tab.show_laps(laps)

        # Start communication
        self.gt7comm.start()


    def setup_document(self, doc):
        doc.theme = 'carbon'

        css_path = "gt7dashboard/static/css/styles.css"
        globalStylesheet = GlobalImportedStyleSheet(url=css_path)
        doc.add_root(globalStylesheet)

        header = self.create_header()

        # Create a layout with header and tabs
        main_layout = column(
            header,
            self.tabs,
            sizing_mode="stretch_both",
            name="main",
            stylesheets=[globalStylesheet]
        )

        # Add the layout to the document
        doc.add_root(main_layout)
        doc.title = "GT7 Dashboard"

        # Set up periodic callbacks
        doc.add_periodic_callback(self.tab_manager.race_tab.update_lap_change, 1000)
        #doc.add_periodic_callback(lambda step=None: self.tab_manager.fuel_tab.update_fuel_map(step), 5000)
        #doc.add_periodic_callback(self.update_header, 5000)  # Update header every 5 seconds

    def create_header(self):
        """Create a header showing connection status and PS5 IP"""

        # Create the header div with full width
        self.header = Div(
            name="gt7-header",
            text=self.update_connection_status(),
            height=30,
            sizing_mode="stretch_width"
            )

        return self.header

    def update_connection_status(self):
        """Generate the HTML content for the header"""
        is_connected = self.gt7comm.is_connected()
        status_color = "green" if is_connected else "red"
        status_icon = "✓" if is_connected else "✗"
        status_text = "Connected" if is_connected else "Not Connected"

        return f"""
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 5px 10px;
                   border-bottom: 1px solid #ddd; 
                   width: 100%; box-sizing: border-box; position: relative; left: 0; right: 0;">
            <div style="margin-right: 20px; flex: 0 0 auto;">
                <span style="font-weight: bold;">GT7 Dashboard</span>
            </div>
            <div style="flex-grow: 1; text-align: center;">
                <span style="color: {status_color}; font-weight: bold;">{status_icon} {status_text}</span>
            </div>
            <div style="margin-left: 20px; flex: 0 0 auto;">
                PS5 IP: {self.gt7comm.playstation_ip}
            </div>
        </div>
        """

    def update_header(self, step=None):
        """Update the header with current connection status"""
        if hasattr(self, 'header'):
            self.header.text = self.update_connection_status()

    def on_laps_loaded(self, laps):
        if hasattr(self, "race_time_data_table_tab"):
            self.race_time_data_table_tab.show_laps(laps)

    def delete_lap(self, lap_number):
        """
        Delete a lap by its number from the loaded laps.
        Updates all tabs that display lap data.
        """
        self.gt7comm.session.delete_lap(lap_number)

        # Update time table tab and other relevant tabs
        if hasattr(self.tab_manager, 'time_table_tab'):
            self.tab_manager.time_table_tab.show_laps(self.gt7comm.session.laps)
        if hasattr(self.tab_manager, 'race_tab'):
            self.tab_manager.race_tab.update_lap_change()

        logger.info(f"Deleted lap {lap_number}. Laps before: {original_count}, after: {new_count}")

# Create and set up the application
app = GT7Application()
app.setup_document(curdoc())