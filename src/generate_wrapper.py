#!/usr/bin/python
##Copyright 2008-2019 Thomas Paviot (tpaviot@gmail.com)

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

###########
# imports #
###########
import configparser
import datetime
import glob
import logging
from operator import itemgetter
import os
import os.path
import platform
import re
import subprocess
import sys
import time

from Modules import *

# import CppHeaderParser
def path_from_root(*pathelems):
    return os.path.join(__rootpath__, *pathelems)
__rootpath__ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(path_from_root('src', 'robotpy-cppheaderparser'))

import CppHeaderParser

##############################################
# Load configuration file and setup settings #
##############################################
config = configparser.ConfigParser()
config.read('wrapper_generator.conf')
# pythonocc version
PYTHONOCC_VERSION = config.get('pythonocc-core', 'version')
# oce headers location
OCE_INCLUDE_DIR = config.get('OCE', 'include_dir')
if not os.path.isdir(OCE_INCLUDE_DIR):
    raise AssertionError("OCE include dir %s not found." % OCE_INCLUDE_DIR)

# smesh, if any
SMESH_INCLUDE_DIR = config.get('SMESH', 'include_dir')
if not os.path.isdir(SMESH_INCLUDE_DIR):
    logging.warning("SMESH include dir %s not found. SMESH wrapper not generated." % SMESH_INCLUDE_DIR)
# swig output path
PYTHONOCC_CORE_PATH = config.get('pythonocc-core', 'path')
SWIG_OUTPUT_PATH = os.path.join(PYTHONOCC_CORE_PATH, 'src', 'SWIG_files', 'wrapper')
HEADERS_OUTPUT_PATH = os.path.join(PYTHONOCC_CORE_PATH, 'src', 'SWIG_files', 'headers')
# cmake output path, i.e. the location where the __init__.py file is created
CMAKE_PATH = os.path.join(PYTHONOCC_CORE_PATH, 'cmake')

###################################################
# Set logger, to log both to a file and to stdout #
# code from https://stackoverflow.com/questions/13733552/logger-configuration-to-log-to-file-and-print-to-stdout
###################################################
log_formatter = logging.Formatter("[%(levelname)-5.5s]  %(message)s")
log = logging.getLogger()
log.setLevel(logging.INFO)
log_file_name = os.path.join(SWIG_OUTPUT_PATH, 'generator.log')
# ensure log file is emptied before running the generator
lf = open(log_file_name, 'w')
lf.close()

file_handler = logging.FileHandler(log_file_name)
file_handler.setFormatter(log_formatter)
log.addHandler(file_handler)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
log.addHandler(console_handler)

####################
# Global variables #
####################
ALL_TOOLKITS = [TOOLKIT_Foundation,
                TOOLKIT_Modeling,
                TOOLKIT_Visualisation,
                TOOLKIT_DataExchange,
                TOOLKIT_OCAF,
                TOOLKIT_SMesh,
                TOOLKIT_VTK]
TOOLKITS = {}
for tk in ALL_TOOLKITS:
    TOOLKITS.update(tk)

LICENSE_HEADER = """/*
Copyright 2008-2019 Thomas Paviot (tpaviot@gmail.com)

This file is part of pythonOCC.
pythonOCC is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

pythonOCC is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with pythonOCC.  If not, see <http://www.gnu.org/licenses/>.
*/
"""

# check if SWIG_OUTPUT_PATH exists, otherwise create it
if not os.path.isdir(SWIG_OUTPUT_PATH):
    os.mkdir(SWIG_OUTPUT_PATH)

# the following var is set when the module
# is created
CURRENT_MODULE = None

PYTHON_MODULE_DEPENDENCY = []
HEADER_DEPENDENCY = []

# remove headers that can't be parse by CppHeaderParser
HXX_TO_EXCLUDE_FROM_CPPPARSER = ['NCollection_StlIterator.hxx',
                                 'NCollection_CellFilter.hxx',
                                 'Standard_CLocaleSentry.hxx',
                                 'TColStd_PackedMapOfInteger.hxx',
                                 # this file has to be fixed
                                 # there's a missing include
                                 'Aspect_VKeySet.hxx',
                                 'TPrsStd_AISPresentation.hxx',
                                 'TPrsStd_AISViewer.hxx',
                                 'StepToTopoDS_Tool.hxx',
                                 'AIS_DataMapOfSelStat.hxx',
                                 'BVH_IndexedBoxSet.hxx',
                                 'AIS_Axis.hxx',
                                 'BRepApprox_SurfaceTool.hxx',
                                 'BRepBlend_BlendTool.hxx',
                                 'BRepBlend_HCurveTool.hxx',
                                 'BRepBlend_HCurve2dTool.hxx',
                                 'IntWalk_PWalking.hxx',
                                 'HLRAlgo_PolyHidingData.hxx',
                                 'HLRAlgo_Array1OfPHDat.hxx',
                                 'Standard_Dump.hxx',  # to avoid a dependency of Standard over TCollection
                                 'IMeshData_ParametersListArrayAdaptor.hxx',
                                 'BRepMesh_CustomBaseMeshAlgo.hxx',
                                 'BRepMesh_CylinderRangeSplitter.hxx',
                                 'BRepMesh_DefaultRangeSplitter.hxx',
                                 'BRepMesh_BoundaryParamsRangeSplitter.hxx',
                                 'BRepMesh_ConeRangeSplitter.hxx',
                                 'BRepMesh_NURBSRangeSplitter.hxx',
                                 'BRepMesh_SphereRangeSplitter.hxx',
                                 'BRepMesh_TorusRangeSplitter.hxx',
                                 'BRepMesh_UVParamRangeSplitter.hxx'
                                 ]

# some includes fail at being compiled
HXX_TO_EXCLUDE_FROM_BEING_INCLUDED = ['AIS_DataMapOfSelStat.hxx', # TODO : report the bug upstream
                                      # same for the following
                                      'AIS_DataMapIteratorOfDataMapOfSelStat.hxx',
                                      # file has to be fixed, missing include
                                      'NCollection_CellFilter.hxx',
                                      'Aspect_VKeySet.hxx',
                                      'TPrsStd_AISPresentation.hxx',
                                      'Interface_ValueInterpret.hxx',
                                      'TPrsStd_AISViewer.hxx',
                                      'StepToTopoDS_Tool.hxx',
                                      'BVH_IndexedBoxSet.hxx',
                                      'AIS_Axis.hxx',
                                      # report the 3 following to upstream, buggy
                                      # error: ‘ChFiDS_ChamfMode’ does not name a type;
                                      'ChFiKPart_ComputeData_ChPlnPln.hxx',
                                      'ChFiKPart_ComputeData_ChPlnCyl.hxx',
                                      'ChFiKPart_ComputeData_ChPlnCon.hxx',
                                      # others
                                      'BRepApprox_SurfaceTool.hxx',
                                      'BRepBlend_BlendTool.hxx',
                                      'BRepBlend_HCurveTool.hxx',
                                      'BRepBlend_HCurve2dTool.hxx',
                                      'IntWalk_PWalking.hxx',
                                      'HLRAlgo_PolyHidingData.hxx',
                                      'HLRAlgo_Array1OfPHDat.hxx',
                                      'ShapeUpgrade_UnifySameDomain.hxx',
                                      'IMeshData_ParametersListArrayAdaptor.hxx',
                                      'BRepMesh_CustomBaseMeshAlgo.hxx',
                                      'BRepMesh_CylinderRangeSplitter.hxx',
                                      'BRepMesh_DefaultRangeSplitter.hxx',
                                      'BRepMesh_BoundaryParamsRangeSplitter.hxx',
                                      'BRepMesh_ConeRangeSplitter.hxx',
                                      'BRepMesh_NURBSRangeSplitter.hxx',
                                      'BRepMesh_SphereRangeSplitter.hxx',
                                      'BRepMesh_TorusRangeSplitter.hxx',
                                      'BRepMesh_UVParamRangeSplitter.hxx'
                                      ]

# some typedefs parsed by CppHeader can't be wrapped
# and generate SWIG syntax errors. We just forget
# about wrapping those typedefs
TYPEDEF_TO_EXCLUDE = ['Handle_Standard_Transient',
                      'NCollection_DelMapNode',
                      'BOPDS_DataMapOfPaveBlockCommonBlock',
                      # BOPCol following templates are already wrapped in TColStd
                      # which causes issues with SWIg
                      'BOPCol_MapOfInteger', 'BOPCol_SequenceOfReal', 'BOPCol_DataMapOfIntegerInteger',
                      'BOPCol_DataMapOfIntegerReal', 'BOPCol_IndexedMapOfInteger', 'BOPCol_ListOfInteger',
                      'IntWalk_VectorOfWalkingData',
                      'IntWalk_VectorOfInteger',
                      'TopoDS_AlertWithShape',
                      'gp_TrsfNLerp',
                      'TopOpeBRepTool_IndexedDataMapOfSolidClassifier',
                      #
                      'Graphic3d_Vec2u',
                      'Graphic3d_Vec3u',
                      'Graphic3d_Vec4u',
                      'Select3D_BndBox3d',
                      'SelectMgr_TriangFrustums',
                      'SelectMgr_TriangFrustumsIter',
                      'SelectMgr_MapOfObjectSensitives',
                      'Graphic3d_IndexedMapOfAddress',
                      'Graphic3d_MapOfObject',
                      'Storage_PArray',
                      'Interface_StaticSatisfies',
                      'IMeshData::ICurveArrayAdaptor'
                     ]


# The list of all enums defined in oce
ALL_ENUMS = []

# HArray1 apperead in occt 7x
# They are a kind of collection defined in NCollection_DefineHArray1
# a macro define this kind of object
ALL_HARRAY1 = {}
# same for NCollection_DefineHarray2
ALL_HARRAY2 = {}
# same for NCollection_DefineHSequence
ALL_HSEQUENCE = {}

# the list of all handles defined by the
# DEFINE_STANDARD_HANDLE occ macro
ALL_STANDARD_HANDLES = ['SMESH_MeshVSLink']

# the list of al classes that inherit from Standard_Transient
# and, as a consequence, need the %wrap_handle and %make_alias macros
ALL_STANDARD_TRANSIENTS = ['Standard_Transient']

BOPDS_HEADER_TEMPLATE = '''
%include "BOPCol_NCVector.hxx";
'''

INTPOLYH_HEADER_TEMPLATE = '''
%include "IntPolyh_Array.hxx";
%include "IntPolyh_ArrayOfTriangles.hxx";
%include "IntPolyh_SeqOfStartPoints.hxx";
%include "IntPolyh_ArrayOfEdges.hxx";
%include "IntPolyh_ArrayOfTangentZones.hxx";
%include "IntPolyh_ArrayOfSectionLines.hxx";
%include "IntPolyh_ListOfCouples.hxx";
%include "IntPolyh_ArrayOfPoints.hxx";
'''

