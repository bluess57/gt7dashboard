import copy
import itertools
import logging
import os
import time
import html
from typing import List

import bokeh.application
from bokeh.driving import linear
from bokeh.layouts import layout, column
from bokeh.models import (
    Select,
    Paragraph,
    ColumnDataSource,
    TableColumn,
    DataTable,
    Button,
    Div, CheckboxGroup, TabPanel, Tabs, TextInput,
)
from bokeh.palettes import Plasma11 as palette
from bokeh.plotting import (
    curdoc,
    figure
)

from gt7dashboard import gt7communication, gt7diagrams, gt7help, gt7helper, gt7lap
from gt7dashboard.gt7diagrams import get_speed_peak_and_valley_diagram

from gt7dashboard.gt7help import (
    get_help_div, 
    add_help_tooltip,
    add_plot_tooltip
)

from gt7dashboard.gt7helper import (
    load_laps_from_pickle,
    save_laps_to_pickle,
    list_lap_files_from_path,
    calculate_time_diff_by_distance, save_laps_to_json, load_laps_from_json,
)
from gt7dashboard.gt7lap import Lap

# set logging level to debug
logger = logging.getLogger('main.py')
logger.setLevel(logging.DEBUG)

def update_connection_status():
    """Update the connection status display on config tab"""
    if app.gt7comm.is_connected():
        connection_status.text = f"""
        <div style="color: green; font-weight: bold;">
            ✓ Connected to PlayStation at {app.gt7comm.playstation_ip}
        </div>
        """
    else:
        connection_status.text = f"""
        <div style="color: red; font-weight: bold;">
            ✗ Not connected to PlayStation at {app.gt7comm.playstation_ip}
        </div>
        <div>
            Make sure your PS5 is on the same network and Gran Turismo 7 is running.
        </div>
        """
        
def update_connection_info():
    div_connection_info.text = ""
    if app.gt7comm.is_connected():
        div_connection_info.text += f"<p title='Connected to {app.gt7comm.playstation_ip}'>🟢</p>"
    else:
        div_connection_info.text += f"<p title='Not connected to {app.gt7comm.playstation_ip}'>🔴</p>"


def update_reference_lap_select(laps):
    reference_lap_select.options = [
        tuple(("-1", "Best Lap"))
    ] + gt7helper.bokeh_tuple_for_list_of_laps(laps)


@linear()
def update_fuel_map(step):
    global g_stored_fuel_map

    if len(app.gt7comm.laps) == 0:
        div_fuel_map.text = ""
        return

    last_lap = app.gt7comm.laps[0]

    if last_lap == g_stored_fuel_map:
        return
    else:
        g_stored_fuel_map = last_lap

    # TODO Add real live data during a lap
    div_fuel_map.text = gt7diagrams.get_fuel_map_html_table(last_lap)


def update_race_lines(laps: List[Lap], reference_lap: Lap):
    """
    This function updates the race lines on the second tab with the amount of laps
    that the race line tab can hold
    """
    global race_lines, race_lines_data


    reference_lap_data = reference_lap.get_data_dict()

    for i, lap in enumerate(laps[:len(race_lines)]):
        logger.info(f"Updating Race Line for Lap {len(laps) -i} - {lap.title} and reference lap {reference_lap.title}")

        race_lines[i].title.text = "Lap %d - %s (%s), Reference Lap: %s (%s)" % (len(laps) - i, lap.title, lap.car_name(), reference_lap.title, reference_lap.car_name())

        lap_data = lap.get_data_dict()
        race_lines_data[i][0].data_source.data = lap_data
        race_lines_data[i][1].data_source.data = lap_data
        race_lines_data[i][2].data_source.data = lap_data

        race_lines_data[i][3].data_source.data = reference_lap_data
        race_lines_data[i][4].data_source.data = reference_lap_data
        race_lines_data[i][5].data_source.data = reference_lap_data

        race_lines[i].axis.visible = False

        gt7diagrams.add_annotations_to_race_line(race_lines[i], lap, reference_lap)

        # Fixme not working
        race_lines[i].x_range = race_lines[0].x_range


