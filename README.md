[![Build Status](https://dev.azure.com/tpaviot/pythonocc-generator/_apis/build/status/tpaviot.pythonocc-generator?branchName=master)](https://dev.azure.com/tpaviot/pythonocc-generator/_build/latest?definitionId=11)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/512945885d214293995c482e31efd0d7)](https://www.codacy.com/gh/tpaviot/pythonocc-generator/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=tpaviot/pythonocc-generator&amp;utm_campaign=Badge_Grade)

pythonocc-generator
-------------------

pythonocc-generator is a subproject of pythonocc, a Python library designed for 3D modeling features. pythonocc is aimed at developers who are developing CAD/PDM/PLM applications.

pythonocc-generator is specifically focused on automatic SWIG (Simple Wrapper Interface Generator) interface file generation from OpenCascade C++ header files. It utilizes CppHeaderParser (https://github.com/robotpy/robotpy-cppheaderparser) to parse .hxx headers and perform code generation.

To use pythonocc-generator, you will need to have OpenCascade C++ library installed, as it relies on its header files for interface generation. You can find more information about pythonocc at (http://github.com/tpaviot/pythonocc-core).

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
