##Copyright 2008-2015 Thomas Paviot (tpaviot@gmail.com)

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

from __future__ import print_function

import glob
import os
import os.path
import ConfigParser
import sys
import re

from Modules import *


# import CppHeaderParser
def path_from_root(*pathelems):
    return os.path.join(__rootpath__, *pathelems)
__rootpath__ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path = [path_from_root('src', 'contrib', 'cppheaderparser')] + sys.path
import CppHeaderParser

all_toolkits = [TOOLKIT_Foundation,
                TOOLKIT_Modeling,
                TOOLKIT_Visualisation,
                TOOLKIT_DataExchange,
                TOOLKIT_OCAF,
                #TOOLKIT_SMesh,
                TOOLKIT_VTK]
TOOLKITS = {}
for tk in all_toolkits:
    TOOLKITS.update(tk)

#
# Load configuration file and setup settings
#
header_year = "2008-2016"
author = "Thomas Paviot"
author_email = "tpaviot@gmail.com"
license_header = """
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
"""
config = ConfigParser.ConfigParser()
config.read('wrapper_generator.conf')
# pythonocc version
PYTHONOCC_VERSION = config.get('pythonocc-core', 'version')
# oce headers location
try:
    oce_base_dir = config.get('OCE', 'base_dir')
    OCE_INCLUDE_DIR = os.path.join(oce_base_dir, 'include', 'oce')
except ConfigParser.NoOptionError:
    OCE_INCLUDE_DIR = config.get('OCE', 'include_dir')
if not os.path.isdir(OCE_INCLUDE_DIR):
    raise AssertionError("OCE include dir %s not found." % OCE_INCLUDE_DIR)
# smesh, if any
smesh_base_dir = config.get('SMESH', 'base_dir')
SMESH_INCLUDE_DIR = os.path.join(smesh_base_dir, 'include', 'smesh')
if not os.path.isdir(SMESH_INCLUDE_DIR):
    print("SMESH include dir %s not found. SMESH wrapper not generated." % SMESH_INCLUDE_DIR)
# swig output path
SWIG_OUTPUT_PATH = config.get('pythonocc-core', 'generated_swig_files')
# cmake output path, i.e. the location where the __init__.py file is created
CMAKE_PATH = config.get('pythonocc-core', 'init_path')

# check if SWIG_OUTPUT_PATH exists, otherwise create it
if not os.path.isdir(SWIG_OUTPUT_PATH):
    os.mkdir(SWIG_OUTPUT_PATH)

# the following var is set when the module
# is created
CURRENT_MODULE = None
CURRENT_HEADER_CONTENT = None
PYTHON_MODULE_DEPENDENCY = []
HEADER_DEPENDENCY = []


def reset_header_depency():
    global HEADER_DEPENDENCY
    HEADER_DEPENDENCY = ['TColgp', 'TColStd', 'TCollection', 'Storage']

