# compare occt package/module structure and current pythonocc wrapper status
import itertools
from pathlib import Path

from _modules import TOOLKITS

occt_src_dir = Path("/home/thomas/Téléchargements/occt-770/src")
occt_toolkits = occt_src_dir.glob("TK*")

# First check which toolkits are currently adressed by the wrapper

# for each toolit, we parse the occt source file structure
t = {}
for occt_tk in occt_toolkits:
    t[occt_tk.name] = (occt_tk / "PACKAGES").read_text(encoding="utf8").splitlines()

# build the flattened list of opencascade modules
occt_modules = list(itertools.chain(*list(t.values())))

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
for wrapped_modules in TOOLKITS.values():
    for m in wrapped_modules:
        if m not in occt_modules:
            print("pythonocc module ", m, "not part of opencascade")