def update_header_line(div: Div, last_lap: Lap, reference_lap: Lap):
    div.text = f"<p><b>Last Lap: {last_lap.title} ({last_lap.car_name()})<b></p>" \
               f"<p><b>Reference Lap: {reference_lap.title} ({reference_lap.car_name()})<b></p>"

def update_lap_change():
    """
    Is called whenever a lap changes.
    It detects if the telemetry date retrieved is the same as the data displayed.
    If true, it updates all the visual elements.
    """
    global g_laps_stored
    global g_session_stored
    global g_connection_status_stored
    global g_telemetry_update_needed
    global g_reference_lap_selected

    update_start_time = time.time()

    laps = app.gt7comm.get_laps()

    if app.gt7comm.session != g_session_stored:
        update_tuning_info()
        g_session_stored = copy.copy(app.gt7comm.session)

    if app.gt7comm.is_connected() != g_connection_status_stored:
        update_connection_info()
        g_connection_status_stored = copy.copy(app.gt7comm.is_connected())

    # This saves on cpu time, 99.9% of the time this is true
    if laps == g_laps_stored and not g_telemetry_update_needed:
        return

    logger.debug("Rerendering laps")

    reference_lap = Lap()

    if len(laps) > 0:

        last_lap = laps[0]

        if len(laps) > 1:
            reference_lap = gt7helper.get_last_reference_median_lap(
                laps, reference_lap_selected=g_reference_lap_selected
            )[1]

            div_speed_peak_valley_diagram.text = get_speed_peak_and_valley_diagram(last_lap, reference_lap)

        update_header_line(div_header_line, last_lap, reference_lap)

    logger.debug("Updating of %d laps" % len(laps))

    start_time = time.time()
    update_time_table(laps)
    logger.debug("Updating time table took %dms" % ((time.time() - start_time) * 1000))

    start_time = time.time()
    update_reference_lap_select(laps)
    logger.debug("Updating reference lap select took %dms" % ((time.time() - start_time) * 1000))

    start_time = time.time()
    update_speed_velocity_graph(laps)
    logger.debug("Updating speed velocity graph took %dms" % ((time.time() - start_time) * 1000))

    start_time = time.time()
    update_race_lines(laps, reference_lap)
    logger.debug("Updating race lines took %dms" % ((time.time() - start_time) * 1000))

    logger.debug("End of updating laps, whole Update took %dms" % ((time.time() - update_start_time) * 1000))

    g_laps_stored = laps.copy()
    g_telemetry_update_needed = False


def update_speed_velocity_graph(laps: List[Lap]):
    last_lap, reference_lap, median_lap = gt7helper.get_last_reference_median_lap(
        laps, reference_lap_selected=g_reference_lap_selected
    )

    if last_lap:
        last_lap_data = last_lap.get_data_dict()
        race_diagram.source_last_lap.data = last_lap_data
        last_lap_race_line.data_source.data = last_lap_data

        if reference_lap and len(reference_lap.data_speed) > 0:
            reference_lap_data = reference_lap.get_data_dict()
            race_diagram.source_time_diff.data = calculate_time_diff_by_distance(reference_lap, last_lap)
            race_diagram.source_reference_lap.data = reference_lap_data
            reference_lap_race_line.data_source.data = reference_lap_data

    if median_lap:
        race_diagram.source_median_lap.data = median_lap.get_data_dict()


    s_race_line.legend.visible = False
    s_race_line.axis.visible = False

    fastest_laps = race_diagram.update_fastest_laps_variance(laps)
    logger.info("Updating Speed Deviance with %d fastest laps" % len(fastest_laps))
    div_deviance_laps_on_display.text = ""
    for fastest_lap in fastest_laps:
        div_deviance_laps_on_display.text += f"<b>Lap {fastest_lap.number}:</b> {fastest_lap.title}<br>"

    # Update breakpoints
    # Adding Brake Points is slow when rendering, this is on Bokehs side about 3s
    brake_points_enabled = os.environ.get("GT7_ADD_BRAKEPOINTS") == "true"

    if brake_points_enabled and len(last_lap.data_braking) > 0:
        update_break_points(last_lap, s_race_line, "blue")

    if brake_points_enabled and len(reference_lap.data_braking) > 0:
        update_break_points(reference_lap, s_race_line, "magenta")