# remove headers that can't be parse by CppHeaderParser
HXX_TO_EXCLUDE = ['TCollection_AVLNode.hxx',
                  'AdvApp2Var_Data_f2c.hxx',
                  'NCollection_DataMap.hxx',
                  'NCollection_DoubleMap.hxx',
                  'NCollection_IndexedDataMap.hxx',
                  'NCollection_IndexedMap.hxx', 'NCollection_Map.hxx',
                  'NCollection_CellFilter.hxx',
                  'NCollection_EBTree.hxx',
                  'NCollection_BaseSequence.hxx',
                  'NCollection_Haft.h',
                  'NCollection_StlIterator.hxx',
                  'Standard_StdAllocator.hxx',
                  'Standard_CLocaleSentry.hxx',
                  'BOPTools_DataMapOfShapeSet.hxx',
                  'Resource_gb2312.h', 'Resource_Shiftjis.h',
                  'TopOpeBRepBuild_SplitShapes.hxx',
                  'TopOpeBRepBuild_SplitSolid.hxx',
                  'TopOpeBRepBuild_Builder.hxx',
                  'TopOpeBRepBuild_SplitEdge.hxx',
                  'TopOpeBRepBuild_Fill.hxx',
                  'TopOpeBRepBuild_SplitFace.hxx',
                  'TopOpeBRepDS_traceDSX.hxx',
                  'ChFiKPart_ComputeData_ChAsymPlnCon.hxx',
                  'ChFiKPart_ComputeData_ChAsymPlnCyl.hxx',
                  'ChFiKPart_ComputeData_ChAsymPlnPln.hxx',
                  'ChFiKPart_ComputeData_ChPlnCon.hxx',
                  'ChFiKPart_ComputeData_ChPlnCyl.hxx',
                  'ChFiKPart_ComputeData_ChPlnPln.hxx',
                  'ChFiKPart_ComputeData_Sphere.hxx',
                  'Font_FTFont.hxx', 'Font_FTLibrary.hxx',
                  'IntTools_LineConstructor.hxx',
                  'IntTools_PolyhedronTool.hxx',
                  'IntPatch_PolyhedronTool.hxx',
                  'IntPatch_TheInterfPolyhedron.hxx',
                  'SelectMgr_CompareResults.hxx',
                  'InterfaceGraphic_wntio.hxx',
                  'Interface_STAT.hxx',
                  'Aspect_DisplayConnection.hxx',
                  'XSControl_Vars.hxx',
                  'MeshVS_Buffer.hxx',
                  'SMDS_SetIterator.hxx',
                  'SMESH_Block.hxx',
                  'SMESH_ExceptHandlers.hxx', 'StdMeshers_Penta_3D.hxx',
                  'SMESH_ControlsDef.hxx',
                  'SMESH_Algo.hxx',
                  'SMESH_0D_Algo.hxx', 'SMESH_1D_Algo.hxx',
                  'SMESH_2D_Algo.hxx',
                  'SMESH_3D_Algo.hxx',
                  'IntTools_CurveRangeSampleMapHasher.hxx',
                  'Interface_ValueInterpret.hxx',
                  'StepToTopoDS_DataMapOfRI.hxx',
                  'StepToTopoDS_DataMapOfTRI.hxx',
                  'StepToTopoDS_DataMapOfRINames.hxx',
                  'StepToTopoDS_PointEdgeMap.hxx',
                  'StepToTopoDS_PointVertexMap.hxx'
                  # New excludes for 0.17
                  #'BOPAlgo_MakerVolume.hxx',
                  'BOPTools_CoupleOfShape.hxx',
                  'BRepApprox_SurfaceTool.hxx',
                  'BRepBlend_HCurveTool.hxx',
                  'BRepBlend_HCurve2dTool.hxx',
                  'BRepMesh_FaceAttribute.hxx',
                  'ChFiKPart_ComputeData_FilPlnCon.hxx',
                  'ChFiKPart_ComputeData_FilPlnPln.hxx',
                  'ChFiKPart_ComputeData_FilPlnCyl.hxx',
                  'ChFiKPart_ComputeData_Rotule.hxx',
                  'PrsMgr_ListOfPresentableObjects.hxx',
                  'PrsMgr_PresentableObject.hxx',
                  'TDF_LabelMapHasher.hxx'
                  ]


# some typedefs parsed by CppHeader can't be wrapped
# and generate SWIG syntax errors. We just forget
# about wrapping those typedefs
TYPEDEF_TO_EXCLUDE = ['NCollection_DelMapNode',
                      'BOPDS_DataMapOfPaveBlockCommonBlock',
                      'IntWalk_VectorOfWalkingData',
                      'IntWalk_VectorOfInteger'
                      ]


def process_handle(class_name, inherits_from_class_name):
    """ Given a class name that inherits from Standard_Transient,
    generate the wrapper for the related Handle
    """

    handle_constructor_append = """
%%pythonappend Handle_%s::Handle_%s %%{
    # register the handle in the base object
    if len(args) > 0:
        register_handle(self, args[0])
%%}
""" % (class_name, class_name)

    if class_name == "Standard_Transient":
        handle_inheritance_declaration = """
%nodefaultctor Handle_Standard_Transient;
class Handle_Standard_Transient {
"""
    else:
        handle_inheritance_declaration = """
%%nodefaultctor Handle_%s;
class Handle_%s : public Handle_%s {
""" % (class_name, class_name, inherits_from_class_name)

    handle_body_template = """
    public:
        // constructors
        Handle_%s();
        Handle_%s(const Handle_%s &aHandle);
        Handle_%s(const %s *anItem);
        void Nullify();
        Standard_Boolean IsNull() const;
        static const Handle_%s DownCast(const Handle_Standard_Transient &AnObject);
"""
    if class_name == "Standard_Transient":
        handle_body_template += """
        %%extend{
            bool __eq_wrapper__(const Handle_Standard_Transient &right) {
                if (*self==right) return true;
                else return false;
            }
        }
        %%extend{
            bool __eq_wrapper__(const Standard_Transient *right) {
                if (*self==right) return true;
                else return false;
            }
        }
        %%extend{
            bool __ne_wrapper__(const Handle_Standard_Transient &right) {
                if (*self!=right) return true;
                else return false;
            }
        }
        %%extend{
            bool __ne_wrapper__(const Standard_Transient *right) {
                if (*self!=right) return true;
                else return false;
            }
        }
        %%extend{
            std::string DumpToString() {
            std::stringstream s;
            self->Dump(s);
            return s.str();
            }
        }
        %%pythoncode {
        def __eq__(self,right):
            try:
                return self.__eq_wrapper__(right)
            except:
                return False
        }
        %%pythoncode {
        def __ne__(self,right):
            try:
                return self.__ne_wrapper__(right)
            except:
                return True
        }
"""
    handle_body_template += """
};
%%extend Handle_%s {
    %s* _get_reference() {
    return (%s*)$self->Access();
    }
};

%%extend Handle_%s {
    %%pythoncode {
        def GetObject(self):
            obj = self._get_reference()
            register_handle(self, obj)
            return obj
    }
};

"""
    c = tuple([class_name for i in range(handle_body_template.count('%s'))])
    return handle_constructor_append + handle_inheritance_declaration + handle_body_template % c