BVH_HEADER_TEMPLATE = '''
%include "BVH_Box.hxx";
%include "BVH_PrimitiveSet.hxx";
'''

PRS3D_HEADER_TEMPLATE = '''
%include "Prs3d_Point.hxx";
'''

BREPALGOAPI_HEADER = '''
%include "BRepAlgoAPI_Algo.hxx";
'''

GRAPHIC3D_DEFINE_HEADER = '''
%define Handle_Graphic3d_TextureSet Handle(Graphic3d_TextureSet)
%enddef
%define Handle_Aspect_DisplayConnection Handle(Aspect_DisplayConnection)
%enddef
%define Handle_Graphic3d_NMapOfTransient Handle(Graphic3d_NMapOfTransient)
%enddef
'''

NCOLLECTION_HEADER_TEMPLATE = '''
%include "NCollection_TypeDef.hxx";
%include "NCollection_Array1.hxx";
%include "NCollection_Array2.hxx";
%include "NCollection_Map.hxx";
%include "NCollection_DefaultHasher.hxx";
%include "NCollection_List.hxx";
%include "NCollection_Sequence.hxx";
%include "NCollection_DataMap.hxx";
%include "NCollection_IndexedMap.hxx";
%include "NCollection_IndexedDataMap.hxx";
%include "NCollection_DoubleMap.hxx";
%include "NCollection_DefineAlloc.hxx";
%include "Standard_Macro.hxx";
%include "Standard_DefineAlloc.hxx";
%include "NCollection_UBTree.hxx";
%include "NCollection_UBTreeFiller.hxx";
%include "NCollection_Lerp.hxx";
%include "NCollection_Vector.hxx";
%include "NCollection_Vec2.hxx";
%include "NCollection_Vec3.hxx";
%include "NCollection_Vec4.hxx";
%include "NCollection_Mat4.hxx";
%include "NCollection_TListIterator.hxx";
%include "NCollection_UtfString.hxx";
%include "NCollection_UtfIterator.hxx";
%include "NCollection_SparseArray.hxx";

%ignore NCollection_List::First();
%ignore NCollection_List::Last();
%ignore NCollection_TListIterator::Value();
'''

TEMPLATES_TO_EXCLUDE = ['gp_TrsfNLerp',
                        # IntPolyh templates don't work
                        'IntPolyh_Array',
                        # and this one also
                        'NCollection_CellFilter',
                        'BVH_PrimitiveSet',
                        'BVH_Builder',
                        'std::pair',
                        # for Graphic3d to compile
                        'Graphic3d_UniformValue',
                        'NCollection_Shared',
                        'NCollection_Handle',
                        'NCollection_DelMapNode'
                        #'NCollection_IndexedMap',
                        #'NCollection_DataMap'
                        'BOPTools_BoxSet',
                        'BOPTools_PairSelector',
                        'BOPTools_BoxSet',
                        'BOPTools_BoxSelector',
                        'BOPTools_PairSelector'
                        ]

HARRAY1_TEMPLATE = """
class HClassName : public _Array1Type_, public Standard_Transient {
  public:
    HClassName(const Standard_Integer theLower, const Standard_Integer theUpper);
    HClassName(const Standard_Integer theLower, const Standard_Integer theUpper, const _Array1Type_::value_type& theValue);
    HClassName(const _Array1Type_& theOther);
    const _Array1Type_& Array1();
    _Array1Type_& ChangeArray1();
};
%make_alias(HClassName)

"""

HARRAY2_TEMPLATE = """
class HClassName : public _Array2Type_, public Standard_Transient {
  public:
    HClassName(const Standard_Integer theRowLow, const Standard_Integer theRowUpp, const Standard_Integer theColLow,
                const Standard_Integer theColUpp);
    HClassName(const Standard_Integer theRowLow, const Standard_Integer theRowUpp, const Standard_Integer theColLow,
               const Standard_Integer theColUpp, const _Array2Type_::value_type& theValue);
    HClassName(const _Array2Type_& theOther);
    const _Array2Type_& Array2 ();
    _Array2Type_& ChangeArray2 (); 
};
%make_alias(HClassName)

"""

HSEQUENCE_TEMPLATE = """
class HClassName : public _SequenceType_, public Standard_Transient {
    HClassName();
    HClassName(const _SequenceType_& theOther);
    const _SequenceType_& Sequence();
    void Append (const _SequenceType_::value_type& theItem);
    void Append (_SequenceType_& theSequence);
    _SequenceType_& ChangeSequence();
};
%make_alias(HClassName)

"""

NCOLLECTION_ARRAY1_EXTEND_TEMPLATE = '''
%extend NCollection_Array1_Template_Instanciation {
    %pythoncode {
    def __getitem__(self, index):
        if index + self.Lower() > self.Upper():
            raise IndexError("index out of range")
        else:
            return self.Value(index + self.Lower())

    def __setitem__(self, index, value):
        if index + self.Lower() > self.Upper():
            raise IndexError("index out of range")
        else:
            self.SetValue(index + self.Lower(), value)

    def __len__(self):
        return self.Length()

    def __iter__(self):
        self.low = self.Lower()
        self.up = self.Upper()
        self.current = self.Lower() - 1
        return self

    def next(self):
        if self.current >= self.Upper():
            raise StopIteration
        else:
            self.current += 1
        return self.Value(self.current)

    __next__ = next
    }
};
'''


def get_log_header():
    """ returns a timestand to be appended to the SWIG file
    Useful for development
    """
    os_name = platform.linux_distribution()[0] + ' ' + platform.system() + ' ' + platform.release()
    generator_git_revision = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip().decode('utf8')
    now = str(datetime.datetime.now())
    # find the OCC VERSION targeted by the wrapper
    # the OCCT version is available from the Standard_Version.hxx header
    # e.g. define OCC_VERSION_COMPLETE     "7.4.0"
    standard_version_header = os.path.join(OCE_INCLUDE_DIR, "Standard_Version.hxx")
    occ_version = "unknown"
    if os.path.isfile(standard_version_header):
        with open(standard_version_header, 'r') as f:
            file_lines = f.readlines()
        for l in file_lines:
            if l.startswith("#define OCC_VERSION_COMPLETE"):
                occ_version = l.split('"')[1].strip()
    timestamp = """
############################
Running pythonocc-generator.
############################
git revision : %s

operating system : %s

occt version targeted : %s

date : %s
############################
""" % (generator_git_revision, os_name, occ_version, now)
    return timestamp


def get_log_footer(total_time):
    footer = """
#################################################
SWIG interface file generation completed in {:.2f}s
#################################################
""".format(total_time)
    return footer


def reset_header_depency():
    global HEADER_DEPENDENCY
    HEADER_DEPENDENCY = ['TColgp', 'TColStd', 'TCollection', 'Storage']


def check_is_persistent(class_name):
    """
    Checks, whether a class belongs to the persistent classes (and not to the transient ones)
    """
    for occ_module in ['PFunction', 'PDataStd', 'PPrsStd', 'PDF',
                       'PDocStd', 'PDataXtd', 'PNaming', 'PCDM_Document']:
        if class_name.startswith(occ_module):
            return True
    return False


def filter_header_list(header_list, exclusion_list):
    """ From a header list, remove hxx to HXX_TO_EXCLUDE
    The files to be excluded is specificed in the exlusion list
    """
    for header_to_remove in exclusion_list:
        if os.path.join(OCE_INCLUDE_DIR, header_to_remove) in header_list:
            header_list.remove(os.path.join(OCE_INCLUDE_DIR, header_to_remove))
        elif os.path.join(SMESH_INCLUDE_DIR, header_to_remove) in header_list:
            header_list.remove(os.path.join(SMESH_INCLUDE_DIR, header_to_remove))
    # remove platform dependent files
    # this is done to have the same SWIG files on every platform
    # wnt specific
    header_list = [x for x in header_list if not 'WNT' in x.lower()]
    header_list = [x for x in header_list if not 'wnt' in x.lower()]
    # linux
    header_list = [x for x in header_list if not 'X11' in x]
    header_list = [x for x in header_list if not 'XWD' in x]
    # and osx
    header_list = [x for x in header_list if not 'Cocoa' in x]
    return header_list


def test_filter_header_list():
    if sys.platform != 'win32':
        assert filter_header_list(['something', 'somethingWNT'], HXX_TO_EXCLUDE_FROM_CPPPARSER) == ['something']


def case_sensitive_glob(wildcard):
    """
    Case sensitive glob for Windows.
    Designed for handling of GEOM and Geom modules
    This function makes the difference between GEOM_* and Geom_* under Windows
    """
    flist = glob.glob(wildcard)
    pattern = wildcard.split('*')[0]
    f = []
    for file_ in flist:
        if pattern in file_:
            f.append(file_)
    return f


def get_all_module_headers(module_name):
    """ Returns a list with all header names
    """
    mh = case_sensitive_glob(os.path.join(OCE_INCLUDE_DIR, '%s.hxx' % module_name))
    mh += case_sensitive_glob(os.path.join(OCE_INCLUDE_DIR, '%s_*.hxx' % module_name))
    mh += case_sensitive_glob(os.path.join(SMESH_INCLUDE_DIR, '%s.hxx' % module_name))
    mh += case_sensitive_glob(os.path.join(SMESH_INCLUDE_DIR, '%s_*.hxx' % module_name))
    mh += case_sensitive_glob(os.path.join(SMESH_INCLUDE_DIR, 'Handle_%s.hxx*' % module_name))
    mh = filter_header_list(mh, HXX_TO_EXCLUDE_FROM_BEING_INCLUDED)
    headers_list = list(map(os.path.basename, mh))
    # sort alphabetical order
    headers_list.sort()
    return headers_list


def test_get_all_module_headers():
    # 'Standard' should return some files (at lease 10)
    # this number depends on the OCE version
    headers_list_1 = get_all_module_headers("Standard")
    assert len(list(headers_list_1)) > 10
    # an empty list
    headers_list_2 = list(get_all_module_headers("something_else"))
    assert not headers_list_2


def check_has_related_handle(class_name):
    """ For a given class :
    Check if a header exists.
    """
    if check_is_persistent(class_name):
        return False

    filename = os.path.join(OCE_INCLUDE_DIR, "Handle_%s.hxx" % class_name)
    other_possible_filename = filename
    if class_name.startswith("Graphic3d"):
        other_possible_filename = os.path.join(OCE_INCLUDE_DIR, "%s_Handle.hxx" % class_name)
    return os.path.exists(filename) or os.path.exists(other_possible_filename) or need_handle(class_name)