def update_break_points(lap: Lap, race_line: figure, color: str):
    brake_points_x, brake_points_y = gt7helper.get_brake_points(lap)

    for i, _ in enumerate(brake_points_x):
        race_line.scatter(
            brake_points_x[i],
            brake_points_y[i],
            marker="circle",
            size=10,
            fill_color=color,
        )


def update_time_table(laps: List[Lap]):
    global race_time_table
    global lap_times_source
    # FIXME time table is not updating
    logger.info("Adding %d laps to table" % len(laps))
    race_time_table.show_laps(laps)

    # t_lap_times.trigger("source", t_lap_times.source, t_lap_times.source)


def reset_button_handler(event):
    global g_laps_stored
    global g_telemetry_update_needed
    global g_reference_lap_selected
    global g_session_stored
    
    logger.info("Reset button clicked - clearing all data and graphs")
    
    # Clear race diagram data
    race_diagram.delete_all_additional_laps()
    
    # Clear data sources for main graphs
    race_diagram.source_last_lap.data = {"distance": [], "speed": [], "throttle": [], "brake": [], "time": []}
    race_diagram.source_reference_lap.data = {"distance": [], "speed": [], "throttle": [], "brake": [], "time": []}
    race_diagram.source_median_lap.data = {"distance": [], "speed": [], "throttle": [], "brake": [], "time": []}
    race_diagram.source_time_diff.data = {"distance": [], "time_diff": []}
    
    # Clear race line visualization
    last_lap_race_line.data_source.data = {"raceline_x": [], "raceline_z": []}
    reference_lap_race_line.data_source.data = {"raceline_x": [], "raceline_z": []}
    
    # Reset race time table
    race_time_table.lap_times_source.data = {"index": [], "car": [], "time": [], "number": [], "title": []}
    race_time_table.lap_times_source.selected.indices = []
    
    # Clear all race lines on the second tab
    for i, lines_data in enumerate(race_lines_data):
        for line in lines_data:
            line.data_source.data = {"raceline_x_throttle": [], "raceline_z_throttle": [], 
                                    "raceline_x_braking": [], "raceline_z_braking": [],
                                    "raceline_x_coasting": [], "raceline_z_coasting": []}
        
        if i < len(race_lines):
            race_lines[i].title.text = "Race Line"
            # Clear any annotations
            for renderer in list(race_lines[i].renderers):
                if hasattr(renderer, 'glyph') and hasattr(renderer.glyph, '_scatter'):
                    race_lines[i].renderers.remove(renderer)
    
    # Clear information displays
    div_header_line.text = "<p><b>Last Lap: None</b></p><p><b>Reference Lap: None</b></p>"
    div_speed_peak_valley_diagram.text = ""
    div_deviance_laps_on_display.text = ""
    div_fuel_map.text = ""
    
    # Reset reference lap selection
    g_reference_lap_selected = None
    reference_lap_select.value = "-1"  # Best Lap option
    
    # Reset stored data
    g_laps_stored = []
    g_session_stored = None
    
    # Clear GT7 communication data
    app.gt7comm.load_laps([], replace_other_laps=True)
    app.gt7comm.reset()
    
    # Force full UI update
    g_telemetry_update_needed = True
    
    logger.info("Reset complete - all graphs and data cleared")


def always_record_checkbox_handler(event, old, new):
    if len(new) == 2:
        logger.info("Set always record data to True")
        app.gt7comm.always_record_data = True
    else:
        logger.info("Set always record data to False")
        app.gt7comm.always_record_data = False


def log_lap_button_handler(event):
    app.gt7comm.finish_lap(manual=True)
    logger.info("Added a lap manually to the list of laps: %s" % app.gt7comm.laps[0])


