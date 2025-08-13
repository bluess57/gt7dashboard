#!/bin/bash
# Set path to a python virtual environment
pythonvenv="/home/ian/gt7dashboard-1/python/bin" # Adjust this path as needed to a virtual python environment

$pythonvenv/pip3 install -r requirements.txt

$pythonvenv/python3 helper/download_cars_csv.py

export GT7_LOG_LEVEL="DEBUG" # Change to "INFO" or "ERROR" as needed
export GT7_PLAYSTATION_IP="192.168.1.103"  # Replace with your actual IP address
$pythonvenv/python3 -m bokeh serve --show .