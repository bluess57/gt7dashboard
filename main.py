import logging
import os
from bokeh.plotting import curdoc
from bokeh.models import Div
from gt7dashboard import gt7communication
from gt7dashboard.tab_manager import TabManager
from gt7dashboard.styles import get_header_styles  # Rename this function in styles.py

# Set up logging
logger = logging.getLogger('main.py')
logger.setLevel(logging.DEBUG)

# Create the application
class GT7Application:
    def __init__(self):
        # Set up GT7 communication
        playstation_ip = os.environ.get("GT7_PLAYSTATION_IP", "255.255.255.255")
        self.gt7comm = gt7communication.GT7Communication(playstation_ip)
        
        # Load laps if specified
        load_laps_path = os.environ.get("GT7_LOAD_LAPS_PATH")
        if load_laps_path:
            from gt7dashboard.gt7helper import load_laps_from_pickle
            self.gt7comm.load_laps(
                load_laps_from_pickle(load_laps_path), replace_other_laps=True
            )
            
        # Start communication
        self.gt7comm.start()
        
        # Set up tabs
        self.tab_manager = TabManager(self)
        self.tabs = self.tab_manager.create_tabs()
        
    def setup_document(self, doc):
        # Create a layout with header and tabs
        from bokeh.layouts import column
        
        # Create header (previously footer)
        header = self.create_header()
        
        # Create a layout with header and tabs
        main_layout = column(
            header,     # Put header at the top instead of bottom
            self.tabs,
            sizing_mode="stretch_both"  # Change to stretch_both instead of stretch_width
        )

        # Add the layout to the document
        doc.add_root(main_layout)
        doc.title = "GT7 Dashboard"
        
        # Set up periodic callbacks
        doc.add_periodic_callback(self.tab_manager.race_tab.update_lap_change, 1000)
        #doc.add_periodic_callback(lambda step=None: self.tab_manager.fuel_tab.update_fuel_map(step), 5000)
        doc.add_periodic_callback(self.tab_manager.config_tab.update_connection_status, 5000)
        doc.add_periodic_callback(self.update_header, 5000)  # Update header every 5 seconds

        # Add CSS for header styling
        doc.add_root(get_header_styles())

    def create_header(self):
        """Create a header showing connection status and PS5 IP"""
        from bokeh.models import Div
        
        # Create the header div with full width
        self.header = Div(
            text=self._get_header_html(),
            width=None,  # Remove any width restriction
            height=30,
            sizing_mode="stretch_width",  # Make it stretch horizontally
            css_classes=["gt7-header"]
        )
        
        return self.header

    def _get_header_html(self):
        """Generate the HTML content for the header"""
        is_connected = self.gt7comm.is_connected()
        status_color = "green" if is_connected else "red"
        status_icon = "✓" if is_connected else "✗"
        status_text = "Connected" if is_connected else "Not Connected"
        
        return f"""
        <div style="display: flex; justify-content: space-between; padding: 5px 10px; 
                   background-color: #f5f5f5; border-bottom: 1px solid #ddd;">
            <div style="margin-right: 20px;">
                <span style="font-weight: bold;">GT7 Dashboard</span>
            </div>
            <div style="flex-grow: 1; text-align: center;">
                <span style="color: {status_color}; font-weight: bold;">{status_icon} {status_text}</span>
            </div>
            <div style="margin-left: 20px;">
                PS5 IP: {self.gt7comm.playstation_ip}
            </div>
        </div>
        """

    def update_header(self, step=None):
        """Update the header with current connection status"""
        if hasattr(self, 'header'):
            self.header.text = self._get_header_html()

# Create and set up the application
app = GT7Application()
app.setup_document(curdoc())