def write__init__():
    """ creates the OCC/__init__.py file.
    In this file, the Version is created.
    The OCE version is checked into the oce-version.h file
    """
    fp__init__ = open(os.path.join(CMAKE_PATH, '__init__.py'), 'w')
    fp__init__.write('VERSION = "%s"\n' % PYTHONOCC_VERSION)
    # @TODO : then check OCE version


def need_handle(class_name):
    """ Returns True if the current parsed class needs an
    Handle to be defined. This is useful when headers define
    handles but no header """
    # @TODO what about DEFINE_RTTI ?
    return class_name in ALL_STANDARD_HANDLES or class_name in ALL_STANDARD_TRANSIENTS


def adapt_header_file(header_content):
    """ take an header filename as input.
    Returns the output of a tempfile with :
    * all occurrences of Handle(something) moved to Handle_Something
    otherwise CppHeaderParser is confused ;
    * all define RTTI moved
    """
    global ALL_STANDARD_HANDLES, ALL_HARRAY1, ALL_HARRAY2, ALL_HSEQUENCE
    # search for STANDARD_HANDLE
    outer = re.compile("DEFINE_STANDARD_HANDLE[\\s]*\\([\\w\\s]+\\,+[\\w\\s]+\\)")
    matches = outer.findall(header_content)
    if matches:
        for match in matches:
            # @TODO find inheritance name
            header_content = header_content.replace('DEFINE_STANDARD_HANDLE',
                                                    '//DEFINE_STANDARD_HANDLE')
            ALL_STANDARD_HANDLES.append(match.split('(')[1].split(',')[0])
    # Search for RTTIEXT
    outer = re.compile("DEFINE_STANDARD_RTTIEXT[\\s]*\\([\\w\\s]+\\,+[\\w\\s]+\\)")
    matches = outer.findall(header_content)
    if matches:
        for match in matches:
            # @TODO find inheritance name
            header_content = header_content.replace('DEFINE_STANDARD_RTTIEXT',
                                                    '//DEFINE_STANDARD_RTTIEXT')
     # Search for HARRAY1
    outer = re.compile("DEFINE_HARRAY1[\\s]*\\([\\w\\s]+\\,+[\\w\\s]+\\)")
    matches = outer.findall(header_content)
    if matches:
        for match in matches:
            # @TODO find inheritance name
            typename = match.split('(')[1].split(',')[0]
            base_typename = match.split(',')[1].split(')')[0]
            # we keep only te RTTI that are defined in this module,
            # to avoid cyclic references in the SWIG files
            logging.info("Found HARRAY1 definition" + typename + ':' + base_typename)
            ALL_HARRAY1[typename] = base_typename
    # Search for HARRAY2
    outer = re.compile("DEFINE_HARRAY2[\\s]*\\([\\w\\s]+\\,+[\\w\\s]+\\)")
    matches = outer.findall(header_content)
    if matches:
        for match in matches:
            # @TODO find inheritance name
            typename = match.split('(')[1].split(',')[0]
            base_typename = match.split(',')[1].split(')')[0]
            # we keep only te RTTI that are defined in this module,
            # to avoid cyclic references in the SWIG files
            logging.info("Found HARRAY2 definition" + typename + ':' + base_typename)
            ALL_HARRAY2[typename] = base_typename
   # Search for HSEQUENCE
    outer = re.compile("DEFINE_HSEQUENCE[\\s]*\\([\\w\\s]+\\,+[\\w\\s]+\\)")
    matches = outer.findall(header_content)
    if matches:
        for match in matches:
            # @TODO find inheritance name
            typename = match.split('(')[1].split(',')[0]
            base_typename = match.split(',')[1].split(')')[0]
            # we keep only te RTTI that are defined in this module,
            # to avoid cyclic references in the SWIG files
            logging.info("Found HSEQUENCE definition" + typename + ':' + base_typename)
            ALL_HSEQUENCE[typename] = base_typename
    header_content = header_content.replace('DEFINE_STANDARD_RTTI_INLINE',
                                            '//DEFINE_STANDARD_RTTI_INLINE')
    header_content = header_content.replace('Standard_DEPRECATED',
                                            '//Standard_DEPRECATED')
    # TODO : use the @deprecated python decorator to raise a Deprecation exception
    # see https://github.com/tantale/deprecated
    # each time this method is used
    # then we look for Handle(Something) use
    # and replace with Handle_Something
    outer = re.compile("Handle[\\s]*\\([\\w\\s]*\\)")
    matches = outer.findall(header_content)
    if matches:
        for match in matches:
            orig_match = match
            # matches are of the form :
            #['Handle(Graphic3d_Structure)',
            # 'Handle(Graphic3d_DataStructureManager)']
            match = match.replace(" ", "")
            match = (match.split('Handle(')[1]).split(')')[0]
            #header_content = header_content.replace(orig_match,
            #                                        'Handle_%s' % match)
            header_content = header_content.replace(orig_match,
                                                    'opencascade::handle<%s>' % match)

    # for smesh, remove EXPORTS that cause parser errors
    header_content = header_content.replace("SMESH_EXPORT", "")
    header_content = header_content.replace("SMESHCONTROLS_EXPORT", "")
    header_content = header_content.replace("SMESHDS_EXPORT", "")
    header_content = header_content.replace("STDMESHERS_EXPORT", "")
    header_content = header_content.replace("NETGENPLUGIN_EXPORT", "")
    return header_content


def parse_header(header_filename):
    """ Use CppHeaderParser module to parse header_filename
    """
    header_content = open(header_filename, 'r', encoding='ISO-8859-1').read()
    adapted_header_content = adapt_header_file(header_content)
    try:
        cpp_header = CppHeaderParser.CppHeader(adapted_header_content, "string")
    except CppHeaderParser.CppParseError as e:
        print(e)
        print("Filename : %s" % header_filename)
        print("FileContent :\n", adapted_header_content)
        sys.exit(1)
    return cpp_header


def filter_typedefs(typedef_dict):
    """ Remove some strange thing that generated SWIG
    errors
    """
    if '{' in typedef_dict:
        del typedef_dict['{']
    if ':' in typedef_dict:
        del typedef_dict[':']
    for key in list(typedef_dict):
        if key in TYPEDEF_TO_EXCLUDE:
            del typedef_dict[key]
    return typedef_dict


def test_filter_typedefs():
    a_dict = {'1': 'one', '{': 'two', 'NCollection_DelMapNode':'3'}
    assert filter_typedefs(a_dict) == {'1': 'one'}


def process_templates_from_typedefs(list_of_typedefs):
    """
    """
    wrapper_str = "/* templates */\n"
    for t in list_of_typedefs:
        template_name = t[1]
        template_type = t[0]
        # we must include
        if not (template_type.endswith("::Iterator") or template_type.endswith("::Type")):  #it's not an iterator
            # check that there's no forbidden template
            wrap_template = True
            for forbidden_template in TEMPLATES_TO_EXCLUDE:
                if forbidden_template in template_type:
                    wrap_template = False
            # sometimes the template name is weird (parenthesis, commma etc.)
            # don't consider this
            if not "_" in template_name:
                wrap_template = False
                logging.warning("Template: " + template_name + "skipped because name does'nt contain _.")
            if wrap_template:
                wrapper_str += "%%template(%s) %s;\n" %(template_name, template_type)
                # if a NCollection_Array1, extend this template to benefit from pythonic methods
                # All "Array1" classes are considered as python arrays
                # TODO : it should be a good thing to use decorators here, to avoid code duplication
                if 'NCollection_Array1' in template_type:
                    wrapper_str += NCOLLECTION_ARRAY1_EXTEND_TEMPLATE.replace("NCollection_Array1_Template_Instanciation", template_type)
        elif template_name.endswith("Iter") or "_ListIteratorOf" in template_name:  # it's a lst iterator, we use another way to wrap the template
        # #%template(TopTools_ListIteratorOfListOfShape) NCollection_TListIterator<TopTools_ListOfShape>;
            if "IteratorOf" in template_name:
                if not "opencascade::handle" in template_type:
                    typ = (template_type.split('<')[1]).split('>')[0]
                else:
                    h_typ = (template_type.split('<')[2]).split('>')[0]
                    typ = "opencascade::handle<%s>" % h_typ
            elif template_name.endswith("Iter"):
                typ = template_name.split('Iter')[0]
            wrapper_str += "%%template(%s) NCollection_TListIterator<%s>;\n" %(template_name, typ)
    wrapper_str += "/* end templates declaration */\n"
    return wrapper_str


def process_typedefs(typedefs_dict):
    """ Take a typedef dictionary and returns a SWIG definition string
    """
    templates_str = ""
    typedef_str = "/* typedefs */\n"
    templates = []
    # careful, there might be some strange things returned by CppHeaderParser
    # they should not be taken into account
    filtered_typedef_dict = filter_typedefs(typedefs_dict)
    # we check if there is any type def type that relies on an opencascade::handle
    # if this is the case, we must add the corresponding python module
    # as a dependency otherwise it leads to a runtime issue
    
    # #check_dependency(must_include)
    for template_type in filtered_typedef_dict.values():
        if "opencascade::handle" in template_type: # we must add a PYTHON DEPENDENCY
            if template_type.count('<') == 2:
                h_typ = (template_type.split('<')[2]).split('>')[0]
            elif template_type.count('<') == 1:
                h_typ = (template_type.split('<')[1]).split('>')[0]
            else:
                logging.warning("This template type cannot be handled: " + template_type)
                continue
            module = h_typ.split("_")[0]
            if module != CURRENT_MODULE:
                # need to be added to the list of dependend object
                if (module not in PYTHON_MODULE_DEPENDENCY) and (is_module(module)):
                    PYTHON_MODULE_DEPENDENCY.append(module)

    for typedef_value in filtered_typedef_dict.keys():
        # some occttype defs are actually templated classes,
        # for instance
        # typedef NCollection_Array1<Standard_Real> TColStd_Array1OfReal;
        # this must be wrapped as a typedef but rather as an instaicated class
        # the good way to proceed is:
        # %{include "NCollection_Array1.hxx"}
        # %template(TColStd_Array1OfReal) NCollection_Array1<Standard_Real>;
        # we then check if > or < are in the typedef string then we process it.
        if ("<" in "%s" % filtered_typedef_dict[typedef_value] or
                ">" in "%s" % filtered_typedef_dict[typedef_value]):
            templates.append([filtered_typedef_dict[typedef_value], typedef_value])
        typedef_str += "typedef %s %s;\n" % (filtered_typedef_dict[typedef_value], typedef_value)
        check_dependency(filtered_typedef_dict[typedef_value].split()[0])
    typedef_str += "/* end typedefs declaration */\n\n"
    # then we process templates
    # at this stage, we get a list as follows
    templates_str += process_templates_from_typedefs(templates)
    templates_str += "\n"
    return templates_str + typedef_str