def filter_header_list(header_list):
    """ From a header list, remove hxx to HXX_TO_EXCLUDE
    """
    for header_to_remove in HXX_TO_EXCLUDE:
        if os.path.join(OCE_INCLUDE_DIR, header_to_remove) in header_list:
            header_list.remove(os.path.join(OCE_INCLUDE_DIR, header_to_remove))
        elif os.path.join(SMESH_INCLUDE_DIR, header_to_remove) in header_list:
            header_list.remove(os.path.join(SMESH_INCLUDE_DIR, header_to_remove))
    # remove platform dependent files
    # this is done to have the same SWIG files on every platform
    # wnt specific
    header_list = [x for x in header_list if not ('WNT' in x.lower())]
    header_list = [x for x in header_list if not ('wnt' in x.lower())]
    # linux
    header_list = [x for x in header_list if not ('X11' in x)]
    header_list = [x for x in header_list if not ('XWD' in x)]
    # and osx
    header_list = [x for x in header_list if not ('Cocoa' in x)]
    return header_list


def test_filter_header_list():
    if sys.platform != 'win32':
        assert(filter_header_list(['something', 'somethingWNT']) == ['something'])


def case_sensitive_glob(wildcard):
    """
    Case sensitive glob for Windows.
    Designed for handling of GEOM and Geom modules
    This function makes the difference between GEOM_* and Geom_* under Windows
    """
    flist = glob.glob(wildcard)
    pattern = wildcard.split('*')[0]
    f = []
    for file in flist:
        if pattern in file:
            f.append(file)
    return f


def get_all_module_headers(module_name):
    """ Returns a list with all header names
    """
    mh = case_sensitive_glob(os.path.join(OCE_INCLUDE_DIR, '%s.hxx' % module_name))
    mh += case_sensitive_glob(os.path.join(OCE_INCLUDE_DIR, '%s_*.hxx' % module_name))
    mh += case_sensitive_glob(os.path.join(OCE_INCLUDE_DIR, '%s*.h' % module_name))
    mh += case_sensitive_glob(os.path.join(OCE_INCLUDE_DIR, 'Handle_%s.hxx*' % module_name))
    mh += case_sensitive_glob(os.path.join(SMESH_INCLUDE_DIR, '%s.hxx' % module_name))
    mh += case_sensitive_glob(os.path.join(SMESH_INCLUDE_DIR, '%s_*.hxx' % module_name))
    mh += case_sensitive_glob(os.path.join(SMESH_INCLUDE_DIR, '%s*.h' % module_name))
    mh += case_sensitive_glob(os.path.join(SMESH_INCLUDE_DIR, 'Handle_%s.hxx*' % module_name))
    mh = filter_header_list(mh)
    return map(os.path.basename, mh)


def test_get_all_module_headers():
    # 'Standard' should return some files (at lease 10)
    # this number depends on the OCE version
    headers_list_1 = get_all_module_headers("Standard")
    assert(len(headers_list_1) > 10)
    # an empty list
    headers_list_2 = get_all_module_headers("something_else")
    assert(not headers_list_2)


def check_has_related_handle(class_name):
    """ For a given class :
    Check if a header exists.
    """
    filename = os.path.join(OCE_INCLUDE_DIR, "Handle_%s.hxx" % class_name)
    other_possible_filename = filename
    if class_name.startswith("Graphic3d"):
        other_possible_filename = os.path.join(OCE_INCLUDE_DIR, "%s_Handle.hxx" % class_name)
    return (os.path.exists(filename) or os.path.exists(other_possible_filename) or need_handle())


def get_license_header():
    """ Write the header to the different SWIG files
    """
    header = "/*\nCopyright %s %s (%s)\n\n" % (header_year, author, author_email)
    header += license_header
    header += "\n*/\n"
    return header


def write__init__():
    """ creates the OCC/__init__.py file.
    In this file, the Version is created.
    The OCE version is checked into the oce-version.h file
    """
    fp__init__ = open(os.path.join(CMAKE_PATH, '__init__.py'), 'w')
    fp__init__.write('VERSION = "%s"\n' % PYTHONOCC_VERSION)
    # @TODO : then check OCE version


def need_handle():
    """ Returns True if the current parsed class needs an
    Handle to be defined. This is useful when headers define
    handles but no header """
    # @TODO what about DEFINE_RTTI ?
    if 'DEFINE_STANDARD_HANDLE' in CURRENT_HEADER_CONTENT:
        return True
    else:
        return False