def save_button_handler(event):
    if len(app.gt7comm.laps) > 0:
        path = save_laps_to_json(app.gt7comm.laps)
        logger.info("Saved %d laps as %s" % (len(app.gt7comm.laps), path))


def load_laps_handler(attr, old, new):
    logger.info("Loading %s" % new)
    race_diagram.delete_all_additional_laps()
    app.gt7comm.load_laps(load_laps_from_json(new), replace_other_laps=True)


def load_reference_lap_handler(attr, old, new):
    global g_reference_lap_selected
    global reference_lap_select
    global g_telemetry_update_needed

    if int(new) == -1:
        # Set no reference lap
        g_reference_lap_selected = None
    else:
        g_reference_lap_selected = g_laps_stored[int(new)]
        logger.info("Loading %s as reference" % g_laps_stored[int(new)].format())

    g_telemetry_update_needed = True
    update_lap_change()



def update_tuning_info():
    div_tuning_info.text = """<h4>Tuning Info</h4>
    <p>Max Speed: <b>%d</b> kph</p>
    <p>Min Body Height: <b>%d</b> mm</p>""" % (
        app.gt7comm.session.max_speed,
        app.gt7comm.session.min_body_height,
    )

def get_race_lines_layout(number_of_race_lines):
    """
    This function returns the race lines layout.
    It returns a grid of 3x3 race lines. Red is braking.
    Green is throttling.
    """
    i = 0
    race_line_diagrams = []
    race_lines_data = []

    sizing_mode = "scale_height"

    while i < number_of_race_lines:
        s_race_line, throttle_line, breaking_line, coasting_line, reference_throttle_line, reference_breaking_line, reference_coasting_line = gt7diagrams.get_throttle_braking_race_line_diagram()
        s_race_line.sizing_mode = sizing_mode
        race_line_diagrams.append(s_race_line)
        race_lines_data.append([throttle_line, breaking_line, coasting_line, reference_throttle_line, reference_breaking_line, reference_coasting_line])
        i+=1

    l = layout(children=race_line_diagrams)
    l.sizing_mode = sizing_mode

    return l, race_line_diagrams, race_lines_data

app = bokeh.application.Application

# Share the gt7comm connection between sessions by storing them as an application attribute
if not hasattr(app, "gt7comm"):
    playstation_ip = os.environ.get("GT7_PLAYSTATION_IP")
    load_laps_path = os.environ.get("GT7_LOAD_LAPS_PATH")

    if not playstation_ip:
        playstation_ip = "255.255.255.255"
        logger.info(f"No IP set in env var GT7_PLAYSTATION_IP using broadcast at {playstation_ip}")

    app.gt7comm = gt7communication.GT7Communication(playstation_ip)

    if load_laps_path:
        app.gt7comm.load_laps(
            load_laps_from_pickle(load_laps_path), replace_other_laps=True
        )

    app.gt7comm.start()
else:
    # Reuse existing thread
    if not app.gt7comm.is_connected():
        logger.info("Restarting gt7communcation because of no connection")
        app.gt7comm.restart()
    else:
        # Existing thread has connection, proceed
        pass


# def init_lap_times_source():
#     global lap_times_source
#     lap_times_source.data = gt7helper.pd_data_frame_from_lap([], best_lap_time=app.gt7comm.session.last_lap)
#
# init_lap_times_source()

g_laps_stored = []
g_session_stored = None
g_connection_status_stored = None
g_reference_lap_selected = None
g_stored_fuel_map = None
g_telemetry_update_needed = False

stored_lap_files = gt7helper.bokeh_tuple_for_list_of_lapfiles(
    list_lap_files_from_path(os.path.join(os.getcwd(), "data"))
)

race_diagram = gt7diagrams.RaceDiagram(width=1000)
race_time_table = gt7diagrams.RaceTimeTable()
colors = itertools.cycle(palette)