def process_enums(enums_list):
    """ Take an enum list and generate a compliant SWIG string
    """
    enum_str = "/* public enums */\n"
    for enum in enums_list:
        if "name" not in enum:
            enum_name = ""
        else:
            enum_name = enum["name"]
            if not enum_name in ALL_ENUMS:
                ALL_ENUMS.append(enum_name)
        enum_str += "enum %s {\n" % enum_name
        for enum_value in enum["values"]:
            enum_str += "\t%s = %s,\n" % (enum_value["name"], enum_value["value"])
        enum_str += "};\n\n"
    enum_str += "/* end public enums declaration */\n\n"
    return enum_str


def is_return_type_enum(return_type):
    """ This method returns True is an enum is returned. For instance:
    BRepCheck_Status &
    BRepCheck_Status
    """
    for r in return_type.split():
        if r in ALL_ENUMS:
            return True
    return False


def adapt_param_type(param_type):
    param_type = param_type.replace("Standard_CString", "const char *")
    param_type = param_type.replace("DrawType", "NIS_Drawer::DrawType")
    # for SMESH
    param_type = param_type.replace("TDefaults", "SMESH_0D_Algo::TDefaults")
    param_type = param_type.replace("DistrType", "StdMeshers_NumberOfSegments::DistrType")
    param_type = param_type.replace("TWireVector", "StdMeshers_MEFISTO_2D::TWireVector")
    param_type = param_type.replace("::SMESH_Mesh", "SMESH_Mesh")
    param_type = param_type.replace("::MeshDimension", " MeshDimension")
    param_type = param_type.replace("TShapeShapeMap", " StdMeshers_ProjectionUtils::TShapeShapeMap")
    param_type = param_type.replace("TAncestorMap", "StdMeshers_ProjectionUtils::TAncestorMap")
    check_dependency(param_type)
    return param_type


def adapt_param_type_and_name(param_type_and_name):
    """ We sometime need to replace some argument type and name
    to properly deal with byref values
    """
    if (('Standard_Real &' in param_type_and_name) or
            ('Quantity_Parameter &' in param_type_and_name) or
            ('Quantity_Length &' in param_type_and_name) or
            ('V3d_Coordinate &' in param_type_and_name) or
            (param_type_and_name.startswith('double &'))) and not 'const' in param_type_and_name:
        adapted_param_type_and_name = "Standard_Real &OutValue"
    elif (('Standard_Integer &' in param_type_and_name) or
          (param_type_and_name.startswith('int &'))) and not 'const' in param_type_and_name:
        adapted_param_type_and_name = "Standard_Integer &OutValue"
    elif (('Standard_Boolean &' in param_type_and_name) or
          (param_type_and_name.startswith('bool &'))) and not 'const' in param_type_and_name:
        adapted_param_type_and_name = "Standard_Boolean &OutValue"
    elif 'FairCurve_AnalysisCode &' in param_type_and_name:
        adapted_param_type_and_name = 'FairCurve_AnalysisCode &OutValue'
    else:
        adapted_param_type_and_name = param_type_and_name
    if "& &" in adapted_param_type_and_name:
        adapted_param_type_and_name = adapted_param_type_and_name.replace("& &", "&")
    return adapted_param_type_and_name


def test_adapt_param_type_and_name():
    p1 = "Standard_Real & Xp"
    ad_p1 = adapt_param_type_and_name(p1)
    assert ad_p1 == "Standard_Real &OutValue"
    p2 = "Standard_Integer & I"
    ad_p2 = adapt_param_type_and_name(p2)
    assert ad_p2 == "Standard_Integer &OutValue"
    p3 = "int & j"
    ad_p3 = adapt_param_type_and_name(p3)
    assert ad_p3 == "Standard_Integer &OutValue"
    p4 = "double & x"
    ad_p4 = adapt_param_type_and_name(p4)
    assert ad_p4 == "Standard_Real &OutValue"


def check_dependency(item):
    """ For any type or class name passe to this function,
    returns the module name to which it belongs.
    a. Handle_Geom_Curve -> Geom
    b. Handle ( Geom2d_Curve) -> Geom2d
    c. opencascade::handle<TopoDS_TShape> -> TopoDS
    d. TopoDS_Shape -> TopoDS
    For the case 1 (a, b, c), the module has to be added to the headers list
    For the case 2 (d), the module TopoDS.i has to be added as a dependency in
    order that the class hierarchy is propagated.
    """
    if not item:
        return False
    filt = ["const ", "static ", "virtual ", "clocale_t", "pointer",
            "size_type", "void", "reference", "const_", "inline "]
    for f in filt:
        item = item.replace(f, '')
    if not item:  # if item list is empty
        return False
    # the element can be either a template ie Handle(Something) else Something_
    # or opencascade::handle<Some_Class>
    if item.startswith("Handle ("):
        item = item.split("Handle ( ")[1].split(")")[0].strip()
        module = item.split('_')[0]
    elif item.startswith("Handle_"):
        module = item.split('_')[1]
    elif item.startswith("opencascade::handle<"):
        item = item.split("<")[1].split(">")[0]
        module = item.split('_')[0]
    elif item.count('_') > 0:  # Standard_Integer or NCollection_CellFilter_InspectorXYZ
        module = item.split('_')[0]
    else:  # do nothing, it's a trap
        return False
    # we strip the module, who knows, there maybe trailing spaces
    module = module.strip()
    # TODO : is the following line really necessary ?
    if module == 'Font':  # forget about Font dependencies, issues with FreeType
        return True
    if module != CURRENT_MODULE:
        # need to be added to the list of dependend object
        if (module not in PYTHON_MODULE_DEPENDENCY) and (is_module(module)):
            PYTHON_MODULE_DEPENDENCY.append(module)
    return module


def test_check_dependency():
    dep1 = check_dependency("Handle_Geom_Curve")
    assert dep1 == "Geom"
    dep2 = check_dependency("Handle ( Geom2d_Curve)")
    assert dep2 == "Geom2d"
    dep3 = check_dependency("opencascade::handle<TopoDS_TShape>")
    assert dep3 == "TopoDS"
    dep4 = check_dependency("Standard_Integer")
    assert dep4 == "Standard"


def adapt_return_type(return_type):
    """ Remove Standard_EXPORT and everything that pollute
    the type definition
    """
    replaces = ["Standard_EXPORT ",
                "Standard_EXPORT",
                "SMESHDS_EXPORT",
                "DEFINE_STANDARD_ALLOC ",
                "DEFINE_NCOLLECTION_ALLOC :",
                "DEFINE_NCOLLECTION_ALLOC",
               ]
    for replace in replaces:
        return_type = return_type.replace(replace, "")
    return_type = return_type.strip()
    # replace Standard_CString with char *
    return_type = return_type.replace("Standard_CString", "const char *")
    # remove const if const virtual double *  # SMESH only
    return_type = return_type.replace(": static", "static")
    return_type = return_type.replace(": const", "const")
    return_type = return_type.replace("const virtual double *", "virtual double *")
    return_type = return_type.replace("DistrType", "StdMeshers_NumberOfSegments::DistrType")
    return_type = return_type.replace("TWireVector", "StdMeshers_MEFISTO_2D::TWireVector")
    return_type = return_type.replace("PGroupIDs", "SMESH_MeshEditor::PGroupIDs")
    return_type = return_type.replace("TAncestorMap", "TopTools_IndexedDataMapOfShapeListOfShape")
    return_type = return_type.replace("ErrorCode", "SMESH_Pattern::ErrorCode")
    return_type = return_type.replace("Fineness", "NETGENPlugin_Hypothesis::Fineness")
    # for instance "const TopoDS_Shape & -> ["const", "TopoDS_Shape", "&"]
    if (('gp' in return_type) and not 'TColgp' in return_type) or ('TopoDS' in return_type):
        return_type = return_type.replace('&', '')
    check_dependency(return_type)
    # check is it is an enum
    if is_return_type_enum(return_type) and "&" in return_type:
        # remove the reference
        return_type = return_type.replace("&", "")
    return return_type


def test_adapt_return_type():
    adapted_1 = adapt_return_type("Standard_EXPORT Standard_Integer")
    assert adapted_1 == "Standard_Integer"
    adapted_2 = adapt_return_type("DEFINE_STANDARD_ALLOC Standard_EXPORT static Standard_Integer")
    assert adapted_2 == "static Standard_Integer"


def adapt_function_name(f_name):
    """ Some function names may result in errors with SWIG
    """
    f_name = f_name.replace("operator", "operator ")
    return f_name


def test_adapt_function_name():
    assert adapt_function_name('operator*') == 'operator *'


def get_module_docstring(module_name):
    """ The module docstring is not provided anymore in cdl files since
    opencascade 7 and higher was released.
    Instead, the link to the official package documentation is
    used, for instance, for the gp package:
    https://www.opencascade.com/doc/occt-7.4.0/refman/html/package_gp.html
    """
    module_docstring = "%s module, see official documentation at\n" % module_name
    module_docstring += "https://www.opencascade.com/doc/occt-7.4.0/refman/html/package_%s.html" % module_name.lower()
    return module_docstring


