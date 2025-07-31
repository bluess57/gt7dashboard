import logging
import csv
import os

def car_name(car_id: int) -> str:
    return get_car_name_for_car_id(car_id)

CARS_CSV_FILENAME = "db/cars.csv"

def get_car_name_for_car_id(car_id: int) -> str:
    # check if file exists
    if not os.path.isfile(CARS_CSV_FILENAME):
        logging.info("Could not find file %s" % CARS_CSV_FILENAME)
        return "CAR-ID-%d" % car_id

    # Static cache dictionary
    if not hasattr(get_car_name_for_car_id, "_car_id_cache"):
        get_car_name_for_car_id._car_id_cache = None

    # Load cache if not already loaded
    if get_car_name_for_car_id._car_id_cache is None:
        car_id_cache = {}

        with open(CARS_CSV_FILENAME, 'r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            for row in csv_reader:
                if len(row) >= 2:
                    # Strip whitespace and store as int for robust matching
                    try:
                        key = int(row[0].strip())
                        car_id_cache[key] = row[1].strip()
                    except ValueError:
                        continue
        get_car_name_for_car_id._car_id_cache = car_id_cache
    else:
        car_id_cache = get_car_name_for_car_id._car_id_cache

    # Look up car_id as int
    try:
        car_id_int = int(car_id)
    except ValueError:
        return f"CAR-ID-{car_id}"

    if car_id_int in car_id_cache:
        return car_id_cache[car_id_int]
    else:
        return f"CAR-ID-{car_id}"