def table_row_selection_callback(attrname, old, new):
    global g_laps_stored
    global race_diagram
    global race_time_table
    global colors

    selectionIndex=race_time_table.lap_times_source.selected.indices
    logger.info("you have selected the row nr "+str(selectionIndex))

    colors = ["blue", "magenta", "green", "orange", "black", "purple"]
    # max_additional_laps = len(palette)
    colors_index = len(race_diagram.sources_additional_laps) + race_diagram.number_of_default_laps # which are the default colors

    for index in selectionIndex:
        if index >= len(colors):
            colors_index = 0

        # get element at index of iterator
        color = colors[colors_index]
        colors_index+=1
        lap_to_add = g_laps_stored[index]
        new_lap_data_source = race_diagram.add_lap_to_race_diagram(color, legend=g_laps_stored[index].title, visible=True)
        new_lap_data_source.data = lap_to_add.get_data_dict()


race_time_table.lap_times_source.selected.on_change('indices', table_row_selection_callback)

# Race line

race_line_tooltips = [("index", "$index"), ("Breakpoint", "")]
race_line_width = 250
speed_diagram_width = 1200
total_width = race_line_width + speed_diagram_width
s_race_line = figure(
    title="Race Line",
    x_axis_label="x",
    y_axis_label="z",
    match_aspect=True,
    width=race_line_width,
    height=race_line_width,
    active_drag="box_zoom",
    tooltips=race_line_tooltips,
)

# We set this to true, since maps appear flipped in the game
# compared to their actual coordinates
s_race_line.y_range.flipped = True

s_race_line.toolbar.autohide = True

last_lap_race_line = s_race_line.line(
    x="raceline_x",
    y="raceline_z",
    legend_label="Last Lap",
    line_width=1,
    color="blue",
    source=ColumnDataSource(data={"raceline_x": [], "raceline_z": []})
)
reference_lap_race_line = s_race_line.line(
    x="raceline_x",
    y="raceline_z",
    legend_label="Reference Lap",
    line_width=1,
    color="magenta",
    source=ColumnDataSource(data={"raceline_x": [], "raceline_z": []})
)

select_title = Paragraph(text="Load Laps:", align="center")
select = Select(value="laps", options=stored_lap_files)
select.on_change("value", load_laps_handler)

reference_lap_select = Select(value="laps")
reference_lap_select.on_change("value", load_reference_lap_handler)

manual_log_button = Button(label="Log Lap Now")
manual_log_button.on_click(log_lap_button_handler)

save_button = Button(label="Save Laps")
save_button.on_click(save_button_handler)

reset_button = Button(label="Reset Laps")
reset_button.on_click(reset_button_handler)

div_tuning_info = Div(width=200, height=100)

# div_last_lap = Div(width=200, height=125)
# div_reference_lap = Div(width=200, height=125)
div_speed_peak_valley_diagram = Div(width=200, height=125)
div_gt7_dashboard = Div(width=120, height=30)
div_header_line = Div(width=400, height=30)
div_connection_info = Div(width=30, height=30)
div_deviance_laps_on_display = Div(width=200, height=race_diagram.f_speed_variance.height)

div_fuel_map = Div(width=200, height=125, css_classes=["fuel_map"])

div_gt7_dashboard.text = f"<a href='https://github.com/snipem/gt7dashboard' target='_blank'>GT7 Dashboard</a>"

LABELS = ["Record Replays"]

checkbox_group = CheckboxGroup(labels=LABELS, active=[1])
checkbox_group.on_change("active", always_record_checkbox_handler)

race_time_table.t_lap_times.width=900