def adapt_header_file(header_content):
    """ take an header filename as input.
    Returns the output of a tempfile with :
    * all occurrences of Handle(something) moved to Handle_Something
    otherwise CppHeaderParser is confused ;
    * all define RTTI moved
    """
    global CURRENT_HEADER_CONTENT
    outer = re.compile("DEFINE_STANDARD_HANDLE[\s]*\([\w\s]+\,+[\w\s]+\)")
    matches = outer.findall(header_content)
    if matches:
        for match in matches:
            # @TODO find inheritance name
            header_content = header_content.replace('DEFINE_STANDARD_HANDLE',
                                                    '//DEFINE_STANDARD_HANDLE')
    # then we look for Handle(Something) use
    # and replace with Handle_Something
    outer = re.compile("Handle[\s]*\([\w\s]*\)")
    matches = outer.findall(header_content)
    if matches:
        for match in matches:
            orig_match = match
            # matches are of the form :
            #['Handle(Graphic3d_Structure)',
            # 'Handle(Graphic3d_DataStructureManager)']
            match = match.replace(" ", "")
            match = (match.split('Handle(')[1]).split(')')[0]
            header_content = header_content.replace(orig_match,
                                                    'Handle_%s' % match)
    # for smesh, remove EXPORTS that cause parser errors
    header_content = header_content.replace("SMESH_EXPORT", "")
    header_content = header_content.replace("SMESHCONTROLS_EXPORT", "")
    header_content = header_content.replace("SMESHDS_EXPORT", "")
    header_content = header_content.replace("STDMESHERS_EXPORT", "")
    CURRENT_HEADER_CONTENT = header_content
    return header_content


def parse_header(header_filename):
    """ Use CppHeaderParser module to parse header_filename
    """
    header_content = open(header_filename, 'r').read()
    adapted_header_content = adapt_header_file(header_content)
    try:
        cpp_header = CppHeaderParser.CppHeader(adapted_header_content, "string")
    except CppHeaderParser.CppParseError, e:
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
    for key in typedef_dict.keys():
        if key in TYPEDEF_TO_EXCLUDE:
            del typedef_dict[key]
    return typedef_dict


def test_filter_typedefs():
    a_dict = {'1': 'one', '{': 'two', '3': 'aNCollection_DelMapNodeb'}
    #assert(filter_typedefs(a_dict) == {'1': 'one'})


def process_typedefs(typedefs_dict):
    """ Take a typedef dictionary and returns a SWIG definition string
    """
    typedef_str = "/* typedefs */\n"
    # careful, there might be some strange things returned by CppHeaderParser
    # they should not be taken into account
    filtered_typedef_dict = filter_typedefs(typedefs_dict)
    for typedef_value in filtered_typedef_dict.keys():
        typedef_str += "typedef %s %s;\n" % (filtered_typedef_dict[typedef_value], typedef_value)
    typedef_str += "/* end typedefs declaration */\n\n"
    return typedef_str


def process_enums(enums_list):
    """ Take an enum list and generate a compliant SWIG string
    """
    enum_str = "/* public enums */\n"
    for enum in enums_list:
        if "name" not in enum:
            enum_name = ""
        else:
            enum_name = enum["name"]
        enum_str += "enum %s {\n" % enum_name
        for enum_value in enum["values"]:
            enum_str += "\t%s = %s,\n" % (enum_value["name"], enum_value["value"])
        enum_str += "};\n\n"
    enum_str += "/* end public enums declaration */\n\n"
    return enum_str


def adapt_param_type(param_type):
    param_type = param_type.replace("Standard_CString", "const char *")
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
        (param_type_and_name.startswith('double &'))) and not ('const' in param_type_and_name):
        adapted_param_type_and_name = "Standard_Real &OutValue"
    elif (('Standard_Integer &' in param_type_and_name) or
          (param_type_and_name.startswith('int &'))) and not ('const' in param_type_and_name):
        adapted_param_type_and_name = "Standard_Integer &OutValue"
    elif (('Standard_Boolean &' in param_type_and_name) or
         (param_type_and_name.startswith('bool &'))) and not ('const' in param_type_and_name):
        adapted_param_type_and_name = "Standard_Boolean &OutValue"
    elif ('FairCurve_AnalysisCode &' in param_type_and_name):
        adapted_param_type_and_name = 'FairCurve_AnalysisCode &OutValue'
    else:
        adapted_param_type_and_name = param_type_and_name
    return adapted_param_type_and_name


def test_adapt_param_type_and_name():
    p1 = "Standard_Real & Xp"
    ad_p1 = adapt_param_type_and_name(p1)
    assert (ad_p1 == "Standard_Real &OutValue")
    p2 = "Standard_Integer & I"
    ad_p2 = adapt_param_type_and_name(p2)
    assert (ad_p2 == "Standard_Integer &OutValue")
    p3 = "int & j"
    ad_p3 = adapt_param_type_and_name(p3)
    assert (ad_p3 == "Standard_Integer &OutValue")
    p4 = "double & x"
    ad_p4 = adapt_param_type_and_name(p4)
    assert (ad_p4 == "Standard_Real &OutValue")


