import logging
import os
from bokeh.plotting import curdoc
from bokeh.models import Div, GlobalImportedStyleSheet
from bokeh.layouts import column, row

from gt7dashboard import gt7communication
from gt7dashboard.tab_manager import TabManager
from gt7dashboard.gt7lapstorage import load_laps_from_pickle


# Set up logging
logger = logging.getLogger("main")
logger.setLevel(logging.INFO)


# Create the application
class GT7Application:
    def __init__(self):
        # Set up tabs
        # Set up GT7 communication
        playstation_ip = os.environ.get("GT7_PLAYSTATION_IP", "255.255.255.255")
        self.gt7comm = gt7communication.GT7Communication(playstation_ip)
        self.gt7comm.set_on_connected_callback(self.update_header)

        self.tab_manager = TabManager(self)
        self.tabs = self.tab_manager.create_tabs()

    def setup_document(self, doc):
        doc.theme = "carbon"

        css_path = "gt7dashboard/static/css/styles.css"
        globalStylesheet = GlobalImportedStyleSheet(url=css_path)
        doc.add_root(globalStylesheet)

        header = self.create_header()

        self.heartbeat_indicator = Div(
            text='<span id="heartbeat-dot" title="Heart beat indicator, when data is received will flash green." style="font-size:2em; color:gray;">&#10084;</span>'
        )

        # Create a layout with header and tabs
        main_layout = column(
            row(header, self.heartbeat_indicator),
            row(self.tabs),
            sizing_mode="stretch_both",
            name="main",
            stylesheets=[globalStylesheet],
        )

        # Add the layout to the document
        doc.add_root(main_layout)
        doc.title = "GT7 Dashboard"

        # Revisit if periodic callbacks are needed, trying not to use them
        # doc.add_periodic_callback(self.tab_manager.race_tab.update_lap_change, 1000)
        # doc.add_periodic_callback(lambda step=None: self.tab_manager.fuel_tab.update_fuel_map(step), 5000)
        # doc.add_periodic_callback(self.update_header, 5000)  # Update header every 5 seconds

        self.gt7comm.set_on_heartbeat_callback(self.show_heartbeat(doc))

        # Start communication with PS5
        logger.info(
            f"Starting GT7 communication with PS5 at {self.gt7comm.playstation_ip}"
        )

        self.gt7comm.start()

    def create_header(self):
        """Create a header showing connection status and PS5 IP"""

        # Create the header div with full width
        self.header = Div(
            name="gt7-header",
            text=self.update_connection_status(),
            height=30,
            sizing_mode="stretch_width",
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
                   width: fit-content; box-sizing: border-box; position: relative; left: 0; right: 0;">
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
        if hasattr(self, "header"):
            self.header.text = self.update_connection_status()

    def show_heartbeat(self, doc):
        def update():
            self.heartbeat_indicator.text = '<span id="heartbeat-dot" style="font-size:2em; color:lime;">&#10084;</span>'
            doc.add_timeout_callback(
                lambda: self.heartbeat_indicator.update(
                    text='<span id="heartbeat-dot" style="font-size:2em; color:gray;">&#10084;</span>'
                ),
                500,
            )

        doc.add_next_tick_callback(update)


# Create and set up the application
app = GT7Application()
app.setup_document(curdoc())