def process_function_docstring(f):
    """ Create the docstring, for the function f,
    that will be used by the wrapper.
    For that, first check the function parameters and type
    then add the doxygen value
    """
    function_name = f["name"]
    function_name = adapt_function_name(function_name)
    string_to_return = '\t\t%feature("autodoc", "'
    # first process parameters
    parameters_string = ''
    if f["parameters"]:  # at leats one element in the least
        for param in f["parameters"]:
            param_type = adapt_param_type(param["type"])
            # remove const and &
            param_type = fix_type(param_type)
            if "gp_" in param_type:
                param_type = param_type.replace("&", "")
            param_type = param_type.strip()
            parameters_string += "\t:param %s:" % param["name"]
            #parameters_string += "\t%s(%s)" % (param["name"], param_type, )
            if "defaultValue" in param:
                def_value = adapt_default_value(param["defaultValue"])
                parameters_string += " default value is %s" % def_value
            parameters_string += "\n"
            parameters_string += "\t:type %s: %s" % (param["name"], param_type)
            parameters_string += "\n"
    # return types:
    returns_string = '\t:rtype:'
    ret = adapt_return_type(f["rtnType"])
    if ret != 'void':
        ret = ret.replace("&", "")
        ret = ret.replace("virtual", "")
        ret = fix_type(ret)
        ret = ret.replace(": static ", "")
        ret = ret.replace("static ", "")
        ret = ret.strip()
        returns_string += " %s\n" % ret
    else:
        returns_string += " None\n"
    # process doxygen strings
    doxygen_string = ""
    if "doxygen" in f:
        doxygen_string = f["doxygen"]
        # remove comment separator
        doxygen_string = doxygen_string.replace("//! ", "")
        # replace " with '
        doxygen_string = doxygen_string.replace('"', "'")
        # remove ??/ that causes a compilation issue in InterfaceGraphic
        doxygen_string = doxygen_string.replace("??", "")
        # remove <br>
        # first, a strange thing in BSplClib
        doxygen_string = doxygen_string.replace('\\ <br>', " ")
        doxygen_string = doxygen_string.replace('<br>', " ")
        # replace <me> with <self>, which is more pythonic
        doxygen_string = doxygen_string.replace('<me>', "<self>")
        # make '\r' correctly processed
        doxygen_string = doxygen_string.replace(r"\\return", "Returns")
        doxygen_string = doxygen_string.replace("\\r", "")
        # replace \n with space
        doxygen_string = doxygen_string.replace("\n", " ")
        doxygen_string = doxygen_string.replace("'\\n'", "A newline")
        # replace TRUE and FALSE with True and False
        doxygen_string = doxygen_string.replace("TRUE", "True")
        doxygen_string = doxygen_string.replace("FALSE", "False")
        # misc
        doxygen_string = doxygen_string.replace("@return", "returns")
        # replace the extra spaces
        doxygen_string = doxygen_string.replace('    ', " ")
        doxygen_string = doxygen_string.replace('   ', " ")
        doxygen_string = doxygen_string.replace('  ', " ")
        # when documentation is missing,
        # the related string is "returns the algorithm"
        # it's quite unclear
        doxygen_string = doxygen_string.replace("Returns the algorithm",
                                                "Missing detailed docstring")
        # then remove spaces from start and end
        doxygen_string = doxygen_string.strip()
        doxygen_string = "\t* " + doxygen_string + "\n"
    # concatenate everything
    final_string = doxygen_string + parameters_string + returns_string
    string_to_return += '%s") %s;\n' % (final_string.strip(), function_name)
    return string_to_return


def adapt_default_value(def_value):
    """ adapt default value """
    #def_value = def_value.replace(": : ", "")
    def_value = def_value.replace(' ', '')
    def_value = def_value.replace('"', "'")
    def_value = def_value.replace("''", '""')
    def_value = def_value.replace("PConfusion", "::Confusion")
    def_value = def_value.replace("PrecisionConfusion", "Precision::Confusion")
    def_value = def_value.replace("Precision::::Confusion", "Precision::Confusion")
    return def_value


def adapt_default_value_parmlist(parm):
    """ adapts default value to be used in swig parameter list """
    def_value = parm["defaultValue"]
    #def_value = def_value.replace(": : ", "")
    def_value = def_value.replace(' ', '')
    def_value = def_value.replace("PConfusion", "::Confusion")
    def_value = def_value.replace("PrecisionConfusion", "Precision::Confusion")
    def_value = def_value.replace("Precision::::Confusion", "Precision::Confusion")
    return def_value


def test_adapt_default_value():
    pass#assert adapt_default_value(": : MeshDim_3D") == "MeshDim_3D"


def filter_member_functions(class_name, class_public_methods, member_functions_to_exclude, class_is_abstract):
    """ This functions removes member function to exclude from
    the class methods list. Some of the members functions have to be removed
    because they can't be wrapped (usually, this results in a linkage error)
    """
    member_functions_to_process = []
    for public_method in class_public_methods:
        method_name = public_method["name"]
        if method_name in member_functions_to_exclude:
            continue
        if class_is_abstract and public_method["constructor"]:
            logging.warning("Constructor skipped for abstract class %s" % class_name)
            continue
        if method_name == "ShallowCopy":  # specific to 0.17.1 and Mingw
            continue
        if "<" in method_name:
            continue
        # finally, we add this method to process
        member_functions_to_process.append(public_method)
    return member_functions_to_process


def test_filter_member_functions():
    class_public_methods = [{"name": "method_1"},
                            {"name": "method_2"},
                            {"name": "method_3"},
                           ]
    member_functions_to_exclude = ["method_2"]
    result = filter_member_functions("klass_name", class_public_methods,
                                     member_functions_to_exclude,
                                     False)
    assert result == [{"name": "method_1"}, {"name": "method_3"}]


def process_function(f):
    """ Process function f and returns a SWIG compliant string.
    If process_docstrings is set to True, the documentation string
    from the C++ header will be used as is for the python wrapper
    """
    if f["template"]:
        return False

    # first, adapt function name, if needed
    function_name = adapt_function_name(f["name"])
    # destructors are not wrapped
    # they are shadowed by a function that calls a garbage collector
    if f["destructor"]:
        return ""
    if f["returns"] == "~":
        return ""  # a destructor that should be considered as a destructor
    if "operator Handle" in function_name:
        return ""  # difficult to wrap, useless
    if "operator ++" in function_name:
        return ""  # impossible to wrap in python
    if "operator ()" in function_name:
        return""  # impossible to wrap in python
    if "operator []" in function_name:
        return ""  # impossible to wrap in python
    if "operator <<" in function_name:
        return ""
    if "operator ^" in function_name:
        return ""
    if "operator !" in function_name:
        return ""
    # special process for operator ==
    if "operator ==" in function_name:
        param = f["parameters"][0]
        param_type = param["type"].replace("&", "")
        return """
        %%extend{
            bool __eq_wrapper__(%s other) {
            if (*self==other) return true;
            else return false;
            }
        }
        %%pythoncode {
        def __eq__(self, right):
            try:
                return self.__eq_wrapper__(right)
            except:
                return False
        }
        """ % param_type
    # special process for operator !=
    if "operator !=" in function_name:
        param = f["parameters"][0]
        param_type = param["type"].replace("&", "")
        return """
        %%extend{
            bool __ne_wrapper__(%s other) {
            if (*self!=other) return true;
            else return false;
            }
        }
        %%pythoncode {
        def __ne__(self, right):
            try:
                return self.__ne_wrapper__(right)
            except:
                return True
        }
        """ % param_type
    # special process for operator +=
    if "operator +=" in function_name:
        param = f["parameters"][0]
        param_type = param["type"].replace("&", "")
        return """
        %%extend{
            void __iadd_wrapper__(%s other) {
            *self += other;
            }
        }
        %%pythoncode {
        def __iadd__(self, right):
            self.__iadd_wrapper__(right)
            return self
        }
        """ % param_type
    # special process for operator *=
    if "operator *=" in function_name:
        param = f["parameters"][0]
        param_type = param["type"].replace("&", "")
        return """
        %%extend{
            void __imul_wrapper__(%s other) {
            *self *= other;
            }
        }
        %%pythoncode {
        def __imul__(self, right):
            self.__imul_wrapper__(right)
            return self
        }
        """ % param_type
    # special process for operator -=
    if "operator -=" in function_name:
        param = f["parameters"][0]
        param_type = param["type"].replace("&", "")
        return """
        %%extend{
            void __isub_wrapper__(%s other) {
            *self -= other;
            }
        }
        %%pythoncode {
        def __isub__(self, right):
            self.__isub_wrapper__(right)
            return self
        }
        """ % param_type
    # special process for operator -=
    if "operator /=" in function_name:
        param = f["parameters"][0]
        param_type = param["type"].replace("&", "")
        return """
        %%extend{
            void __itruediv_wrapper__(%s other) {
            *self /= other;
            }
        }
        %%pythoncode {
        def __itruediv__(self, right):
            self.__itruediv_wrapper__(right)
            return self
        }
        """ % param_type
    # special case : Standard_OStream or Standard_IStream is the only parameter
    if len(f["parameters"]) == 1:
        param = f["parameters"][0]
        param_type = param["type"].replace("&", "")
        if 'Standard_OStream' in '%s' % param_type:
            str_function = """
        %%feature("autodoc", "1");
        %%extend{
            std::string %sToString() {
            std::stringstream s;
            self->%s(s);
            return s.str();}
        };
        """ % (function_name, function_name)
            return str_function
        if ('std::istream &' in '%s' % param_type) or ('Standard_IStream' in param_type):
            return """
        %%feature("autodoc", "1");
        %%extend{
            void %sFromString(std::string src) {
            std::stringstream s(src);
            self->%s(s);}
        };
        """ % (function_name, function_name)
    if function_name == "DumpJson":
        str_function = """
        %feature("autodoc", "1");
        %extend{
            std::string DumpJsonToString(int depth=-1) {
            std::stringstream s;
            self->DumpJson(s, depth);
            return s.str();}
        };
        """
        return str_function
    if "TYPENAME" in f["rtnType"]:
        return ""  # something in NCollection
    if function_name == "DEFINE_STANDARD_RTTIEXT":
        return ""
    if function_name == "Handle":  # TODO: make it possible!
    # this is because Handle (something) some function can not be
    # handled by swig
        return ""
    # enable autocompactargs feature to enable compilation with swig>3.0.3
    str_function = '\t\t/****************** %s ******************/\n' % function_name
    str_function += '\t\t%%feature("compactdefaultargs") %s;\n' % function_name
    str_function += process_function_docstring(f)
    str_function += "\t\t"
    # return type
    # in the return type, we remove the Standard_EXPORT macro
    # and all that pollutes the wrapping
    # Careful: for constructors, we have to remove the "void"
    # return type from the SWIG wrapper
    # otherwise it causes the compiler to fail
    # with "incorrect use of ..."
    # function name
    if f["constructor"]:
        return_type = ""
    else:
        return_type = adapt_return_type(f["rtnType"])
    if f['static'] and 'static' not in return_type:
        return_type = 'static ' + return_type
    # Case where primitive values are accessed by reference
    # one method Get* that returns the object
    # one method Set* that sets the object
    if return_type in ['Standard_Integer &', 'Standard_Real &', 'Standard_Boolean &',
                       'Standard_Integer&', 'Standard_Real&', 'Standard_Boolean&']:
        logging.warning('Creating Get and Set methods for method %s' % function_name)
        modified_return_type = return_type.split(" ")[0]
        # we compute the parameters type and name, seperated with comma
        getter_params_type_and_names = []
        getter_params_only_names = []
        for param in f["parameters"]:
            param_type_and_name = "%s %s" % (adapt_param_type(param["type"]), param["name"])
            getter_params_type_and_names.append(param_type_and_name)
            getter_params_only_names.append(param["name"])
        setter_params_type_and_names = getter_params_type_and_names + ['%s value' % modified_return_type]
        
        getter_params_type_and_names_str_csv = ','.join(getter_params_type_and_names)
        setter_params_type_and_names_str_csv = ','.join(setter_params_type_and_names)
        getter_params_only_names_str_csv = ','.join(getter_params_only_names)
        
        str_function = """
        %%feature("autodoc","1");
        %%extend {
            %s Get%s(%s) {
            return (%s) $self->%s(%s);
            }
        };
        %%feature("autodoc","1");
        %%extend {
            void Set%s(%s) {
            $self->%s(%s)=value;
            }
        };\n""" % (modified_return_type, function_name, getter_params_type_and_names_str_csv,
                   modified_return_type, function_name, getter_params_only_names_str_csv,
                   function_name, setter_params_type_and_names_str_csv,
                   function_name, getter_params_only_names_str_csv)
        return str_function
    str_function += "%s " % return_type
    # function name
    str_function += "%s " % function_name
    # process parameters
    str_function += "("
    for param in f["parameters"]:
        param_type = adapt_param_type(param["type"])
        if "Handle_T &" in param_type:
            return False  # skipe thi function, it will raise a compilation exception, it's something like a template
        if 'array_size' in param:
            param_type_and_name = "%s %s[%s]" % (param_type, param["name"], param["array_size"])
        else:
            param_type_and_name = "%s %s" % (param_type, param["name"])
        str_function += adapt_param_type_and_name(param_type_and_name)
        if "defaultValue" in param:
            def_value = adapt_default_value_parmlist(param)
            str_function += " = %s" % def_value
        # argument separator
        str_function += ","
    # before closing parenthesis, remove the last comma
    if str_function.endswith(","):
        str_function = str_function[:-1]
    str_function += ");\n"
    # if the function is HashCode, we add immediately after
    # an __hash__ overloading
    if function_name == "HashCode" and len(f["parameters"]) == 1:
        str_function += """
        %extend {
            Standard_Integer __hash__() {
            return $self->HashCode(2147483647);
            }
        };
        """
    str_function = str_function.replace('const const', 'const') + '\n'
    return str_function


