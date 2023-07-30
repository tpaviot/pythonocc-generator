# compare occt package/module structure and current pythonocc wrapper status
import glob
import itertools
import os
from Modules import *

occt_src_dir = "/home/thomas/Téléchargements/occt-770/src"
occt_toolkits = glob.glob(os.path.join(occt_src_dir, "TK*"))

# First check which toolkits are currently adressed by the wrapper

# for each toolit, we parse the occt source file structure
t = {}
for occt_tk in occt_toolkits:
    with open(os.path.join(occt_tk, "PACKAGES"), "r") as f:
        d = f.read().splitlines()
    toolkit_name = os.path.basename(occt_tk)
    t[toolkit_name] = d

# build the flattened list of opencascade modules
occt_modules = list(itertools.chain(*list(t.values())))

ALL_TOOLKITS = [
    TOOLKIT_Foundation,
    TOOLKIT_Modeling,
    TOOLKIT_Visualisation,
    TOOLKIT_DataExchange,
    TOOLKIT_OCAF,
    TOOLKIT_VTK,
]
TOOLKITS = {}
for tk in ALL_TOOLKITS:
    TOOLKITS |= tk

# compare the two dictionnaries
for tk_name, modules in t.items():
    if tk_name in TOOLKITS:
        other_modules = TOOLKITS[tk_name]
        # check that modules are wrapped
        for m in modules:
            if m not in other_modules:
                print(m, "module not wrapped, should be in toolkit", tk_name)
    else:
        print(tk_name, "toolkit not wrapped")

# on the other side, verify that all wrapped modules are actually part of opencascade
# (some packages may be removed or renamed from one release to the other)
for tk_name in t:
    if tk_name in TOOLKITS:
        modules = t[tk_name]
        for m in modules:
            if m not in occt_modules:
                print("pythonocc module ", m, "not part of opencascade")