def check_dependency(item):
    """ Given a typedef, classname, parameter etc.
    if not the module prefix then add dependency
    """
    if not item:
        return False
    filt = ["const ", "static ", "virtual ", "clocale_t", "pointer",
            "size_type", "void", "reference", "const_", "inline "]
    for f in filt:
        item = item.replace(f, '')
    if len(item) == 0:
        return False
    tmp = item.split('_')
    if tmp[0] == 'Handle':
        module = tmp[1]
    else:
        module = tmp[0]
    if module == 'Font':  # forget about Font dependencies, issues with FreeType
        return True
    if module != CURRENT_MODULE:
        # need to be added to the list of dependend object
        if (not module in PYTHON_MODULE_DEPENDENCY) and (is_module(module)):
            PYTHON_MODULE_DEPENDENCY.append(module)


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
    # replace Standard_CString with char *
    return_type = return_type.replace("Standard_CString", "const char *")
    # remove const if const virtual double *  # SMESH only
    return_type = return_type.replace("const virtual double *", "virtual double *")
    return_type = return_type.replace("DistrType", "StdMeshers_NumberOfSegments::DistrType")
    return_type = return_type.replace("TWireVector", "StdMeshers_MEFISTO_2D::TWireVector")
    return_type = return_type.replace("PGroupIDs", "SMESH_MeshEditor::PGroupIDs")
    return_type = return_type.replace("TAncestorMap", "TopTools_IndexedDataMapOfShapeListOfShape")
    return_type = return_type.replace("ErrorCode", "SMESH_Pattern::ErrorCode")
    return_type = return_type.replace("Fineness", "NETGENPlugin_Hypothesis::Fineness")
    #ex: Handle_WNT_GraphicDevice const &
    # for instance "const TopoDS_Shape & -> ["const", "TopoDS_Shape", "&"]
    if (('gp' in return_type) and not ('TColgp' in return_type))or ('TopoDS' in return_type):
        return_type = return_type.replace('&', '')
    check_dependency(return_type)
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


def process_docstring(f):
    """ Create the docstring, for the function f,
    that will be used by the wrapper.
    For that, first check the function parameters and type
    then add the doxygen value
    """
    function_name = f["name"]
    string_to_return = '\t\t%feature("autodoc", "'
    # first process parameters
    parameters_string = ''
    if len(f["parameters"]) > 0:
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
        doxygen_string = "\t* " + doxygen_string + "\n\n"
    # concatenate everything
    final_string = doxygen_string + parameters_string + returns_string
    string_to_return += '%s") %s;\n' % (final_string, function_name)
    return string_to_return


def adapt_default_value(def_value):
    """ adapt default value """
    def_value = def_value.replace(": : ", "")
    def_value = def_value.replace(' ', '')
    def_value = def_value.replace('"', "'")
    def_value = def_value.replace("''", '""')
    return def_value


def adapt_default_value_parmlist(parm):
    """ adapts default value to be used in swig parameter list """
    def_value = parm["defaultValue"]
    def_value = def_value.replace(": : ", "")
    def_value = def_value.replace(' ', '')
    return def_value


def test_adapt_default_value():
    assert adapt_default_value(": : MeshDim_3D") == "MeshDim_3D"


def filter_member_functions(class_public_methods, member_functions_to_exclude, class_is_abstract):
    """ This functions removes member function to exclude from
    the class methods list. Some of the members functions have to be removed
    because they can't be wrapped (usually, this results in a linkage error)
    """
    member_functions_to_process = []
    for public_method in class_public_methods:
        #print(public_method)
        method_name = public_method["name"]
        if method_name in member_functions_to_exclude:
            continue
        elif class_is_abstract and public_method["constructor"]:
            print("Constructor skipped for abstract class")
            continue
        elif method_name == "ShallowCopy":  # specific to 0.17.1 and Mingw
            continue
        else:  # finally, we add this method to process
            member_functions_to_process.append(public_method)
    return member_functions_to_process


def test_filter_member_functions():
    class_public_methods = [{"name": "method_1"},
                            {"name": "method_2"},
                            {"name": "method_3"},
                            ]
    member_functions_to_exclude = ["method_2"]
    result = filter_member_functions(class_public_methods,
                                     member_functions_to_exclude,
                                     False)
    assert result == [{"name": "method_1"}, {"name": "method_3"}]


def handle_by_value(return_str):
    """
    If function returns reference to Handle, the name of the
    handle will be returned. None otherwise
    """
    handlePattern = re.compile(r'(virtual )?(const )?(?P<name>(Handle_)+([A-Za-z_0-9])*)(\s)*(&)')
    match = re.search(handlePattern, return_str)

    if match:
        handle_name = match.group('name')
        return handle_name
    else:
        return return_str


