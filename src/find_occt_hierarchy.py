import json
import os
import glob

OCCT_DIRECTORY = "/home/thomas/Téléchargements/OCCT-7_8_1_ii/"
OCCT_SRC_PATH = os.path.join(OCCT_DIRECTORY, "src")

# load all TK folders
all_toolkits = glob.glob(os.path.join(OCCT_SRC_PATH, "TK*"))

toolkits = {}
# loop over toolkits
for toolkit in all_toolkits:
    toolkit_name = toolkit.split(os.sep)[-1]
    with open(os.path.join(toolkit, "PACKAGES"), "r") as f:
        packages = [l.strip() for l in f.readlines()]
    # alphabetical sort
    packages.sort()
    # add the entry to the dict
    toolkits[toolkit_name] = packages

# save to json
with open("toolkits.json", "w") as f:
    f.write(json.dumps(toolkits, indent=4, ensure_ascii=True))
