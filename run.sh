#!/bin/bash
# Set path to a python virtual environment
pythonvenv="/home/ian/gt7dashboard-1/python/bin"

$pythonvenv/pip3 install -r requirements.txt

$pythonvenv/python3 helper/download_cars_csv.py

$pythonvenv/python3 -m bokeh serve --show .
