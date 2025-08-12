import logging
import os
from bokeh.plotting import curdoc
from bokeh.models import Div, GlobalImportedStyleSheet
from bokeh.layouts import column, row

from gt7dashboard import gt7communication
from gt7dashboard.tab_manager import TabManager

from gt7dashboard.gt7settings import GT7Settings, get_log_level

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(get_log_level())


# Create the application
class GT7Application:
    # Class-level cache for environment variables
    _ENV_CACHE = {}

    @classmethod
    def get_env(cls, key, default=None):
        """Cached environment variable access"""
        if key not in cls._ENV_CACHE:
            cls._ENV_CACHE[key] = os.environ.get(key, default)
        return cls._ENV_CACHE[key]

    def __init__(self):
        # Use cached environment access
        playstation_ip = self.get_env("GT7_PLAYSTATION_IP", "255.255.255.255")

        # Cache header templates and state
        self._header_template = """
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
                PS5 IP: {playstation_ip}
            </div>
        </div>
        """
        self._last_connection_status = None
        self._cached_header_html = None

        # Cache the heartbeat HTML strings
        self._heartbeat_active = (
            '<span id="heartbeat-dot" '
            'title="Green: Receiving data from PlayStation. Gray: No data." '
            'style="font-size:2em; color:lime;">&#10084;</span>'
        )
        self._heartbeat_inactive = (
            '<span id="heartbeat-dot" '
            'title="Green: Receiving data from PlayStation. Gray: No data." '
            'style="font-size:2em; color:gray;">&#10084;</span>'
        )
        self._heartbeat_timeout_id = None

        # Defer heavy initialization until needed
        self._gt7comm = None
        self._tab_manager = None
        self._tabs = None

    @property
    def gt7comm(self):
        """Lazy initialization of GT7 communication"""
        if self._gt7comm is None:
            playstation_ip = os.environ.get("GT7_PLAYSTATION_IP", "255.255.255.255")
            self._gt7comm = gt7communication.GT7Communication(playstation_ip)
        return self._gt7comm

    @property
    def tab_manager(self):
        """Lazy initialization of tab manager"""
        if self._tab_manager is None:
            self._tab_manager = TabManager(self)
        return self._tab_manager

    @property
    def tabs(self):
        """Lazy initialization of tabs"""
        if self._tabs is None:
            self._tabs = self.tab_manager.create_tabs()
        return self._tabs

    def setup_document(self, doc):
        self.doc = doc
        doc.theme = "carbon"

        # Cache CSS path and only load once
        if not hasattr(self, "_css_loaded"):
            css_path = "gt7dashboard/static/css/styles.css"
            globalStylesheet = GlobalImportedStyleSheet(url=css_path)
            doc.add_root(globalStylesheet)
            self._css_loaded = True
            self._global_stylesheet = globalStylesheet

        header = self.create_header()

        self.gt7comm.set_on_connected_callback(lambda: self.update_header(doc))

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

        self.gt7comm.set_on_heartbeat_callback(lambda: self.show_heartbeat(doc))

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
        """Generate the HTML content for the header with caching"""
        is_connected = self.gt7comm.is_connected()

        # Only regenerate if connection status changed
        if is_connected == self._last_connection_status and self._cached_header_html:
            return self._cached_header_html

        self._last_connection_status = is_connected
        status_color = "green" if is_connected else "red"
        status_icon = "✓" if is_connected else "✗"
        status_text = "Connected" if is_connected else "Not Connected"

        self._cached_header_html = self._header_template.format(
            status_color=status_color,
            status_icon=status_icon,
            status_text=status_text,
            playstation_ip=self.gt7comm.playstation_ip,
        )

        return self._cached_header_html

    def update_header(self, doc=None, step=None):
        """Update the header with current connection status - batched updates"""

        def do_update():
            if hasattr(self, "header"):
                new_text = self.update_connection_status()
                # Only update if content actually changed
                if self.header.text != new_text:
                    self.header.text = new_text

        if doc is not None:
            doc.add_next_tick_callback(do_update)
        else:
            do_update()

    def show_heartbeat(self, doc):
        """Optimized heartbeat with reduced DOM updates"""
        try:

            def update():
                self.heartbeat_indicator.text = self._heartbeat_active

                # Cancel existing timeout to prevent multiple timers
                if self._heartbeat_timeout_id:
                    doc.remove_timeout_callback(self._heartbeat_timeout_id)

                # Set new timeout
                self._heartbeat_timeout_id = doc.add_timeout_callback(
                    lambda: setattr(
                        self.heartbeat_indicator, "text", self._heartbeat_inactive
                    ),
                    500,
                )

            if self.gt7comm.is_connected():
                doc.add_next_tick_callback(update)

        except Exception as e:
            logger.exception("Exception in show_heartbeat")

    def cleanup(self):
        """Clean up resources when application shuts down"""
        if hasattr(self, "_heartbeat_timeout_id") and self._heartbeat_timeout_id:
            if hasattr(self, "doc"):
                self.doc.remove_timeout_callback(self._heartbeat_timeout_id)

        if hasattr(self, "_gt7comm") and self._gt7comm:
            self._gt7comm.stop()

        # Clear references
        self._gt7comm = None
        self._tab_manager = None
        self._tabs = None

    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()


# Create and set up the application
app = GT7Application()
app.setup_document(curdoc())
