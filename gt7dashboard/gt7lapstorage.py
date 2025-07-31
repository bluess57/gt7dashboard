import os
import pickle
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from gt7dashboard.gt7lap import Lap
from gt7dashboard.gt7lapfile import LapFile
from gt7dashboard.gt7car import car_name

def list_lap_files_from_path(root: str):
    lap_files = []
    for path, sub_dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".json"):
                lf = LapFile()
                lf.name = name
                lf.path = os.path.join(path, name)
                lf.size = os.path.getsize(lf.path)
                lap_files.append(lf)

    lap_files.sort(key=lambda x: x.path, reverse=True)
    return lap_files


def load_laps_from_pickle(path: str) -> List[Lap]:
    with open(path, "rb") as f:
        return pickle.load(f)


def load_laps_from_json(json_file):
    if json_file and os.path.isfile(json_file):
        with open(json_file, 'r') as file:
            data = json.load(file)

        laps = []
        for lap_data in data:
            lap = Lap()
            lap.__dict__.update(lap_data)
            for key, value in lap_data.items():
                if key.endswith('_timestamp') and isinstance(value, str):
                    value = datetime.fromisoformat(value)
                    setattr(lap, key, value)
            laps.append(lap)

        return laps

def save_laps_to_pickle(laps: List[Lap]) -> str:
    storage_folder = "data"
    local_timezone = datetime.now(timezone.utc).astimezone().tzinfo
    dt = datetime.now(tz=local_timezone)
    str_date_time = dt.strftime("%Y-%m-%d_%H_%M_%S")
    storage_filename = "%s_%s.laps" % (str_date_time, get_safe_filename(laps[0].car_name()))
    Path(storage_folder).mkdir(parents=True, exist_ok=True)

    path = os.path.join(os.getcwd(), storage_folder, storage_filename)

    with open(path, "wb") as f:
        pickle.dump(laps, f)

    return path

def save_laps_to_json(laps: List[Lap]) -> str:
    storage_folder = "data"
    local_timezone = datetime.now(timezone.utc).astimezone().tzinfo
    dt = datetime.now(tz=local_timezone)
    str_date_time = dt.strftime("%Y-%m-%d_%H_%M_%S")
    storage_filename = "%s_%s.json" % (str_date_time, get_safe_filename(car_name(laps[0].car_id)))
    Path(storage_folder).mkdir(parents=True, exist_ok=True)

    path = os.path.join(os.getcwd(), storage_folder, storage_filename)

    with open(path, "w") as f:
        json.dump([ob.__dict__ for ob in laps], f, default=str)

    return path


def get_safe_filename(unsafe_filename: str) -> str:
    return "".join(x for x in unsafe_filename if x.isalnum() or x in "._- ").replace(" ", "_")