def process_free_functions(free_functions_list):
    """ process a string for free functions
    """
    str_free_functions = ""
    sorted_free_functions_list = sorted(free_functions_list, key=itemgetter('name'))
    for free_function in sorted_free_functions_list:
        ok_to_wrap = process_function(free_function)
        if ok_to_wrap:
            str_free_functions += ok_to_wrap
    return str_free_functions


def process_methods(methods_list):
    """ process a list of public process_methods
    """
    str_functions = ""
    # sort methods according to the method name
    sorted_methods_list = sorted(methods_list, key=itemgetter('name'))
    for function in sorted_methods_list:
        # don't process friend methods
        if not function["friend"]:
            ok_to_wrap = process_function(function)
            if ok_to_wrap:
                str_functions += ok_to_wrap
    return str_functions


def must_ignore_default_destructor(klass):
    """ Some classes, like for instance BRepFeat_MakeCylindricalHole
    has a protected destructor that must explicitely be ignored
    This is done by the directive
    %ignore Class::~Class() just before the wrapper definition
    """
    class_protected_methods = klass['methods']['protected']
    for protected_method in class_protected_methods:
        if protected_method["destructor"]:
            return True
    class_private_methods = klass['methods']['private']
    # finally, return True, the default constructor can be safely defined
    for private_method in class_private_methods:
        if private_method["destructor"]:
            return True
    return False


def class_can_have_default_constructor(klass):
    """ By default, classes don't have default constructor.
    We only use default constructor for classes that :
    have DEFINE_STANDARD_ALLOC
    and has not any private or protected constructor
    """
    # class must not be an abstract class
    if klass["abstract"]:
        return False
    # we look for the DEFINE_STANDARD_ALLOC string in the class definition
    class_public_methods = klass['methods']['public']
    IS_STANDARD_ALLOC = False
    for public_method in class_public_methods:
        if "rtnType" in public_method:
            if "DEFINE_STANDARD_ALLOC" in public_method["rtnType"]:
                IS_STANDARD_ALLOC = True
                break
    if not IS_STANDARD_ALLOC:
        return False
    # moreover, we have to ensure that no private or protected constructor is defined
    class_protected_methods = klass['methods']['protected']
    # finally, return True, the default constructor can be safely defined
    for protected_method in class_protected_methods:
        if protected_method["constructor"]:
            return False
    class_private_methods = klass['methods']['private']
    # finally, return True, the default constructor can be safely defined
    for private_method in class_private_methods:
        if private_method["constructor"]:
            return False
    # finallyn returns True
    return True


def build_inheritance_tree(classes_dict):
    """ From the classes dict, return a list of classes
    with the class ordered from the most abtract to
    the more specialized. The more abstract will be
    processed first.
    """
    global ALL_STANDARD_TRANSIENTS
    # first, we build two dictionaries
    # the first one, level_0_classes
    # contain class names that does not inherit from
    # any other class
    # they will be processed first
    level_0_classes = []
    # the inheritance dict contains the relationships
    # betwwen a class and its upper class.
    # the dict schema is as the following :
    # inheritance_dict = {'base_class_name': 'upper_class_name'}
    inheritance_dict = {}
    for klass in classes_dict.values():
        class_name = klass["name"]
        upper_classes = klass["inherits"]
        nbr_upper_classes = len(upper_classes)
        if nbr_upper_classes == 0:
            level_0_classes.append(class_name)
        # if class has one or more ancestors
        # for class with one or two ancestors, let's process them
        # the same. Anyway, whan there are two ancestors (only a few cases),
        # one of the two ancestors come from another module.
        elif nbr_upper_classes == 1:
            upper_class_name = upper_classes[0]["class"]
            # if the upper class depends on another module
            # add it to the level 0 list.
            if upper_class_name.split("_")[0] != CURRENT_MODULE:
                level_0_classes.append(class_name)
            # else build the inheritance tree
            else:
                inheritance_dict[class_name] = upper_class_name
        elif nbr_upper_classes == 2:
            # if one, or the other
            upper_class_name_1 = upper_classes[0]["class"]
            class_1_module = upper_class_name_1.split("_")[0]
            upper_class_name_2 = upper_classes[1]["class"]
            class_2_module = upper_class_name_2.split("_")[0]
            if class_1_module == upper_class_name_2 == CURRENT_MODULE:
                logging.warning("Tthis is a special case, where the 2 ancestors belong the same module. Class %s skipped." % class_name)
            if class_1_module == CURRENT_MODULE:
                inheritance_dict[class_name] = upper_class_name_1
            elif class_2_module == CURRENT_MODULE:
                inheritance_dict[class_name] = upper_class_name_2
            elif upper_class_name_1 == upper_class_name_2:  # the samemodule, but external, not the current one
                level_0_classes.append(class_name)
            inheritance_dict[class_name] = upper_class_name_1
        else:
            # prevent multiple inheritance: OCE only has single
            # inheritance
            logging.warning("Class %s has %i ancestors and is skipped." % (class_name, nbr_upper_classes))
    # then, after that, we process both dictionaries, list so
    # that we reorder class.
    # first, we build something called the inheritance_depth.
    # that is to say a dict with the class name and the number of upper classes
    # inheritance_depth = {'Standard_Transient':0, 'TopoDS_Shape':1}
    inheritance_depth = {}
    # first we fill in with level_0:
    for class_name in level_0_classes:
        inheritance_depth[class_name] = 0
    upper_classes = inheritance_dict.values()
    for base_class_name in inheritance_dict:
        tmp = base_class_name
        i = 0
        while tmp in inheritance_dict:
            tmp = inheritance_dict[tmp]
            i += 1
        inheritance_depth[base_class_name] = i
    # after that, we traverse the inheritance depth dict
    # to order classes names according to their depth.
    # first classes with level 0, then 1, 2 etc.
    # at last, we return the class_list containing a list
    # of ordered classes.
    class_list = []
    for class_name, depth_value in sorted(inheritance_depth.items(),
                                          key=lambda kv: (kv[1], kv[0])):
        if class_name in classes_dict:  # TODO: should always be the case!
            class_list.append(classes_dict[class_name])
    # Then we build the list of all classes that inherit from Standard_Transient
    # at some point. These classes will need the %wrap_handle and %make_alias_macros
    for klass in class_list:
        upper_class = klass['inherits']
        class_name = klass['name']
        if upper_class:
            upper_class_name = klass['inherits'][0]['class']
            if upper_class_name in ALL_STANDARD_TRANSIENTS:
                # this class inherits from a Standard_Transient base class
                # so we add it to the ALL_STANDARD_TRANSIENTS list:
                if not klass in ALL_STANDARD_TRANSIENTS:
                    ALL_STANDARD_TRANSIENTS.append(class_name)
    return class_list


def fix_type(type_str):
    type_str = type_str.replace("Standard_Boolean &", "bool")
    type_str = type_str.replace("Standard_Boolean", "bool")
    type_str = type_str.replace("Standard_Real", "float")
    type_str = type_str.replace("Standard_Integer", "int")
    type_str = type_str.replace("const", "")
    type_str = type_str.replace("& &", "&")
    return type_str


def process_harray1():
    wrapper_str = "/* harray1 class */"
    for HClassName in ALL_HARRAY1:
        if HClassName.startswith(CURRENT_MODULE + "_"):
            _Array1Type_ = ALL_HARRAY1[HClassName]
            wrapper_for_harray1 = HARRAY1_TEMPLATE.replace("HClassName", HClassName)
            wrapper_for_harray1 = wrapper_for_harray1.replace("_Array1Type_", _Array1Type_)
            wrapper_str += wrapper_for_harray1
    wrapper_str += "\n"
    return wrapper_str


def process_harray2():
    wrapper_str = "/* harray2 class */"
    for HClassName in ALL_HARRAY2:
        if HClassName.startswith(CURRENT_MODULE + "_"):
            _Array2Type_ = ALL_HARRAY2[HClassName]
            wrapper_for_harray2 = HARRAY2_TEMPLATE.replace("HClassName", HClassName)
            wrapper_for_harray2 = wrapper_for_harray2.replace("_Array2Type_", _Array2Type_)
            wrapper_str += wrapper_for_harray2
    wrapper_str += "\n"
    return wrapper_str


def process_hsequence():
    wrapper_str = "/* harray2 class */"
    for HClassName in ALL_HSEQUENCE:
        if HClassName.startswith(CURRENT_MODULE + "_"):
            _SequenceType_ = ALL_HSEQUENCE[HClassName]
            wrapper_for_hsequence = HSEQUENCE_TEMPLATE.replace("HClassName", HClassName)
            wrapper_for_hsequence = wrapper_for_hsequence.replace("_SequenceType_", _SequenceType_)
            wrapper_str += wrapper_for_hsequence
    wrapper_str += "\n"
    return wrapper_str

