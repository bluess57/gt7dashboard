from bokeh.models import TabPanel

class GT7Tab:
    """Base class for all GT7 Dashboard tabs"""
    
    def __init__(self, title):
        self.title = title
        self.layout = None
        
    def create_layout(self):
        """Create and return the layout for this tab"""
        raise NotImplementedError("Subclasses must implement create_layout()")
    
    def get_tab_panel(self):
        """Create a TabPanel for this tab"""
        if not self.layout:
            self.layout = self.create_layout()
        return TabPanel(child=self.layout, title=self.title)