def process_function(f):
    """ Process function f and returns a SWIG compliant string.
    If process_docstrings is set to True, the documentation string
    from the C++ header will be used as is for the python wrapper
    """
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
        def __eq__(self,right):
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
        def __ne__(self,right):
            try:
                return self.__ne_wrapper__(right)
            except:
                return True
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
    if "TYPENAME" in f["rtnType"]:
        return ""  # something in NCollection
    if function_name == "Handle":  # TODO: make it possible!
    # this is because Handle (something) some function can not be
    # handled by swig
        return ""
    # enable autocompactargs feature to enable compilation with swig>3.0.3
    str_function = '\t\t%%feature("compactdefaultargs") %s;\n' % function_name
    str_function += process_docstring(f)
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
    # First case we handle : byref Standard_Integer and Standard_Real
    # this is wrapped the followind way:
    # one function Get* that returns the object
    # one function Set* that sets the object
    if (return_type in ['Standard_Integer &', 'Standard_Real &', 'Standard_Boolean &']):
        # we only wrap this way methods that does not have any parameter
        if len(f["parameters"]) == 0:
            modified_return_type = return_type.split(" ")[0]
            str_function = """
            %%feature("autodoc","1");
            %%extend {
                %s Get%s() {
                return (%s) $self->%s();
                }
            };
            %%feature("autodoc","1");
            %%extend {
                void Set%s(%s value ) {
                $self->%s()=value;
                }
            };
            """ % (modified_return_type, function_name, modified_return_type,
                   function_name, function_name, modified_return_type, function_name)
            return str_function
    str_function += "%s " % handle_by_value(return_type)
    # function name
    str_function += "%s " % function_name
    # process parameters
    str_function += "("
    for param in f["parameters"]:
        param_type = adapt_param_type(param["type"])
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
    str_function = str_function.replace('const const', 'const')
    return str_function


def process_free_functions(free_functions_list):
    """ process a string for free functions
    """
    str_free_functions = ""
    for free_function in free_functions_list:
        str_free_functions += process_function(free_function)
    return str_free_functions


def process_methods(methods_list):
    """ process a list of public process_methods
    """
    str_functions = ""
    for function in methods_list:
        # don't process frind methods
        if not function["friend"]:
            str_functions += process_function(function)
    return str_functions


def must_ignore_default_destructor(klass):
    """ Some classes, like for instance BRepFeat_MakeCylindricalHole
    has a protected destructor that must explicitely be ignored
    This is done by the directive
    %ignore Class::~Class() just before the wrapper definition
    """
    class_protected_methods = klass['methods']['protected']
    for protected_method in class_protected_methods:
        #print(public_method)
        #if klass["name"]=="BOPAlgo_BuilderShape":
        #  print(protected_method)
        if protected_method["destructor"]:
            return True
    class_private_methods = klass['methods']['private']
    # finally, return True, the default constructor can be safely defined
    for private_method in class_private_methods:
        #print(public_method)
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
        #print(public_method)
        if protected_method["constructor"]:
            return False
    class_private_methods = klass['methods']['private']
    # finally, return True, the default constructor can be safely defined
    for private_method in class_private_methods:
        #print(public_method)
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
    # first, we build two dictionaries
    # the first one, level_0_classes
    # contain class names that does not inherit from
    # any other class
    # they will be processed first
    level_0_classes = []
    # containes
    level_n_classes = []
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
        elif nbr_upper_classes == 1:
            upper_class_name = upper_classes[0]["class"]
            # if the upper class depends on another module
            # add it to the level 0 list.
            if upper_class_name.split("_")[0] != CURRENT_MODULE:
                level_0_classes.append(class_name)
            # else build the inheritance tree
            else:
                inheritance_dict[class_name] = upper_class_name
        else:
            # prevent multiple inheritance: OCE only has single
            # inheritance
            print("\nWARNING : NOT SINGLE INHERITANCE")
            print("CLASS %s has %i ancestors" % (class_name, nbr_upper_classes))
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
    for class_name, depth_value in sorted(inheritance_depth.iteritems(),
                                          key=lambda (k, v): (v, k)):
        if class_name in classes_dict:  # TODO: should always be the case!
            class_list.append(classes_dict[class_name])
    return class_list


