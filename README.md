[![Build Status](https://dev.azure.com/tpaviot/pythonocc-generator/_apis/build/status/tpaviot.pythonocc-generator?branchName=master)](https://dev.azure.com/tpaviot/pythonocc-generator/_build/latest?definitionId=11)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/512945885d214293995c482e31efd0d7)](https://www.codacy.com/gh/tpaviot/pythonocc-generator/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=tpaviot/pythonocc-generator&amp;utm_campaign=Badge_Grade)

pythonocc-generator
-------------------

pythonocc is a python library whose purpose is to provide 3D modeling
features. It is intended to developers who aim at developing
CAD/PDM/PLM applications.

pythonocc is built using SWIG (http://www.swig.org) ,
Simple Wrapper Interface Generator, from a set of interface SWIG files.

pythonocc-generator is the pythonocc subproject dedicated to automatic
SWIG interface files generation from Opencascade C++ header files. It relies on CppHeaderParser (https://github.com/robotpy/robotpy-cppheaderparser) to parse hxx headers and perform code generation.

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
The current developments target opencascade 7.7.0 (http://dev.opencascade.org).


License
-------
You can redistribute it and/or modify it under the terms of the GNU
General Public License version 3 as published by the Free Software Foundation.
