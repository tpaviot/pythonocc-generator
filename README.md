[![Build Status](https://dev.azure.com/tpaviot/pythonocc-generator/_apis/build/status/tpaviot.pythonocc-generator?branchName=review%2Fazure)](https://dev.azure.com/tpaviot/pythonocc-generator/_build/latest?definitionId=11&branchName=review%2Fazure)

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

How to stay up to date with latest developments?
-------------------------------------------------

    $ cd pythonocc-generator
    $ git pull

How to use ?
------------

Install required dependencies (cppheaderparsr, ply):

    $ pip install -r requirements.txt

Edit/Modify the wrapper-generator.conf file then

    $ cd src
    $ python generate_wrapper.py

Requirements
------------
The current developments target opencascade 7.6.2 (http://dev.opencascade.org).


License
-------
You can redistribute it and/or modify it under the terms of the GNU
General Public License version 3 as published by the Free Software Foundation.
