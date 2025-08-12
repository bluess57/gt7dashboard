from bokeh.models import ColumnDataSource, Label
from bokeh.plotting import figure

from gt7dashboard import gt7helper
from gt7dashboard.gt7lap import Lap
from gt7dashboard.gt7helper import seconds_to_lap_time


def get_throttle_braking_race_line_diagram():
    # TODO Make this work, tooltips just show breakpoint
    race_line_tooltips = [("index", "$index")]
    s_race_line = figure(
        title="Race Line",
        match_aspect=True,
        active_scroll="wheel_zoom",
        tooltips=race_line_tooltips,
    )

    # We set this to true, since maps appear flipped in the game
    # compared to their actual coordinates
    s_race_line.y_range.flipped = True

    s_race_line.toolbar.autohide = True

    s_race_line.axis.visible = False
    s_race_line.xgrid.visible = False
    s_race_line.ygrid.visible = False

    throttle_line = s_race_line.line(
        x="raceline_x_throttle",
        y="raceline_z_throttle",
        legend_label="Throttle Last Lap",
        line_width=5,
        color="green",
        source=ColumnDataSource(
            data={"raceline_z_throttle": [], "raceline_x_throttle": []}
        ),
    )
    breaking_line = s_race_line.line(
        x="raceline_x_braking",
        y="raceline_z_braking",
        legend_label="Braking Last Lap",
        line_width=5,
        color="red",
        source=ColumnDataSource(
            data={"raceline_z_braking": [], "raceline_x_braking": []}
        ),
    )

    coasting_line = s_race_line.line(
        x="raceline_x_coasting",
        y="raceline_z_coasting",
        legend_label="Coasting Last Lap",
        line_width=5,
        color="cyan",
        source=ColumnDataSource(
            data={"raceline_z_coasting": [], "raceline_x_coasting": []}
        ),
    )

    # Reference Lap

    reference_throttle_line = s_race_line.line(
        x="raceline_x_throttle",
        y="raceline_z_throttle",
        legend_label="Throttle Reference",
        line_width=15,
        alpha=0.3,
        color="green",
        source=ColumnDataSource(
            data={"raceline_z_throttle": [], "raceline_x_throttle": []}
        ),
    )
    reference_breaking_line = s_race_line.line(
        x="raceline_x_braking",
        y="raceline_z_braking",
        legend_label="Braking Reference",
        line_width=15,
        alpha=0.3,
        color="red",
        source=ColumnDataSource(
            data={"raceline_z_braking": [], "raceline_x_braking": []}
        ),
    )

    reference_coasting_line = s_race_line.line(
        x="raceline_x_coasting",
        y="raceline_z_coasting",
        legend_label="Coasting Reference",
        line_width=15,
        alpha=0.3,
        color="cyan",
        source=ColumnDataSource(
            data={"raceline_z_coasting": [], "raceline_x_coasting": []}
        ),
    )

    s_race_line.legend.visible = True

    s_race_line.add_layout(s_race_line.legend[0], "right")

    s_race_line.legend.click_policy = "hide"

    return (
        s_race_line,
        throttle_line,
        breaking_line,
        coasting_line,
        reference_throttle_line,
        reference_breaking_line,
        reference_coasting_line,
    )


def add_annotations_to_race_line(race_line: figure, last_lap: Lap, reference_lap: Lap):
    """Adds annotations such as speed peaks and valleys and the starting line to the racing line"""

    remove_all_annotation_text_from_figure(race_line)

    decorations = []
    decorations.extend(
        _add_peaks_and_valley_decorations_for_lap(
            last_lap, race_line, color="cyan", offset=0
        )
    )
    decorations.extend(
        _add_peaks_and_valley_decorations_for_lap(
            reference_lap, race_line, color="magenta", offset=0
        )
    )
    add_starting_line_to_diagram(race_line, last_lap)

    # This is multiple times faster by adding all texts at once rather than adding them above
    # With around 20 positions, this took 27s before.
    # Maybe this has something to do with every text being transmitted over network
    race_line.center.extend(decorations)

    # Add peaks and valleys of last lap


