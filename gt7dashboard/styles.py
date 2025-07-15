from bokeh.models import Div

def get_header_styles():
    """Return a Div containing header CSS styles and layout adjustments"""
    return Div(text="""
    <style>
    /* Force header to fill entire browser width */
    .gt7-header {
        display: block !important;
        position: fixed !important; /* Change from sticky to fixed */
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100vw !important; /* Use viewport width */
        max-width: 100vw !important;
        z-index: 99999 !important;
        background-color: #f5f5f5 !important;
        border-bottom: 1px solid #ddd !important;
        height: 30px !important;
        margin: 0 !important;
        padding: 5px 10px !important;
        box-sizing: border-box !important; /* Include padding in width */
        font-size: 14px !important;
        font-family: sans-serif !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1) !important;
    }
    
    /* Push content down to make room for fixed header */
    .bk-root {
        padding-top: 40px !important;
    }
    
    /* Make sure Bokeh container doesn't restrict width */
    .bk-root, .bk-grid, .bk-column {
        width: 100% !important;
        max-width: 100% !important;
    }
    </style>
    """)