add_help_tooltip(race_diagram.f_speed, gt7help.SPEED_DIAGRAM)
add_help_tooltip(s_race_line, gt7help.RACE_LINE_MINI)
add_help_tooltip(race_diagram.f_speed_variance, gt7help.SPEED_VARIANCE)
add_help_tooltip(race_diagram.f_time_diff, gt7help.TIME_DIFF)
add_help_tooltip(race_diagram.f_throttle, gt7help.THROTTLE_DIAGRAM)
add_help_tooltip(race_diagram.f_yaw_rate, gt7help.YAW_RATE_DIAGRAM)
add_help_tooltip(race_diagram.f_braking, gt7help.BRAKING_DIAGRAM)
add_help_tooltip(race_diagram.f_coasting, gt7help.COASTING_DIAGRAM)
add_help_tooltip(race_diagram.f_gear, gt7help.GEAR_DIAGRAM)
add_help_tooltip(race_diagram.f_rpm, gt7help.RPM_DIAGRAM)
add_help_tooltip(race_diagram.f_boost, gt7help.BOOST_DIAGRAM)
add_help_tooltip(race_diagram.f_tires, gt7help.TIRE_DIAGRAM)
# add_help_tooltip(race_time_table.t_lap_times, gt7help.TIME_TABLE)
# add_help_tooltip(div_fuel_map, gt7help.FUEL_MAP)
# add_help_tooltip(div_tuning_info, gt7help.TUNING_INFO)
# add_help_tooltip(div_speed_peak_valley_diagram, gt7help.SPEED_PEAKS_AND_VALLEYS)

# Add a help icon next to your table
race_time_table_help = Div(text=f'<i class="fa fa-question-circle" title="{html.escape(gt7help.TIME_TABLE)}"></i>', width=20)

l1 = layout(
    children=[
        [div_connection_info, div_header_line, reset_button, save_button, select_title, select],
        [race_diagram.f_time_diff, layout(children=[manual_log_button, checkbox_group, reference_lap_select])],
        [race_diagram.f_speed, s_race_line],
        [race_diagram.f_speed_variance, div_deviance_laps_on_display],
        [race_diagram.f_throttle, div_speed_peak_valley_diagram],
        [race_diagram.f_yaw_rate],
        [race_diagram.f_braking],
        [race_diagram.f_coasting],
        [race_diagram.f_gear],
        [race_diagram.f_rpm],
        [race_diagram.f_boost],
        [race_diagram.f_tires],
        [race_time_table.t_lap_times, race_time_table_help, div_fuel_map, div_tuning_info],
    ]
)




l2, race_lines, race_lines_data = get_race_lines_layout(number_of_race_lines=1)

l3 = layout(
    [
        [reset_button, save_button],
        [div_speed_peak_valley_diagram, div_fuel_map], # TODO Race table does not render twice, one rendering will be empty
     ],
    sizing_mode="stretch_width",
)

# Add after the existing layout definitions (l1, l2, l3)
config_help = Div(text="""
<h3>Configuration</h3>
<p>Configure connection settings for GT7 Dashboard</p>
""", width=400)

network_help = Div(text="""
<h4>PlayStation Network Settings</h4>
<p>Enter the IP address of your PlayStation 5 to connect. You can find your PS5 IP address in:</p>
<ol>
    <li>Settings → System → Network → Connection Status</li>
    <li>Or check your router's connected devices list</li>
</ol>
<p>Leave as 255.255.255.255 to use broadcast mode (works on most home networks)</p>
""", width=600)

# Add to the configuration components section
lap_path_input = TextInput(
    value=os.environ.get("GT7_LOAD_LAPS_PATH", ""),
    title="Lap Data Path:",
    width=400,
    placeholder="Path to lap data directory or file"
)
load_path_button = Button(label="Load Laps From Path", button_type="success", width=100)

def load_path_button_handler(event):
    """Handler for loading laps from specified path"""
    path = lap_path_input.value.strip()
    
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
                # Update dropdown options
                select.options = gt7helper.bokeh_tuple_for_list_of_lapfiles(available_files)
                return
        
        # Try to load directly if it's a file
        if os.path.isfile(path):
            if path.endswith('.pickle'):
                laps = load_laps_from_pickle(path)
                app.gt7comm.load_laps(laps, replace_other_laps=True)
                logger.info(f"Loaded {len(laps)} laps from pickle file: {path}")
            elif path.endswith('.json'):
                laps = load_laps_from_json(path)
                app.gt7comm.load_laps(laps, replace_other_laps=True)
                logger.info(f"Loaded {len(laps)} laps from JSON file: {path}")
            else:
                logger.warning(f"Unsupported file format: {path}")
                return
                
            # Force update
            global g_telemetry_update_needed
            g_telemetry_update_needed = True
            update_lap_change()
    except Exception as e:
        logger.error(f"Error loading laps from path: {e}")
        lap_path_status.text = f"<div style='color: red;'>Error: {e}</div>"
        return
        
    lap_path_status.text = f"<div style='color: green;'>Successfully loaded data from: {path}</div>"