def _add_peaks_and_valley_decorations_for_lap(
    lap: Lap, race_line: figure, color, offset
):
    (
        peak_speed_data_x,
        peak_speed_data_y,
        valley_speed_data_x,
        valley_speed_data_y,
    ) = lap.get_speed_peaks_and_valleys()

    decorations = []

    for i in range(len(peak_speed_data_x)):
        # shift 10 px to the left
        position_x = lap.data_position_x[peak_speed_data_y[i]]
        position_y = lap.data_position_z[peak_speed_data_y[i]]

        mytext = Label(
            x=position_x,
            y=position_y,
            text_color=color,
            text_font_size="10pt",
            text_font_style="bold",
            x_offset=offset,
            background_fill_color="white",
            background_fill_alpha=0.75,
        )
        mytext.text = "▴%.0f" % peak_speed_data_x[i]

        decorations.append(mytext)

    for i in range(len(valley_speed_data_x)):
        position_x = lap.data_position_x[valley_speed_data_y[i]]
        position_y = lap.data_position_z[valley_speed_data_y[i]]

        mytext = Label(
            x=position_x,
            y=position_y,
            text_color=color,
            text_font_size="10pt",
            x_offset=offset,
            text_font_style="bold",
            background_fill_color="white",
            background_fill_alpha=0.75,
            text_align="right",
        )
        mytext.text = "%.0f▾" % valley_speed_data_x[i]

        decorations.append(mytext)

    return decorations


def remove_all_annotation_text_from_figure(f: figure):
    f.center = [r for r in f.center if not isinstance(r, Label)]


def get_fuel_map_html_table(last_lap: Lap) -> str:
    """
    Returns a html table of relative fuel map.
    :param last_lap:
    :return: html table
    """

    fuel_maps = gt7helper.get_fuel_on_consumption_by_relative_fuel_levels(last_lap)
    table = (
        "<table><tr>"
        "<th title='The fuel level relative to the current one'>Fuel Lvl.</th>"
        "<th title='Fuel consumed'>Fuel Cons.</th>"
        "<th title='Laps remaining with this setting'>Laps Rem.</th>"
        "<th title='Time remaining with this setting' >Time Rem.</th>"
        "<th title='Time Diff to last lap with this setting'>Time Diff</th></tr>"
    )
    for fuel_map in fuel_maps:
        no_fuel_consumption = fuel_map.fuel_consumed_per_lap <= 0
        line_style = ""
        if fuel_map.mixture_setting == 0 and not no_fuel_consumption:
            line_style = "background-color: #444 "
        table += (
            "<tr id='fuel_map_row_%d' style='%s'>"
            "<td style='text-align:center'>%d</td>"
            "<td style='text-align:center'>%d</td>"
            "<td style='text-align:center'>%.1f</td>"
            "<td style='text-align:center'>%s</td>"
            "<td style='text-align:center'>%s</td>"
            "</tr>"
            % (
                fuel_map.mixture_setting,
                line_style,
                fuel_map.mixture_setting,
                0 if no_fuel_consumption else fuel_map.fuel_consumed_per_lap,
                0 if no_fuel_consumption else fuel_map.laps_remaining_on_current_fuel,
                (
                    "No Fuel"
                    if no_fuel_consumption
                    else (
                        seconds_to_lap_time(
                            fuel_map.time_remaining_on_current_fuel / 1000
                        )
                    )
                ),
                (
                    "Consumption"
                    if no_fuel_consumption
                    else (seconds_to_lap_time(fuel_map.lap_time_diff / 1000))
                ),
            )
        )
    table += "</table>"
    table += "<p>Fuel Remaining: <b>%d</b></p>" % last_lap.fuel_at_end
    return table


def add_starting_line_to_diagram(race_line: figure, last_lap: Lap):

    if len(last_lap.data_position_z) == 0:
        return

    x = last_lap.data_position_x[0]
    y = last_lap.data_position_z[0]

    # We use a text because scatters are too memory consuming
    # and cannot be easily removed from the diagram
    mytext = Label(
        x=x,
        y=y,
        text_font_size="10pt",
        text_font_style="bold",
        background_fill_color="white",
        background_fill_alpha=0.25,
        text_align="center",
    )
    mytext.text = "===="
    race_line.center.append(mytext)