def process_handles(classes_dict, exclude_classes, exclude_member_functions):
    """ Check wether a class has to be wrapped as a handle
    using the wrap_handle swig macro.
    This code is a bit redundant with process_classes, but this step
    appeared to be placed before typedef ans templates definition
    """
    wrap_handle_str = "/* handles */\n"
    if exclude_classes == ['*']:  # don't wrap any class
        return ""
    inheritance_tree_list = build_inheritance_tree(classes_dict)
    for klass in inheritance_tree_list:
        # class name
        class_name = klass["name"]
        if class_name in exclude_classes:
            # if the class has to be excluded,
            # we go on with the next one to be processed
            continue
        if check_has_related_handle(class_name) or class_name == "Standard_Transient":
            wrap_handle_str += "%%wrap_handle(%s)\n" % class_name
    for HClassName in ALL_HARRAY1:
        if HClassName.startswith(CURRENT_MODULE + "_"):
            wrap_handle_str += "%%wrap_handle(%s)\n" % HClassName
    for HClassName in ALL_HARRAY2:
        if HClassName.startswith(CURRENT_MODULE + "_"):
            wrap_handle_str += "%%wrap_handle(%s)\n" % HClassName
    for HClassName in ALL_HSEQUENCE:
        if HClassName.startswith(CURRENT_MODULE + "_"):
            wrap_handle_str += "%%wrap_handle(%s)\n" % HClassName
    wrap_handle_str += "/* end handles declaration */\n\n"
    return wrap_handle_str

def process_classes(classes_dict, exclude_classes, exclude_member_functions):
    """ Generate the SWIG string for the class wrapper.
    Works from a dictionary of all classes, generated with CppHeaderParser.
    All classes but the ones in exclude_classes are wrapped.
    excludes_classes is a list with the class names to exclude_classes
    exclude_member_functions is a dict with classes names as keys and member
    function names as values
    """
    if exclude_classes == ['*']:  # don't wrap any class
        return ""
    class_def_str = ""
    inheritance_tree_list = build_inheritance_tree(classes_dict)
    logging.info("Wrap classes :")
    for klass in inheritance_tree_list:
        # class name
        class_name = klass["name"]
        # header
        stars = ''.join(['*' for i in range(len(class_name ) + 9)])
        class_def_str += "/%s\n* class %s *\n%s/\n" % (stars, class_name, stars)
        #
        if class_name in exclude_classes:
            # if the class has to be excluded,
            # we go on with the next one to be processed
            continue
        # ensure the class returned by CppHeader is defined in this module
        # otherwise we go on with the next class
        if not class_name.startswith(CURRENT_MODULE):
            continue
        # we rename the class if the module is the same name
        # for instance TopoDS is both a module and a class
        # then we rename the class with lowercase
        logging.info(class_name)
        if class_name == CURRENT_MODULE:
            class_def_str += "%%rename(%s) %s;\n" % (class_name.lower(), class_name)
        # then process the class itself
        if not class_can_have_default_constructor(klass):
            class_def_str += "%%nodefaultctor %s;\n" % class_name
        if must_ignore_default_destructor(klass):
        # check if the destructor is protected or private
            class_def_str += "%%ignore %s::~%s();\n" % (class_name, class_name)
        # SMDS_ITerator is templated
        if class_name == "SMDS_Iterator":
            class_def_str += "template<typename VALUE> "
        # then defines the wrapper
        class_def_str += "class %s" % class_name
        # inheritance process
        inherits_from = klass["inherits"]
        if inherits_from: # at least 1 ancestor
            inheritance_name = inherits_from[0]["class"]
            check_dependency(inheritance_name)
            inheritance_access = inherits_from[0]["access"]
            class_def_str += " : %s %s" % (inheritance_access, inheritance_name)
            if len(inherits_from) == 2: ## 2 ancestors
                inheritance_name_2 = inherits_from[1]["class"]
                check_dependency(inheritance_name_2)
                inheritance_access_2 = inherits_from[1]["access"]
                class_def_str += ", %s %s" % (inheritance_access_2, inheritance_name_2)
        class_def_str += " {\n"
        # process class typedefs here
        typedef_str = '\tpublic:\n'
        for typedef_value in list(klass["typedefs"]['public']):
            if ')' in typedef_value:
                continue
            typedef_str += "typedef %s %s;\n" % (klass._public_typedefs[typedef_value], typedef_value)
        class_def_str += typedef_str
        # process class enums here
        class_enums_list = klass["enums"]['public']
        ###### Nested classes
        nested_classes = klass["nested_classes"]
        for n in nested_classes:
            nested_class_name = n["name"]
            logging.info("Wrap nested class %s::%s" % (class_name, nested_class_name))
            class_def_str += "\t\tclass " + nested_class_name + " {};\n"
        ####### class enums
        if class_enums_list:
            class_def_str += process_enums(class_enums_list)
        # process class properties here
        properties_str = ''
        for property_value in list(klass["properties"]['public']):
            if 'NCollection_Vec2' in property_value['type']: # issue in Aspect_Touch
                logging.warning('Wrong type in class property : NCollection_Vec2')
                continue
            if 'using' in property_value['type']:
                logging.warning('Wrong type in class property : using')
                continue
            if 'return' in property_value['type']:
                logging.warning('Wrong type in class property : return')
                continue
            if 'std::map<' in property_value['type']:
                logging.warning('Wrong type in class property std::map')
                continue  # TODO bug with SMESH_0D_Algo etc.
            if property_value['constant'] or 'virtual' in property_value['raw_type'] or 'Standard_EXPORT' in property_value['raw_type'] or 'allback' in property_value['raw_type']:
                continue
            if 'array_size' in property_value:
                temp = "\t\t%s %s[%s];\n" % (fix_type(property_value['type']), property_value['name'], property_value['array_size'])
            else:
                temp = "\t\t%s %s;\n" % (fix_type(property_value['type']), property_value['name'])
            properties_str += temp
        # @TODO : classe typedefs (for instance BRepGProp_MeshProps)
        class_def_str += properties_str
        # process methods here
        class_public_methods = klass['methods']['public']
        # remove, from this list, all functions that
        # are excluded
        try:
            members_functions_to_exclude = exclude_member_functions[class_name]
        except KeyError:
            members_functions_to_exclude = []
        # if ever the header defines DEFINE STANDARD ALLOC
        # then we wrap a copy constructor. Very convenient
        # to create python classes that inherit from OCE ones!
        if class_name in ['TopoDS_Shape', 'TopoDS_Vertex']:
            class_def_str += '\t\t%feature("autodoc", "1");\n'
            class_def_str += '\t\t%s(const %s arg0);\n' % (class_name, class_name)
        methods_to_process = filter_member_functions(class_name, class_public_methods, members_functions_to_exclude, klass["abstract"])
        class_def_str += process_methods(methods_to_process)
        # then terminate the class definition
        class_def_str += "};\n\n"
        #
        # at last, check if there is a related handle
        # if yes, we integrate it into it's shadow class
        # TODO: check that the following is not restricted
        # to protected destructors !
        class_def_str += '\n'
        if check_has_related_handle(class_name) or class_name == "Standard_Transient":
            # Extend class by GetHandle method
            class_def_str += '%%make_alias(%s)\n\n' % class_name

        # We add pickling for TopoDS_Shapes
        if class_name == 'TopoDS_Shape':
            class_def_str += '%extend TopoDS_Shape {\n%pythoncode {\n'
            class_def_str += '\tdef __getstate__(self):\n'
            class_def_str += '\t\tfrom .BRepTools import BRepTools_ShapeSet\n'
            class_def_str += '\t\tss = BRepTools_ShapeSet()\n'
            class_def_str += '\t\tss.Add(self)\n'
            class_def_str += '\t\tstr_shape = ss.WriteToString()\n'
            class_def_str += '\t\tindx = ss.Locations().Index(self.Location())\n'
            class_def_str += '\t\treturn str_shape, indx\n'
            class_def_str += '\tdef __setstate__(self, state):\n'
            class_def_str += '\t\tfrom .BRepTools import BRepTools_ShapeSet\n'
            class_def_str += '\t\ttopods_str, indx = state\n'
            class_def_str += '\t\tss = BRepTools_ShapeSet()\n'
            class_def_str += '\t\tss.ReadFromString(topods_str)\n'
            class_def_str += '\t\tthe_shape = ss.Shape(ss.NbShapes())\n'
            class_def_str += '\t\tlocation = ss.Locations().Location(indx)\n'
            class_def_str += '\t\tthe_shape.Location(location)\n'
            class_def_str += '\t\tself.this = the_shape.this\n'
            class_def_str += '\t}\n};\n'
        # add SMDS_ITerator template instanciation
        if class_name == "SMDS_Iterator":
            class_def_str += "%template(SMDS_ElemIteratorPtr) SMDS_Iterator<const SMDS_MeshElement *>;\n"
            class_def_str += "%template(SMDS_NodeIteratorPtr) SMDS_Iterator<const SMDS_MeshNode *>;\n"
            class_def_str += "%template(SMDS_0DElementIteratorPtr) SMDS_Iterator<const SMDS_Mesh0DElement *>;\n"
            class_def_str += "%template(SMDS_EdgeIteratorPtr) SMDS_Iterator<const SMDS_MeshEdge *>;\n"
            class_def_str += "%template(SMDS_FaceIteratorPtr) SMDS_Iterator<const SMDS_MeshFace *>;\n"
            class_def_str += "%template(SMDS_VolumeIteratorPtr) SMDS_Iterator<const SMDS_MeshVolume *>;\n\n"
        # for each class, overload the __repr__ method to avoid things like:
        # >>> print(box)
        #<OCC.TopoDS.TopoDS_Shape; proxy of <Swig Object of type 'TopoDS_Shape *' at 0x02
        #BCF770> >
        class_def_str += '%%extend %s {\n' % class_name
        class_def_str += '\t%' + 'pythoncode {\n'
        class_def_str += '\t__repr__ = _dumps_object\n'
        class_def_str += '\t}\n};\n\n'
    return class_def_str


def is_module(module_name):
    """ Checks if the name passed as a parameter is
    (or is not) a module that aims at being wrapped.
    'Standard' should return True
    'inj' should return False
    """
    for mod in OCE_MODULES + SMESH_MODULES:
        if mod[0] == module_name:
            return True
    return False


