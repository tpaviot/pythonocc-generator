#!/usr/bin/python
##Copyright 2018 Thomas Paviot (tpaviot@gmail.com)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# From pythooocc-0.18.2, pythonocc follows a new structure:
# All SWIG wrapped modules are moved to OCC.Core whereas they used
# to stand in the OCC package.
# in order to ensure backward compatiblity,
# a warning is raised if the old import is used.
# For instance:
# >>> from OCC.BRepPrimAPI import *
# /.../lib/python3.6/site-packages/OCC/BRepPrimAPI.py:3: DeprecationWarning:
#OCC.BRepPrimAPI is deprecated since pythonocc-0.18.2. Use OCC.Core.BRepPrimAPI
#warnings.warn("OCC.BRepPrimAPI is deprecated since pythonocc-0.18.2. Use OCC.Core.BRepPrimAPI", DeprecationWarning)
# but the script will still work.

from __future__ import print_function

import glob
import os
import os.path
try:  # Python2
    import ConfigParser
except:  # Python3
    import configparser as ConfigParser
import sys

from Modules import *

all_toolkits = [TOOLKIT_Foundation,
                TOOLKIT_Modeling,
                TOOLKIT_Visualisation,
                TOOLKIT_DataExchange,
                TOOLKIT_OCAF,
                TOOLKIT_SMesh,
                TOOLKIT_VTK]
TOOLKITS = {}
for tk in all_toolkits:
    TOOLKITS.update(tk)

config = ConfigParser.ConfigParser()
config.read('wrapper_generator.conf')


# swig output path
PYTHONOCC_CORE_PATH = config.get('pythonocc-core', 'path')
DEPRECATED_MODULES_PATH = os.path.join(PYTHONOCC_CORE_PATH, 'src', 'SWIG_files', 'deprecated_modules')

assert os.path.isdir(DEPRECATED_MODULES_PATH)
all_modules = OCE_MODULES + SALOME_SPLITTER_MODUlES + SMESH_MODULES

template = """import warnings
warnings.simplefilter('once', DeprecationWarning)
warnings.warn("OCC.%s is deprecated since pythonocc-0.18.2. Use OCC.Core.%s", DeprecationWarning)

from OCC.Core.%s import *
"""

for module in all_modules:
    module_name = module[0]
    print(module_name)
    module_file = open(os.path.join(DEPRECATED_MODULES_PATH, "%s.py" % module_name), "w")
    module_file.write(template % (module_name, module_name, module_name))
    module_file.close()