def fix_type(type_str):
    type_str = type_str.replace("Standard_Boolean &", "bool")
    type_str = type_str.replace("Standard_Boolean", "bool")
    type_str = type_str.replace("Standard_Real", "float")
    type_str = type_str.replace("Standard_Integer", "int")
    type_str = type_str.replace("const", "")
    return type_str


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
    for klass in inheritance_tree_list:
        # class name
        class_name = klass["name"]
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
        if class_name == CURRENT_MODULE:
            class_def_str += "%%rename(%s) %s;\n" % (class_name.lower(), class_name)
        # then process the class itself
        if not class_can_have_default_constructor(klass):
            class_def_str += "%%nodefaultctor %s;\n" % class_name
        if must_ignore_default_destructor(klass):
        # check if the destructor is protected or private
            class_def_str += "%%ignore %s::~%s();\n" % (class_name, class_name)
        # then defines the wrapper
        class_def_str += "class %s" % class_name
        # inheritance process
        # in OCE, only single inheritance
        inherits_from = klass["inherits"]
        if inherits_from:
            inheritance_name = inherits_from[0]["class"]
            check_dependency(inheritance_name)
            inheritance_access = inherits_from[0]["access"]
            class_def_str += " : %s %s" % (inheritance_access, inheritance_name)
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
        if class_enums_list:
            class_def_str += process_enums(class_enums_list)
        # process class properties here
        properties_str = ''
        for property_value in list(klass["properties"]['public']):
            if property_value['constant'] or 'virtual' in property_value['raw_type'] or 'Standard_EXPORT' in property_value['raw_type'] or 'allback' in property_value['raw_type']:
                continue
            if 'array_size' in property_value:
                temp = "\t\t%s %s[%s];\n" % (fix_type(property_value['type']), property_value['name'], property_value['array_size'])
            else:
                temp = "\t\t%s %s;\n" % (fix_type(property_value['type']), property_value['name'])
            properties_str += temp
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
        methods_to_process = filter_member_functions(class_public_methods, members_functions_to_exclude, klass["abstract"])
        class_def_str += process_methods(methods_to_process)
        # then terminate the class definition
        class_def_str += "};\n\n"
        #
        # at last, check if there is a related handle
        # if yes, we integrate it into it's shadow class
        # TODO: check that the following is not restricted
        # to protected destructors !
        class_def_str += '\n'
        if check_has_related_handle(class_name) or need_handle():
            # Extend class by GetHandle method
            class_def_str += '%%extend %s {\n' % class_name
            class_def_str += '\t%' + 'pythoncode {\n'
            class_def_str += '\t\tdef GetHandle(self):\n'
            class_def_str += '\t\t    try:\n'
            class_def_str += '\t\t        return self.thisHandle\n'
            class_def_str += '\t\t    except:\n'
            class_def_str += '\t\t        self.thisHandle = Handle_%s(self)\n' % class_name
            class_def_str += '\t\t        self.thisown = False\n'
            class_def_str += '\t\t        return self.thisHandle\n'
            class_def_str += '\t}\n};\n'
            if class_name == "Standard_Transient":
                class_def_str += process_handle(class_name, None)
            else:
                class_def_str += process_handle(class_name, inheritance_name)
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
    """ A modume is defined by a set of headers. For instance AIS,
    gp, BRepAlgoAPI etc. For each module, generate three or more
    SWIG files. This parser returns :
    module_enums, module_typedefs, module_classes
    """
    module_headers = glob.glob('%s/%s_*.hxx' % (OCE_INCLUDE_DIR, module_name))
    module_headers += glob.glob('%s/%s.hxx' % (OCE_INCLUDE_DIR, module_name))
    if not module_headers:  # this can be smesh modules
        module_headers = glob.glob('%s/%s_*.hxx' % (SMESH_INCLUDE_DIR, module_name))
        module_headers += glob.glob('%s/%s.hxx' % (SMESH_INCLUDE_DIR, module_name))
    # filter those headers
    module_headers = filter_header_list(module_headers)
    cpp_headers = map(parse_header, module_headers)
    module_typedefs = {}
    module_enums = []
    module_classes = {}
    module_free_functions = []
    for header in cpp_headers:
        # build the typedef dictionary
        module_typedefs = dict(module_typedefs.items() + header.typedefs.items())
        # build the enum list
        module_enums += header.enums
        # build the class dictionary
        module_classes = dict(module_classes.items() + header.classes.items())
        # build the free functions list
        module_free_functions += header.functions
    return module_typedefs, module_enums, module_classes, module_free_functions


