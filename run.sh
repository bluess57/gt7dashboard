#!/bin/bash

mypython="/home/ian/gt7dashboard-1/python/bin"

$mypython/pip3 install -r requirements.txt

$mypython/python3 helper/download_cars_csv.py

$mypython/python3 -m bokeh serve --show .
