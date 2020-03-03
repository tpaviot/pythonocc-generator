[![Travis Badge](https://travis-ci.org/tpaviot/pythonocc-generator.svg?branch=master)](https://travis-ci.org/tpaviot/pythonocc-generator)

pythonocc-generator
-------------------

pythonocc is a python library whose purpose is to provide 3D modeling
features. It is intended to developers who aim at developing
CAD/PDM/PLM applications.

pythonocc is built using SWIG (http://www.swig.org) ,
Simple Wrapper Interface Generator, from a set of '.i' SWIG files.

pythonocc-generator is the pythonocc subproject dedicated to automatic
SWIG '.i' files generation from OCE or opencascade C++ header files. It relies on a 
fork of CppHeaderParser (https://github.com/robotpy/robotpy-cppheaderparser)
to parse hxx headers and perform code generation.

How to create a local copy of the repository?
---------------------------------------------

    $ git clone git://github.com/tpaviot/pythonocc-generator.git

How to stay up to date with latest developements?
-------------------------------------------------

    $ cd pythonocc-generator
    $ git pull

How to use ?
------------

Install required dependencies (cppheaderparsr, ply):

    $ pip install - requirements.txt

Edit/Modify the wrapper-generator.conf file then

    $ cd src
    $ python generate_wrapper.py

Requirements
------------
The current developments target opencascade 7.4.0 (http://dev.opencascade.org), source can be downloaded at https://github.com/tpaviot/oce/releases/tag/official-upstream-packages.

All .i SWIG files are created and copied to the generated_swig_files path
defined in the wrapper-generator.conf


License
-------
You can redistribute it and/or modify it under the terms of the GNU
General Public License version 3 as published by the Free Software Foundation.