def get_speed_peak_and_valley_diagram(last_lap: Lap, reference_lap: Lap) -> str:
    """
    Returns a html div with the speed peaks and valleys of the last lap and the reference lap
    as a formatted html table
    :param last_lap: Lap
    :param reference_lap: Lap
    :return: html table with peaks and valleys
    """
    table = """<table style='border-spacing: 10px; text-align:center'>"""

    table += """<colgroup>
    <col/>
    <col style='border-left: 1px solid #cdd0d4;'/>
    <col/>
    <col/>
    <col/>
    <col/>
    <col/>
    <col/>
    <col/>
    <col/>
  </colgroup>"""

    ll_tuple_list = gt7helper.get_peaks_and_valleys_sorted_tuple_list(last_lap)
    rl_tuple_list = gt7helper.get_peaks_and_valleys_sorted_tuple_list(reference_lap)

    max_data = max(len(ll_tuple_list), len(rl_tuple_list))

    table += "<tr>"

    table += "<th></th>"
    table += '<th colspan="4">%s - %s</th>' % ("Last", last_lap.title)
    table += '<th colspan="4">%s - %s</th>' % ("Ref.", reference_lap.title)
    table += '<th colspan="2">Diff</th>'

    table += "</tr>"

    table += """<tr>
    <td></td><td>#</td><td></td><td>Pos.</td><td>Speed</td>
    <td>#</td><td></td><td>Pos.</td><td>Speed</td>
    <td>Pos.</td><td>Speed</td>
    </tr>"""

    rl_and_ll_are_same_size = len(ll_tuple_list) == len(rl_tuple_list)

    i = 0
    while i < max_data:
        diff_pos = 0
        diff_speed = 0

        if rl_and_ll_are_same_size:
            diff_pos = ll_tuple_list[i][1] - rl_tuple_list[i][1]
            diff_speed = ll_tuple_list[i][0] - rl_tuple_list[i][0]

            if diff_speed > 0:
                diff_style = f"color: rgba(0, 0, 255, .3)"  # Blue
            elif diff_speed >= -3:
                diff_style = f"color: rgba(0, 255, 0, .3)"  # Green
            elif diff_speed >= -10:
                diff_style = f"color: rgba(251, 192, 147, .3)"  # Orange
            else:
                diff_style = f"color: rgba(255, 0, 0, .3)"  # Red

        else:
            diff_style = f"text-color: rgba(255, 0, 0, .3)"  # Red

        table += "<tr>"
        table += f'<td style="width:15px; text-opacity:0.5; {diff_style}">█</td>'

        if len(ll_tuple_list) > i:
            table += f"""<td>{i+1}</td>
                <td>{"S" if ll_tuple_list[i][2] == gt7helper.PEAK else "T"}</td>
                <td>{ll_tuple_list[i][1]:d}</td>
                <td>{ll_tuple_list[i][0]:.0f}</td>
            """

        if len(rl_tuple_list) > i:
            table += f"""<td>{i+1}</td>
                <td>{"S" if rl_tuple_list[i][2] == gt7helper.PEAK else "T"}</td>
                <td>{rl_tuple_list[i][1]:d}</td>
                <td>{rl_tuple_list[i][0]:.0f}</td>
            """

        if rl_and_ll_are_same_size:
            table += f"""
                <td>{diff_pos:d}</td>
                <td>{diff_speed:.0f}</td>
            """
        else:
            table += f"""
                <td>-</td>
                <td>-</td>
            """

        table += "</tr>"
        i += 1

    table += "</td>"
    table += "<td>"
    table += "</td>"

    table = table + """</table>"""
    return table


def get_speed_peak_and_valley_diagram_row(
    peak_speed_data_x,
    peak_speed_data_y,
    table,
    valley_speed_data_x,
    valley_speed_data_y,
):
    row = "<tr><th>#</th><th>Peak</th><th>Position</th></tr>"
    for i, dx in enumerate(peak_speed_data_x):
        row += "<tr><td>%d.</td><td>%d kph</td><td>%d</td></tr>" % (
            i + 1,
            peak_speed_data_x[i],
            peak_speed_data_y[i],
        )
    row += "<tr><th>#</th><th>Valley</th><th>Position</th></tr>"
    for i, dx in enumerate(valley_speed_data_x):
        row += "<tr><td>%d.</td><td>%d kph</td><td>%d</td></tr>" % (
            i + 1,
            valley_speed_data_x[i],
            valley_speed_data_y[i],
        )
    return row