class ModuleWrapper(object):
    def __init__(self, module_name, additional_dependencies=[],
                 exclude_classes=[], exclude_member_functions={}):
        # Reinit global variables
        global CURRENT_MODULE, PYTHON_MODULE_DEPENDENCY
        CURRENT_MODULE = module_name
        PYTHON_MODULE_DEPENDENCY = []
        reset_header_depency()
        print("=== generating SWIG files for module %s ===" % module_name)
        self._module_name = module_name
        print("\t parsing %s related headers ..." % module_name, end="")
        typedefs, enums, classes, free_functions = parse_module(module_name)
        print("done.")
        print("\t processing typedefs ...", end="")
        self._typedefs_str = process_typedefs(typedefs)
        print("done.")
        print("\t processing enums ...", end="")
        self._enums_str = process_enums(enums)
        print("done")
        print("\t processing classes ...", end="")
        self._classes_str = process_classes(classes, exclude_classes,
                                            exclude_member_functions)
        print("done")
        print("\t processing free functions ...", end="")
        self._free_functions_str = process_free_functions(free_functions)
        print("done")
        self._additional_dependencies = additional_dependencies + HEADER_DEPENDENCY
        print("generating SWIG file")
        self.generate_SWIG_files()
        print("SWIG file generated")

    def generate_SWIG_files(self):
        #
        # Main file
        #
        f = open(os.path.join(SWIG_OUTPUT_PATH, "%s.i" % self._module_name), "w")
        # write header
        f.write(get_license_header())
        # module name
        f.write('%%module (package="OCC") %s\n\n' % self._module_name)
        # remove warnings
        # warning 504 because void suppression
        # 325 : nested class unsupported
        # 503 : Can't wrap class unless renamed to a valid identifier
        f.write("#pragma SWIG nowarn=504,325,503\n")
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
                    "FunctionTransformers", "Operators"]
        for include in includes:
            f.write("%%include ../common/%s.i\n" % include)
        f.write("\n\n")
        # specific includes
        f.write("%%include %s_headers.i\n\n" % self._module_name)
        # write helper functions
        helper_functions = """
%pythoncode {
def register_handle(handle, base_object):
    \"\"\"
    Inserts the handle into the base object to
    prevent memory corruption in certain cases
    \"\"\"
    try:
        if base_object.IsKind("Standard_Transient"):
            base_object.thisHandle = handle
            base_object.thisown = False
    except:
        pass
};

"""
        f.write(helper_functions)
        # write type_defs
        f.write(self._typedefs_str)
        # write public enums
        f.write(self._enums_str)
        # write classes_definition
        f.write(self._classes_str)
        # write free_functions definition
        #TODO: we should write free functions here,
        # but it sometimes fail to compile
        #f.write(self._free_functions_str)
        f.close()
        #
        # Headers
        #
        h = open(os.path.join(SWIG_OUTPUT_PATH, "%s_headers.i" % self._module_name), "w")
        h.write(get_license_header())
        h.write("%{\n")
        module_headers = glob.glob('%s/%s_*.hxx' % (OCE_INCLUDE_DIR, self._module_name))
        module_headers += glob.glob('%s/%s.hxx' % (OCE_INCLUDE_DIR, self._module_name))
        module_headers += glob.glob('%s/%s_*.hxx' % (SMESH_INCLUDE_DIR, self._module_name))
        module_headers += glob.glob('%s/%s.hxx' % (SMESH_INCLUDE_DIR, self._module_name))
        for module_header in filter_header_list(module_headers):
            if not os.path.basename(module_header) in HXX_TO_EXCLUDE:
                h.write("#include<%s>\n" % os.path.basename(module_header))
        # then we add *all* the headers
        # that come with a dependency.
        # All those headers may not be necessary
        # but it's the only way to be sure we don't miss any
        for dep in PYTHON_MODULE_DEPENDENCY:
            for header_basename in get_all_module_headers(dep):
                h.write("#include<%s>\n" % header_basename)
        for add_dep in self._additional_dependencies:
            for header_basename in get_all_module_headers(add_dep):
                h.write("#include<%s>\n" % header_basename)
        h.write("%};\n")
        for dep in PYTHON_MODULE_DEPENDENCY:
            if is_module(dep):
                h.write("%%import %s.i\n" % dep)


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
            print("Next to be processed : %s " % module_name)
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
    for module in modules_list:
        process_module(module)


def process_all_toolkits():
    parallel_build = config.get('build', 'parallel_build')
    if parallel_build == "True":  # multitask
    	print("parallel")
        from multiprocessing import Pool
        pool = Pool()
        try:
            # the timeout is required for proper handling when exciting the parallel build
            pool.map_async(process_toolkit, TOOLKITS).get(9999999999)
        except KeyboardInterrupt:
            pool.terminate()
            pool.join()
        else:
            pool.close()
            pool.join()
    else:  # single task
        for toolkit in TOOLKITS:
            process_toolkit(toolkit)


def run_unit_tests():
    print("running unittests ...", end="")
    test_is_module()
    test_filter_header_list()
    test_get_all_module_headers()
    test_adapt_return_type()
    test_filter_typedefs()
    test_adapt_function_name()
    test_filter_member_functions()
    test_adapt_param_type_and_name()
    test_adapt_default_value()
    print("done.")

if __name__ == '__main__':
    run_unit_tests()
    if len(sys.argv) > 1:
        for module_to_process in sys.argv[1:]:
            process_module(module_to_process)
    else:
        write__init__()
        process_all_toolkits()
    # to process only one toolkit, uncomment the following line and change the toolkit name
    #process_toolkit("TKernel")