def test_is_module():
    assert is_module('Standard') is True
    assert is_module('something') is False


def parse_module(module_name):
    """ A module is defined by a set of headers. For instance AIS,
    gp, BRepAlgoAPI etc. For each module, generate three or more
    SWIG files. This parser returns :
    module_enums, module_typedefs, module_classes
    """
    module_headers = glob.glob('%s/%s_*.hxx' % (OCE_INCLUDE_DIR, module_name))
    module_headers += glob.glob('%s/%s.hxx' % (OCE_INCLUDE_DIR, module_name))
    if not module_headers:  # this can be smesh modules or the splitter
        module_headers = glob.glob('%s/%s_*.hxx' % (SMESH_INCLUDE_DIR, module_name))
        module_headers += glob.glob('%s/%s.hxx' % (SMESH_INCLUDE_DIR, module_name))
    # filter those headers
    module_headers = filter_header_list(module_headers, HXX_TO_EXCLUDE_FROM_CPPPARSER)
    cpp_headers = map(parse_header, module_headers)
    module_typedefs = {}
    module_enums = []
    module_classes = {}
    module_free_functions = []
    for header in cpp_headers:
        # build the typedef dictionary
        module_typedefs.update(header.typedefs)
        # build the enum list
        module_enums += header.enums
        # build the class dictionary
        module_classes.update(header.classes.items())
        # build the free functions list
        module_free_functions += header.functions
    return module_typedefs, module_enums, module_classes, module_free_functions


class ModuleWrapper:
    def __init__(self, module_name, additional_dependencies,
                 exclude_classes, exclude_member_functions):
        # Reinit global variables
        global CURRENT_MODULE, PYTHON_MODULE_DEPENDENCY
        CURRENT_MODULE = module_name
        # all modules depend, by default, upon Standard, NCollection and others
        if module_name != 'Standard':
            PYTHON_MODULE_DEPENDENCY = ['Standard', 'NCollection']
            reset_header_depency()
        else:
            PYTHON_MODULE_DEPENDENCY = []

        logging.info("## Processing module %s" % module_name)
        self._module_name = module_name
        self._module_docstring = get_module_docstring(module_name)
        # parse
        typedefs, enums, classes, free_functions = parse_module(module_name)
        #enums
        self._enums_str = process_enums(enums)
        # handles
        self._wrap_handle_str = process_handles(classes, exclude_classes,
                                                exclude_member_functions)
        # templates and typedefs
        self._typedefs_str = process_typedefs(typedefs)
        #classes
        self._classes_str = process_classes(classes, exclude_classes,
                                            exclude_member_functions)
        # special classes defined by the HARRAY1 and HARRAY2 macro
        self._classes_str += process_harray1()
        self._classes_str += process_harray2()
        self._classes_str += process_hsequence()
        # free functions
        self._free_functions_str = process_free_functions(free_functions)
        # other dependencies
        self._additional_dependencies = additional_dependencies + HEADER_DEPENDENCY
        # generate swig file
        self.generate_SWIG_files()

    def generate_SWIG_files(self):
        #
        # Main file
        #
        f = open(os.path.join(SWIG_OUTPUT_PATH, "%s.i" % self._module_name), "w")
        # write header
        f.write(LICENSE_HEADER)
        # write module docstring
        # for instante define GPDOCSTRING
        docstring_macro = "%sDOCSTRING" % self._module_name.upper()
        f.write('%%define %s\n' % docstring_macro)
        f.write('"%s"\n' % self._module_docstring)
        f.write('%enddef\n')
        # module name
        f.write('%%module (package="OCC.Core", docstring=%s) %s\n\n' % (docstring_macro, self._module_name))
        # write windows pragmas to avoid compiler errors
        win_pragmas = """
%{
#ifdef WNT
#pragma warning(disable : 4716)
#endif
%}

"""
        f.write(win_pragmas)
        # common includes
        includes = ["CommonIncludes", "ExceptionCatcher",
                    "FunctionTransformers", "Operators", "OccHandle"]
        for include in includes:
            f.write("%%include ../common/%s.i\n" % include)
        f.write("\n\n")
        ## SMDS special process
        # the following lines enable to wrap SMDS_Iterators
        # that are boost_shared pointers
        if self._module_name == "SMDS":
            f.write("""%include <boost_shared_ptr.i>
%shared_ptr(SMDS_Iterator<const SMDS_MeshElement *>)
%shared_ptr(SMDS_Iterator<const SMDS_MeshNode *>)
%shared_ptr(SMDS_Iterator<const SMDS_Mesh0DElement *>)
%shared_ptr(SMDS_Iterator<const SMDS_MeshEdge *>)
%shared_ptr(SMDS_Iterator<const SMDS_MeshFace *>)
%shared_ptr(SMDS_Iterator<const SMDS_MeshVolume *>)
%shared_ptr(SMDS_IteratorOfElements)

""")
        # Here we write required dependencies, headers, as well as
        # other swig interface files
        f.write("%{\n")
        if self._module_name == "Adaptor3d": # occt bug in headr file, won't compile otherwise
            f.write("#include<Adaptor2d_HCurve2d.hxx>\n")
        if self._module_name == "AdvApp2Var": # windows compilation issues
            f.write("#if defined(_WIN32)\n#include <windows.h>\n#endif\n")
        if self._module_name in ["BRepMesh", "XBRepMesh"]: # wrong header order with gcc4 issue #63
            f.write("#include<BRepMesh_Delaun.hxx>\n")
        if self._module_name == "ShapeUpgrade":
            f.write("#include<Precision.hxx>\n#include<ShapeUpgrade_UnifySameDomain.hxx>\n")
        module_headers = glob.glob('%s/%s_*.hxx' % (OCE_INCLUDE_DIR, self._module_name))
        module_headers += glob.glob('%s/%s.hxx' % (OCE_INCLUDE_DIR, self._module_name))
        module_headers += glob.glob('%s/%s_*.hxx' % (SMESH_INCLUDE_DIR, self._module_name))
        module_headers += glob.glob('%s/%s.hxx' % (SMESH_INCLUDE_DIR, self._module_name))
        module_headers.sort()

        mod_header = open(os.path.join(HEADERS_OUTPUT_PATH, "%s_module.hxx" % self._module_name), "w")
        mod_header.write("#ifndef %s_HXX\n" % self._module_name.upper())
        mod_header.write("#define %s_HXX\n\n" % self._module_name.upper())
        mod_header.write(LICENSE_HEADER)
        mod_header.write("\n")

        for module_header in filter_header_list(module_headers, HXX_TO_EXCLUDE_FROM_BEING_INCLUDED):
            if not os.path.basename(module_header) in HXX_TO_EXCLUDE_FROM_BEING_INCLUDED:
                mod_header.write("#include<%s>\n" % os.path.basename(module_header))
        mod_header.write("\n#endif // %s_HXX\n" % self._module_name.upper())

        f.write("#include<%s_module.hxx>\n" % self._module_name)
        f.write("\n//Dependencies\n")
        # Include all dependencies
        for dep in PYTHON_MODULE_DEPENDENCY:
            f.write("#include<%s_module.hxx>\n" % dep)
        for add_dep in self._additional_dependencies:
            f.write("#include<%s_module.hxx>\n" % add_dep)
    
        f.write("%};\n")
        for dep in PYTHON_MODULE_DEPENDENCY:
            if is_module(dep):
                f.write("%%import %s.i\n" % dep)
        # for NCollection, we add template classes that can be processed
        # automatically with SWIG
        if self._module_name == "NCollection":
            f.write(NCOLLECTION_HEADER_TEMPLATE)
        if self._module_name == "BVH":
            f.write(BVH_HEADER_TEMPLATE)
        if self._module_name == "Prs3d":
            f.write(PRS3D_HEADER_TEMPLATE)
        if self._module_name == "Graphic3d":
            f.write(GRAPHIC3D_DEFINE_HEADER)
        if self._module_name == "BRepAlgoAPI":
            f.write(BREPALGOAPI_HEADER)
        # write public enums
        f.write(self._enums_str)
        # write wrap_handles
        f.write(self._wrap_handle_str)
        # write type_defs
        f.write(self._typedefs_str)
        # write classes_definition
        f.write(self._classes_str)
        # write free_functions definition
        #TODO: we should write free functions here,
        # but it sometimes fail to compile
        #f.write(self._free_functions_str)
        f.close()


def process_module(module_name):
    all_modules = OCE_MODULES + SMESH_MODULES
    module_exist = False
    for module in all_modules:
        if module[0] == module_name:
            module_exist = True
            module_additionnal_dependencies = module[1]
            module_exclude_classes = module[2]
            if len(module) == 4:
                modules_exclude_member_functions = module[3]
            else:
                modules_exclude_member_functions = {}
            #print("Next to be processed : %s " % module_name)
            ModuleWrapper(module_name,
                          module_additionnal_dependencies,
                          module_exclude_classes,
                          modules_exclude_member_functions)
    if not module_exist:
        raise NameError('Module %s not defined' % module_name)


def process_toolkit(toolkit_name):
    """ Generate wrappers for modules depending on a toolkit
    For instance : TKernel, TKMath etc.
    """
    modules_list = TOOLKITS[toolkit_name]
    logging.info("Processing toolkit %s ===" % toolkit_name)
    for module in sorted(modules_list):
        process_module(module)


def process_all_toolkits():
    parallel_build = config.get('build', 'parallel_build')
    if parallel_build == "True":  # multitask
        logging.info("Multiprocess mode")
        from multiprocessing import Pool
        pool = Pool()
        try:
            # the timeout is required for proper handling when exciting the parallel build
            pool.map_async(process_toolkit, TOOLKITS).get(timeout=1000)
        except KeyboardInterrupt:
            pool.terminate()
            pool.join()
        else:
            pool.close()
            pool.join()
    else:  # single task
        logging.info("Single process mode")
        for toolkit in sorted(TOOLKITS):
            process_toolkit(toolkit)


def run_unit_tests():
    test_is_module()
    test_filter_header_list()
    test_get_all_module_headers()
    test_adapt_return_type()
    test_filter_typedefs()
    test_adapt_function_name()
    test_filter_member_functions()
    test_adapt_param_type_and_name()
    test_adapt_default_value()
    test_check_dependency()


if __name__ == '__main__':
    # do it each time, does not take too much time, prevent regressions
    run_unit_tests()
    logging.info(get_log_header())
    start_time = time.time()
    if len(sys.argv) > 1:
        for module_to_process in sys.argv[1:]:
            process_module(module_to_process)
    else:
        write__init__()
        process_all_toolkits()
    end_time = time.time()
    total_time = end_time - start_time
    # footer
    logging.info(get_log_footer(total_time))
