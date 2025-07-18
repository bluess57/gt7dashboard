pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# python helper/download_cars_csv.py
# run unit tests >> python -m unittest discover

$Env:BOKEH_BROWSER="C:/Program\ Files/Google/Chrome/Application/chrome.exe %s &"

python -m bokeh serve --show .

Read-Host -Prompt "Press Enter to continue..."