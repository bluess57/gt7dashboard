import os
import logging
import html
from bokeh.layouts import layout, column
from bokeh.models import Div, Button, TextInput, TabPanel
from ..gt7help import add_help_tooltip
from ..tabs.base_tab import GT7Tab

logger = logging.getLogger('config_tab')
logger.setLevel(logging.DEBUG)

class ConfigTab(GT7Tab):
    """Configuration tab for GT7 Dashboard"""
    
    def __init__(self, app_instance):
        super().__init__("config")
        self.app = app_instance

        self.create_components()
        self.layout = self.create_layout()
        
    def create_components(self):
        """Create all UI components for the configuration tab"""
        # Help text components
        self.config_help = Div(text="""
        <h3>Configuration</h3>
        <p>Configure connection settings for GT7 Dashboard</p>
        """, width=600)
        
        self.network_help = Div(text="""
        <h4>PlayStation Network Settings</h4>
        <p>Enter the IP address of your PlayStation 5 to connect. You can find your PS5 IP address in:</p>
        <ol>
            <li>Settings → System → Network → Connection Status</li>
            <li>Or check your router's connected devices list</li>
        </ol>
        <p>Leave as 255.255.255.255 to use broadcast mode (works on most home networks)</p>
        """, width=600)
        
        self.lap_path_help = Div(text="""
        <h4>Lap Data Path</h4>
        <p>Specify a path to load lap data from:</p>
        <ul>
            <li>Enter a directory path to list available lap files in that directory</li>
            <li>Enter a specific .json or .pickle file path to load that file directly</li>
        </ul>
        <p>Click "Load Laps From Path" to load the data.</p>
        """, width=600)
        
        # Status/message components
        self.ip_validation_message = Div(text="", width=250, height=30)
        self.connection_status = Div(width=400, height=30)
        self.lap_path_status = Div(width=600, height=30)
        
        # Input components
        self.ps5_ip_input = TextInput(
            value=self.app.gt7comm.playstation_ip,
            title="PlayStation 5 IP Address:",
            width=250,
            placeholder="192.168.1.x or 255.255.255.255"
        )
        
        self.lap_path_input = TextInput(
            value=os.environ.get("GT7_LOAD_LAPS_PATH", ""),
            title="Lap Data Path:",
            width=400,
            placeholder="Path to lap data directory or file"
        )
        
        # Button components
        self.connect_button = Button(label="Connect", button_type="primary", width=100)
        self.load_path_button = Button(label="Load Laps From Path", button_type="success", width=100)
        
        # Dashboard link
        self.div_gt7_dashboard = Div(width=120, height=30)
        self.div_gt7_dashboard.text = f"<a href='https://github.com/snipem/gt7dashboard' target='_blank'>GT7 Dashboard</a>"
        
        # Set up event handlers
        self.ps5_ip_input.on_change("value", self.validate_ip)
        self.connect_button.on_click(self.connect_button_handler)
        self.load_path_button.on_click(self.load_path_button_handler)
        
    def create_layout(self):
        """Create layout for this tab"""
        return layout(
            [
                [self.div_gt7_dashboard],
                [self.config_help],
                [self.network_help],
                [column(self.ps5_ip_input, width=250, height=50, sizing_mode="fixed")],
                [self.ip_validation_message],
                [column(self.connect_button, width=100, height=50, sizing_mode="fixed")],
                [self.connection_status],
                [Div(text="<hr>", sizing_mode="stretch_width")],
                [self.lap_path_help],
                [self.lap_path_input],
                [column(self.load_path_button, width=250, height=50, sizing_mode="fixed")],
                [self.lap_path_status],
            ],
            sizing_mode="stretch_width",
        )
    
    def validate_ip(self, attr, old, new):
        """Validate IP address format and provide feedback"""
        import re
        ip_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        
        if new == "":
            self.ip_validation_message.text = "<span style='color:orange'>Enter an IP address</span>"
        elif re.match(ip_pattern, new):
            self.ip_validation_message.text = "<span style='color:green'>✓ Valid IP format</span>"
        else:
            self.ip_validation_message.text = "<span style='color:red'>Invalid IP format</span>"
    
    def connect_button_handler(self, event):
        """Handler for connecting to PS5 with specified IP"""
        new_ip = self.ps5_ip_input.value.strip()
        
        if not new_ip:
            new_ip = "255.255.255.255"
            self.ps5_ip_input.value = new_ip
            logger.warning("Empty IP provided, defaulting to broadcast address")
        
        logger.info(f"Connecting to PlayStation at IP: {new_ip}")
        
        # Update connection with new IP
        self.app.gt7comm.disconnect()
        self.app.gt7comm.playstation_ip = new_ip
        self.app.gt7comm.restart()
        
        # Update connection status
        self.update_connection_status()
        
    def load_path_button_handler(self, event):
        """Handler for loading laps from specified path"""
        from gt7dashboard.gt7helper import list_lap_files_from_path, load_laps_from_pickle, load_laps_from_json
        
        path = self.lap_path_input.value.strip()
        
        if not path:
            logger.warning("No lap data path provided")
            return
            
        logger.info(f"Loading laps from path: {path}")
        
        try:
            # Store path in environment variable for future reference
            os.environ["GT7_LOAD_LAPS_PATH"] = path
            
            if os.path.isdir(path):
                # If directory, list all JSON files
                available_files = list_lap_files_from_path(path)
                if available_files:
                    from gt7dashboard.gt7helper import bokeh_tuple_for_list_of_lapfiles
                    # Update dropdown options - we need to access the select component in the main app
                    # This will require passing the select component to this class or having a callback mechanism
                    # For now, emit an event or directly update if accessible
                    self.app.select.options = bokeh_tuple_for_list_of_lapfiles(available_files)
                    return
            
            # Try to load directly if it's a file
            if os.path.isfile(path):
                if path.endswith('.pickle'):
                    laps = load_laps_from_pickle(path)
                    self.app.gt7comm.load_laps(laps, replace_other_laps=True)
                    logger.info(f"Loaded {len(laps)} laps from pickle file: {path}")
                elif path.endswith('.json'):
                    laps = load_laps_from_json(path)
                    self.app.gt7comm.load_laps(laps, replace_other_laps=True)
                    logger.info(f"Loaded {len(laps)} laps from JSON file: {path}")
                else:
                    logger.warning(f"Unsupported file format: {path}")
                    return
                    
                # Force update
                #self.app.update_telemetry()  # Or however you trigger updates in the main app
                
        except Exception as e:
            logger.error(f"Error loading laps from path: {e}")
            self.lap_path_status.text = f"<div style='color: red;'>Error: {e}</div>"
            return
            
        self.lap_path_status.text = f"<div style='color: green;'>Successfully loaded data from: {path}</div>"
        
    def update_connection_status(self, step=None):
        """Update the connection status display on config tab"""
        if self.app.gt7comm.is_connected():
            self.connection_status.text = f"""
            <div style="color: green; font-weight: bold;">
                ✓ Connected to PlayStation at {self.app.gt7comm.playstation_ip}
            </div>
            """
        else:
            self.connection_status.text = f"""
            <div style="color: red; font-weight: bold;">
                ✗ Not connected to PlayStation at {self.app.gt7comm.playstation_ip}
            </div>
            <div>
                Make sure your PS5 is on the same network and Gran Turismo 7 is running.
            </div>
            """
    
    def get_tab_panel(self):
        """Create a TabPanel for this tab"""
        return TabPanel(child=self.layout, title="Configuration")