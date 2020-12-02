import glob
import os
from Modules import *

occt_src_dir = '/home/thomas/Téléchargements/opencascade-7.5.0/src'
occt_toolkits = glob.glob(os.path.join(occt_src_dir, 'TK*'))

# for each toolit, we parse the
t = {}
for occt_tk in occt_toolkits:
	f = open(os.path.join(occt_tk, "PACKAGES"), "r")
	d = f.read().splitlines()
	f.close()
	toolkit_name = os.path.basename(occt_tk)
	#print(toolkit_name, d)
	t[toolkit_name] = d

ALL_TOOLKITS = [TOOLKIT_Foundation,
                TOOLKIT_Modeling,
                TOOLKIT_Visualisation,
                TOOLKIT_DataExchange,
                TOOLKIT_OCAF,
                TOOLKIT_VTK]
TOOLKITS = {}
for tk in ALL_TOOLKITS:
    TOOLKITS.update(tk)

# compare the two dictionnaries
for tk_name in t:
	if tk_name in TOOLKITS:
		modules = t[tk_name]
		other_modules = TOOLKITS[tk_name]
		# check that modules are wrapped
		for m in modules:
			if m not in other_modules:
				print(m, "module not wrapped, should be in toolkit", tk_name)
	else:
		print(tk_name, "toolkit not wrapped")

