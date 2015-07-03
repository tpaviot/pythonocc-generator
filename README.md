pythonocc-generator
-------------------

pythonocc is a python library whose purpose is to provide 3D modeling
features. It is intended to developers who aim at developing
CAD/PDM/PLM applications.

pythonocc is built using the SWIG (http://www.swig.org),
Simple Wrapper Interface Generator, from a set of '.i' SWIG files.

pythonocc-generator is the pythonocc subproject dedicated to automatic
SWIG '.i' files generator from OCE C++ header files. It relies on CppHeaderParser
(https://bitbucket.org/senex/cppheaderparser) to perform code generation.

How to create a local copy of the repository?
---------------------------------------------

    git clone git://github.com/tpaviot/pythonocc-generator.git

How to stay up to date with latest developements?
-------------------------------------------------

    cd pythonocc-generator
    git pull

How to use ?
------------

Edit/Modify the wrapper-generator.conf file then

    cd src
    python generate_wrapper.py

Requirements
------------
You need OCE (http://github.com/tpaviot/oce) release 0.16.0 or 0.16.1 headers.

All .i SWIG files are created and copied to the generated_swig_files path
defined in the wrapper-generator.conf


License
-------
You can redistribute it and/or modify it under the terms of the GNU
General Public License version 3 as published by the Free Software Foundation.