# Connect handler to button
load_path_button.on_click(load_path_button_handler)

# Add status display for lap path operations
lap_path_status = Div(width=600, height=30)

# Add help text
lap_path_help = Div(text="""
<h4>Lap Data Path</h4>
<p>Specify a path to load lap data from:</p>
<ul>
    <li>Enter a directory path to list available lap files in that directory</li>
    <li>Enter a specific .json or .pickle file path to load that file directly</li>
</ul>
<p>Click "Load Laps From Path" to load the data.</p>
""", width=600)

# Add a validation status message
ip_validation_message = Div(text="", width=250, height=30)

ps5_ip_input = TextInput(
    value=app.gt7comm.playstation_ip,
    title="PlayStation 5 IP Address:",
    width=250,
    placeholder="192.168.1.x or 255.255.255.255"
)

def validate_ip(attr, old, new):
    """Validate IP address format and provide feedback"""
    import re
    ip_pattern = r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    
    if new == "":
        ip_validation_message.text = "<span style='color:orange'>Enter an IP address</span>"
    elif re.match(ip_pattern, new):
        ip_validation_message.text = "<span style='color:green'>✓ Valid IP format</span>"
    else:
        ip_validation_message.text = "<span style='color:red'>Invalid IP format</span>"

ps5_ip_input.on_change("value", validate_ip)
connect_button = Button(label="Connect", button_type="primary", width=100)
connection_status = Div(width=400, height=30)

def connect_button_handler(event):
    """Handler for connecting to PS5 with specified IP"""
    new_ip = ps5_ip_input.value.strip()
    
    if not new_ip:
        new_ip = "255.255.255.255"
        ps5_ip_input.value = new_ip
        logger.warning("Empty IP provided, defaulting to broadcast address")
    
    logger.info(f"Connecting to PlayStation at IP: {new_ip}")
    
    # Update connection with new IP
    app.gt7comm.disconnect()
    app.gt7comm.playstation_ip = new_ip
    app.gt7comm.restart()
    
    # Update connection status
    update_connection_info()
    update_connection_status()

# Connect handler to button
connect_button.on_click(connect_button_handler)

# Update the configuration tab layout (l4)
l4 = layout(
    [
        [div_gt7_dashboard],
        [config_help],
        [network_help],
        [column(ps5_ip_input, sizing_mode="fixed")],  # IP input on its own line
        [ip_validation_message],  # Add validation message
        [column(connect_button, sizing_mode="fixed")],  # Wrap button in column with fixed sizing
        [connection_status],
        [Div(text="<hr>", width=600)],  # Add separator
        [lap_path_help],
        [lap_path_input],  # Similarly made lap path input on its own line
        [column(load_path_button, sizing_mode="fixed")],  # Button below the input
        [lap_path_status],
    ],
    sizing_mode="stretch_width",
)

#  Setup the tabs
tab1 = TabPanel(child=l1, title="Get Faster")
tab2 = TabPanel(child=l2, title="Race Lines")
tab3 = TabPanel(child=l3, title="Race")
tab4 = TabPanel(child=l4, title="Configuration") # Add the new tab
tabs = Tabs(tabs=[tab1, tab2, tab3, tab4])

curdoc().add_root(tabs)
curdoc().title = "GT7 Dashboard"

# This will only trigger once per lap, but we check every second if anything happened
curdoc().add_periodic_callback(update_lap_change, 1000)
curdoc().add_periodic_callback(update_fuel_map, 5000)

# Initialize connection status
update_connection_status()

# Add to periodic callbacks
curdoc().add_periodic_callback(update_connection_status, 5000)
