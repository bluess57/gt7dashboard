import os

import gt7dashboard.gt7help as gt7help


def add_screenshot(filename):
    # join path
    str_screenshot_path = os.path.join("README.assets", filename)
    # check if file exists
    if os.path.exists(str_screenshot_path):
        return f"![screenshot_header]({str_screenshot_path})"
    else:
        raise Exception("File does not exist: " + str_screenshot_path)


if __name__ == "__main__":

    out_markdown = "## Manual\n\n"

    out_markdown += "### Tab 'Get Faster'\n\n"

    out_markdown += "#### Header\n\n"
    out_markdown += add_screenshot("screenshot_header.png") + "\n\n"
    out_markdown += gt7help.HEADER + "\n\n"

    out_markdown += "#### Lap Controls\n\n"
    out_markdown += add_screenshot("screenshot_lapcontrols.png") + "\n\n"
    out_markdown += gt7help.LAP_CONTROLS + "\n\n"

    out_markdown += "#### Time / Diff\n\n"
    out_markdown += add_screenshot("screenshot_timediff.png") + "\n\n"
    out_markdown += gt7help.TIME_DIFF + "\n\n"

    out_markdown += "#### Manual Controls\n\n"
    out_markdown += add_screenshot("screenshot_manualcontrols.png") + "\n\n"
    out_markdown += gt7help.MANUAL_CONTROLS + "\n\n"

    out_markdown += "#### Speed \n\n"
    out_markdown += add_screenshot("screenshot_speed.png") + "\n\n"
    out_markdown += gt7help.SPEED_DIAGRAM + "\n\n"

    out_markdown += "#### Race Line\n\n"
    out_markdown += add_screenshot("screenshot_raceline.png") + "\n\n"
    out_markdown += gt7help.RACE_LINE_MINI + "\n\n"

    out_markdown += "#### Peaks and Valleys\n\n"
    out_markdown += add_screenshot("screenshot_peaks_and_valleys.png") + "\n\n"
    out_markdown += gt7help.SPEED_PEAKS_AND_VALLEYS + "\n\n"

    out_markdown += "#### Speed Deviation (Spd. Dev.)\n\n"
    out_markdown += add_screenshot("screenshot_speeddeviation.png") + "\n\n"
    out_markdown += gt7help.SPEED_VARIANCE + "\n\n"

    out_markdown += """I got inspired for this diagram by the [Your Data Driven Podcast](https://www.yourdatadriven.com/).
On two different episodes of this podcast both [Peter Krause](https://www.yourdatadriven.com/ep12-go-faster-now-with-motorsports-data-analytics-guru-peter-krause/) and [Ross Bentley](https://www.yourdatadriven.com/ep3-tips-for-racing-faster-with-ross-bentley/) mentioned this visualization.
If they had one graph it would be the deviation in the (best) laps of the same driver, to improve said drivers performance learning from the differences in already good laps. If they could do it once, they could do it every time.\n\n"""

    out_markdown += "#### Throttle\n\n"
    out_markdown += add_screenshot("screenshot_throttle.png") + "\n\n"
    out_markdown += gt7help.THROTTLE_DIAGRAM + "\n\n"

    out_markdown += "#### Yaw Rate / Second\n\n"
    out_markdown += add_screenshot("screenshot_yaw.png") + "\n\n"
    out_markdown += gt7help.YAW_RATE_DIAGRAM + "\n\n"
    out_markdown += "[Suellio Almeida](https://suellioalmeida.ca) introduced this concept to me. See [here](https://www.youtube.com/watch?v=B92vFKKjyB0) for more information.\n\n"

    out_markdown += "#### Braking\n\n"
    out_markdown += add_screenshot("screenshot_braking.png") + "\n\n"
    out_markdown += gt7help.BRAKING_DIAGRAM + "\n\n"

    out_markdown += "#### Coasting\n\n"
    out_markdown += add_screenshot("screenshot_coasting.png") + "\n\n"
    out_markdown += gt7help.COASTING_DIAGRAM + "\n\n"

    out_markdown += "#### Gear\n\n"
    out_markdown += add_screenshot("screenshot_gear.png") + "\n\n"
    out_markdown += gt7help.GEAR_DIAGRAM + "\n\n"

    out_markdown += "#### RPM\n\n"
    out_markdown += add_screenshot("screenshot_rpm.png") + "\n\n"
    out_markdown += gt7help.RPM_DIAGRAM + "\n\n"

    out_markdown += "#### Boost\n\n"
    out_markdown += add_screenshot("screenshot_boost.png") + "\n\n"
    out_markdown += gt7help.BOOST_DIAGRAM + "\n\n"

    out_markdown += "#### Tyre Speed / Car Speed\n\n"
    out_markdown += add_screenshot("screenshot_tyrespeed.png") + "\n\n"
    out_markdown += gt7help.TIRE_DIAGRAM + "\n\n"

    out_markdown += "#### Time Table\n\n"
    out_markdown += add_screenshot("screenshot_timetable.png") + "\n\n"
    out_markdown += gt7help.TIME_TABLE + "\n\n"

    out_markdown += "#### Fuel Map\n\n"
    out_markdown += add_screenshot("screenshot_fuelmap.png") + "\n\n"
    out_markdown += gt7help.FUEL_MAP + "\n\n"

    out_markdown += "#### Tuning Info\n\n"
    out_markdown += add_screenshot("screenshot_tuninginfo.png") + "\n\n"
    out_markdown += gt7help.TUNING_INFO + "\n\n"

    out_markdown += "### Tab 'Race Line'\n\n"

    out_markdown += add_screenshot("screenshot_race_line.png") + "\n\n"
    out_markdown += gt7help.RACE_LINE_BIG + "\n\n"

    print(out_markdown)

    with open("README.md", "r+") as f:
        content = f.read()
        pos = content.find("## Manual")
        if pos != -1:
            f.seek(pos)
            f.truncate()
            f.write(out_markdown)
