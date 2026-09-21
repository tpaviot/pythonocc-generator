#!/usr/bin/env python
##Copyright 2008-2026 Thomas Paviot (tpaviot@gmail.com)

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
import argparse
import configparser
import datetime
import glob
import hashlib  # to compute md5 function signatures
import keyword  # to prevent using python language keywords
import logging
from operator import itemgetter
import os
import platform
import re
import subprocess
import sys
import time

import CppHeaderParser

from _modules import OCCT_MODULES, TOOLKITS
from _exclusions import (
    ENUMS_TO_EXLUDE,
    HXX_TO_EXCLUDE_FROM_BEING_INCLUDED,
    HXX_TO_EXCLUDE_FROM_CPPPARSER,
    NCOLLECTION_WRAPPED_CLASSES,
    NODEFAULTCTOR,
    STANDARD_INTEGER_TYPEDEF,
    TEMPLATES_TO_EXCLUDE,
    TYPEDEF_TO_EXCLUDE,
)
from _swig_templates import (
    BREPALGOAPI_HEADER,
    BREPTOOLS_WRITE_READ_FROM_STRING,
    BREPTOOLS_WRITE_READ_FROM_STRING_PYI,
    BVH_HEADER_TEMPLATE,
    BYREF_ENUM_TEMPLATE,
    GETSTATE_TEMPLATE,
    GRAPHIC3D_DEFINE_HEADER,
    HARRAY1_TEMPLATE,
    HARRAY1_TEMPLATE_PYI,
    HARRAY2_TEMPLATE,
    HARRAY2_TEMPLATE_PYI,
    HASH_TOPODS_SHAPE_TEMPLATE,
    HSEQUENCE_TEMPLATE,
    HSEQUENCE_TEMPLATE_PYI,
    LICENSE_HEADER,
    MATH_HEADER_TEMPLATE,
    NCOLLECTION_ARRAY1_EXTEND_TEMPLATE_PYI,
    NCOLLECTION_DATAMAP_EXTEND_TEMPLATE,
    NCOLLECTION_HEADER_TEMPLATE,
    NCOLLECTION_LIST_EXTEND_TEMPLATE,
    NCOLLECTION_LIST_EXTEND_TEMPLATE_PYI,
    NCOLLECTION_SEQUENCE_EXTEND_TEMPLATE,
    NCOLLECTION_SEQUENCE_EXTEND_TEMPLATE_PYI,
    NUMPY_INIT_TEMPLATE,
    PRS3D_HEADER_TEMPLATE,
    SETSTATE_TEMPLATE,
    SHAPE_ANALYSIS_FREE_BOUNDS_TEMPLATE,
    SHAPE_ANALYSIS_FREE_BOUNDS_TEMPLATE_PYI,
    STANDARD_TRANSIENT_OPERATORS_TEMPLATE,
    TEMPLATE_DUMPJSON,
    TEMPLATE_DUMPJSON_PYI,
    TEMPLATE_GETTER_PYI,
    TEMPLATE_GETTER_SETTER,
    TEMPLATE_INITFROMJSON,
    TEMPLATE_INITFROMJSON_PYI,
    TEMPLATE_SETTER_PYI,
    TEMPLATE__EQ__,
    TEMPLATE__IADD__,
    TEMPLATE__IMUL__,
    TEMPLATE__ISUB__,
    TEMPLATE__ITRUEDIV__,
    TEMPLATE__NE__,
    TIMESTAMP_TEMPLATE,
    TOPODS_CLASS,
    TOPODS_CLASS_PYI,
    TOPODS_SHAPE_PICKLE_TEMPLATE,
    WIN_PRAGMAS,
)

##############################################
# Load configuration file and setup settings #
##############################################
# the PYTHONOCC_GENERATOR_CONFIG environment variable, if set, overrides the
# wrapper_generator.conf next to this script (used by the CI)
DEFAULT_CONFIG_PATH = os.environ.get("PYTHONOCC_GENERATOR_CONFIG") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "wrapper_generator.conf"
)


def load_config(config_path):
    """Read wrapper_generator.conf and set the module-level path settings.

    Called once at import time with the default path (so the helper functions
    are usable from the unit tests), then again from main() if --config is
    given. No filesystem check is done here, see check_paths().
    """
    global PYTHONOCC_VERSION, OCCT_INCLUDE_DIR, PYTHONOCC_CORE_PATH
    global COMMON_OUTPUT_PATH, SWIG_OUTPUT_PATH, HEADERS_OUTPUT_PATH
    config = configparser.ConfigParser()
    if not config.read(config_path, encoding="utf8"):
        raise FileNotFoundError(f"Configuration file {config_path} not found.")
    # pythonocc version
    PYTHONOCC_VERSION = config.get("pythonocc-core", "version")
    # oce headers location
    OCCT_INCLUDE_DIR = config.get("OCCT", "include_dir")
    # swig output path
    PYTHONOCC_CORE_PATH = config.get("pythonocc-core", "path")
    swig_files_path = os.path.join(PYTHONOCC_CORE_PATH, "src", "SWIG_files")
    COMMON_OUTPUT_PATH = os.path.join(swig_files_path, "common")
    SWIG_OUTPUT_PATH = os.path.join(swig_files_path, "wrapper")
    HEADERS_OUTPUT_PATH = os.path.join(swig_files_path, "headers")


def check_paths():
    """Fail early if the OCCT headers are missing, and create the output
    directories the generator writes into."""
    if not os.path.isdir(OCCT_INCLUDE_DIR):
        raise FileNotFoundError(f"OCCT include dir {OCCT_INCLUDE_DIR} not found.")
    for output_path in (SWIG_OUTPUT_PATH, HEADERS_OUTPUT_PATH, COMMON_OUTPUT_PATH):
        os.makedirs(output_path, exist_ok=True)


load_config(DEFAULT_CONFIG_PATH)

GENERATE_SWIG_FILES = (
    True  # if set to False, skip .i generator, to avoid recompile everything
)


def setup_logging():
    """Log both to stdout and to ${SWIG_OUTPUT_PATH}/generator.log, which is
    emptied at each run. Must be called after check_paths()."""
    log_formatter = logging.Formatter("[%(levelname)-5.5s]  %(message)s")
    log = logging.getLogger()
    log.setLevel(logging.INFO)
    file_handler = logging.FileHandler(
        os.path.join(SWIG_OUTPUT_PATH, "generator.log"), mode="w", encoding="utf8"
    )
    file_handler.setFormatter(log_formatter)
    log.addHandler(file_handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    log.addHandler(console_handler)


####################
# Global variables #
####################
DOC_URL = "https://dev.opencascade.org/doc/occt-7.9.0/refman/html"


class GeneratorState:
    """Mutable state shared across the generation pipeline.

    Replaces a dozen module-level globals so the dependencies between passes
    are explicit. A single instance, ``state`` below, is the only authority.
    """

    def __init__(self):
        # set by ModuleWrapper.__init__ for the module currently being wrapped
        self.current_module = None
        # python modules the current module imports (transitive deps).
        # Reassigned per module; check_dependency() and process_typedefs()
        # append to it.
        self.python_module_dependency = []
        # Like above but for additional headers; reset at every module via
        # reset_header_depency().
        self.header_dependency = []

        # occt-800: built lazily by scan_typedef_aliases() — a mapping from
        # canonical template form (e.g. "NCollection_HArray1<gp_Pnt2d>") to
        # the typedef alias (e.g. "TColgp_HArray1OfPnt2d") that pythonocc
        # actually wraps. Many OCCT 8.0 headers replaced typedef names with
        # the canonical template form in their function signatures, but the
        # typedef alias is what carries the SWIG type tag, so we have to
        # rewrite back.
        self.harray_typedef_rewrites = []

        # All enums seen so far; populated by process_enums().
        self.all_enums = []
        # Enums passed/returned by reference; need a SWIG-specific template.
        self.all_byref_enums = []

        # HArray1/HArray2/HSequence registries: name -> base type. Populated
        # both from DEFINE_HARRAY{1,2}/DEFINE_HSEQUENCE macros and from
        # `typedef NCollection_HArrayN<X> Y;` aliases scanned upfront.
        self.all_harray1 = {}
        self.all_harray2 = {}
        self.all_hsequence = {}

        # Classes that need %wrap_handle / %make_alias.
        self.all_standard_handles = []
        self.all_standard_transients = ["Standard_Transient"]

        # since SWIG 4.1.1, static functions can no longer be called as free
        # functions; we emit deprecation shims for the old name.
        self.deprecated_static_functions = []

        # statistics
        self.nb_total_classes = 0
        self.nb_total_methods = 0


state = GeneratorState()


def get_log_header():
    """returns a header to be appended to the SWIG file
    Useful for development
    """
    os_name = f"{platform.system()} {platform.architecture()[0]} {platform.release()}"
    # the generator may be run from a tarball, without git available
    try:
        generator_git_revision = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stderr=subprocess.DEVNULL,
            )
            .strip()
            .decode("utf8")
        )
    except (OSError, subprocess.CalledProcessError):
        generator_git_revision = "unknown"
    # find the OCC VERSION targeted by the wrapper
    # the OCCT version is available from the Standard_Version.hxx header
    # e.g. define OCC_VERSION_COMPLETE     "7.4.0"
    standard_version_header = os.path.join(OCCT_INCLUDE_DIR, "Standard_Version.hxx")
    occ_version = "unknown"
    if os.path.isfile(standard_version_header):
        with open(standard_version_header, "r", encoding="utf8") as f:
            file_lines = f.readlines()
        for file_line in file_lines:
            if file_line.startswith("#define OCC_VERSION_COMPLETE"):
                occ_version = file_line.split('"')[1].strip()
    return TIMESTAMP_TEMPLATE.substitute(
        {
            "GITREVISION": generator_git_revision,
            "OS": os_name,
            "OCCTVERSION": occ_version,
            "DATE": f"{datetime.datetime.now()}",
        }
    )


def get_log_footer(elapsed_seconds):
    return """
#################################################
SWIG interface file generation completed in {:.2f}s
#################################################
""".format(
        elapsed_seconds
    )


def reset_header_depency():
    state.header_dependency = ["TColgp", "TColStd", "TCollection", "Storage"]


def check_is_persistent(class_name):
    """
    Checks, whether a class belongs to the persistent classes (and not to the transient ones)
    """
    return any(
        class_name.startswith(occ_module)
        for occ_module in [
            "PFunction",
            "PDataStd",
            "PPrsStd",
            "PDF",
            "PDocStd",
            "PDataXtd",
            "PNaming",
            "PCDM_Document",
        ]
    )


def filter_header_list(header_list, exclusion_list):
    """From a header list, remove hxx to HXX_TO_EXCLUDE
    The files to be excluded are specified in the exclusion list
    """
    for header_to_remove in exclusion_list:
        if os.path.join(OCCT_INCLUDE_DIR, header_to_remove) in header_list:
            header_list.remove(os.path.join(OCCT_INCLUDE_DIR, header_to_remove))
    # remove platform dependent files
    # this is done to have the same SWIG files on every platform:
    # wnt specific (WNT_*, OSD_WNT), linux (X11, XWD) and osx (Cocoa).
    # Match on the basename only, and case-sensitively, so that neither the
    # include dir path nor names such as Storage_StreamUnknownTypeError
    # ("unknowntype" contains "wnt") are caught by accident.
    platform_markers = ("WNT", "X11", "XWD", "Cocoa")
    header_list = [
        x
        for x in header_list
        if not any(marker in os.path.basename(x) for marker in platform_markers)
    ]
    return header_list


def case_sensitive_glob(wildcard):
    """
    Case sensitive glob for Windows.
    Designed for handling of GEOM and Geom modules
    This function makes the difference between GEOM_* and Geom_* under Windows
    """
    flist = glob.glob(wildcard)
    pattern = wildcard.split("*")[0]
    return [file_ for file_ in flist if pattern in file_]


def get_all_module_headers(module_name):
    """Returns a list with all header names"""
    mh = case_sensitive_glob(os.path.join(OCCT_INCLUDE_DIR, f"{module_name}.hxx"))
    mh += case_sensitive_glob(os.path.join(OCCT_INCLUDE_DIR, f"{module_name}_*.hxx"))
    mh = filter_header_list(mh, HXX_TO_EXCLUDE_FROM_BEING_INCLUDED)
    return sorted(map(os.path.basename, mh))


def check_has_related_handle(class_name):
    """For a given class :
    Check if a header exists.
    """
    if check_is_persistent(class_name):
        return False

    filename = os.path.join(OCCT_INCLUDE_DIR, f"Handle_{class_name}.hxx")
    other_possible_filename = filename
    if class_name.startswith("Graphic3d"):
        other_possible_filename = os.path.join(
            OCCT_INCLUDE_DIR, f"{class_name}_Handle.hxx"
        )
    return (
        os.path.exists(filename)
        or os.path.exists(other_possible_filename)
        or need_handle(class_name)
    )


def need_handle(class_name):
    """Returns True if the current parsed class needs an
    Handle to be defined. This is useful when headers define
    handles but no header"""
    # @TODO what about DEFINE_RTTI ?
    return (
        class_name in state.all_standard_handles
        or class_name in state.all_standard_transients
    )


_DEFINE_STANDARD_HANDLE_RE = re.compile(
    r"DEFINE_STANDARD_HANDLE[\s]*\([\w\s]+,+[\w\s]+\)"
)
# occt-800: many classes that derive from Standard_Transient no longer carry
# a DEFINE_STANDARD_HANDLE; they only have DEFINE_STANDARD_RTTI{,_INLINE,EXT}
# (C, Parent). Treat that as an implicit handle declaration so
# check_has_related_handle picks them up. DEFINE_DERIVED_ATTRIBUTE marks XCAF
# shape tools and similar classes as TDataStd_GenericEmpty subtypes.
_DEFINE_RTTI_RE = re.compile(
    r"DEFINE_(?:STANDARD_RTTI(?:_INLINE|EXT)?|DERIVED_ATTRIBUTE)\s*"
    r"\(\s*([\w]+)\s*,\s*[\w:]+\s*\)"
)
_DEFINE_HARRAY1_RE = re.compile(r"DEFINE_HARRAY1[\s]*\([\w\s]+,+[\w\s]+\)")
_DEFINE_HARRAY2_RE = re.compile(r"DEFINE_HARRAY2[\s]*\([\w\s]+,+[\w\s]+\)")
_DEFINE_HSEQUENCE_RE = re.compile(r"DEFINE_HSEQUENCE[\s]*\([\w\s]+,+[\w\s]+\)")
# Strip Standard_DEPRECATED("...") and Standard_DEPRECATED_STD("...") entirely
# (with the parens), so they disappear from the source rather than leaving a
# dangling //comment. OCCT 8.0 places these attributes mid-declaration (e.g.
# inside `using ... = X;`) which would otherwise produce malformed C++.
_STANDARD_DEPRECATED_RE = re.compile(
    r"Standard_DEPRECATED(?:_STD|_WARNING)?\s*\(\s*"
    r'(?:".*?(?:\\"|[^"])*?"(?:\s*".*?(?:\\"|[^"])*?")*)\s*\)'
)
_USING_ALIAS_RE = re.compile(r"\busing\s+([A-Za-z_]\w*)\s*=\s*([^;]+);")
_HANDLE_PARENS_RE = re.compile(r"Handle[\s]*\([\w\s]*\)")


def _collect_handle_macros(header_content):
    """Populate state.all_standard_handles with names declared via DEFINE_STANDARD_HANDLE
    or one of the DEFINE_STANDARD_RTTI* / DEFINE_DERIVED_ATTRIBUTE macros."""
    for match in _DEFINE_STANDARD_HANDLE_RE.findall(header_content):
        state.all_standard_handles.append(match.split("(")[1].split(",")[0])
    for match in _DEFINE_RTTI_RE.findall(header_content):
        if match not in state.all_standard_handles:
            state.all_standard_handles.append(match)


def _collect_harray_macros(header_content):
    """Populate state.all_harray1/2 and state.all_hsequence from DEFINE_HARRAY{1,2} /
    DEFINE_HSEQUENCE macros."""
    for regex, store, label in (
        (_DEFINE_HARRAY1_RE, state.all_harray1, "HARRAY1"),
        (_DEFINE_HARRAY2_RE, state.all_harray2, "HARRAY2"),
        (_DEFINE_HSEQUENCE_RE, state.all_hsequence, "HSEQUENCE"),
    ):
        for match in regex.findall(header_content):
            typename = match.split("(")[1].split(",")[0]
            base_typename = match.split(",")[1].split(")")[0]
            logging.info("Found %s definition %s:%s", label, typename, base_typename)
            store[typename] = base_typename.strip()


def _comment_out_macros(header_content):
    """Replace macros that confuse CppHeaderParser by their //commented form."""
    for token in (
        "DEFINE_STANDARD_HANDLE",
        "DEFINE_STANDARD_RTTIEXT",
        "DEFINE_STANDARD_RTTI_INLINE",
        "NCOLLECTION_HSEQUENCE",
    ):
        header_content = header_content.replace(token, f"//{token}")
    # Standard_DEPRECATED("...") form: drop the whole macro+parens first, then
    # //comment any bare leftover identifier. Order matters.
    header_content = _STANDARD_DEPRECATED_RE.sub("", header_content)
    for token in (
        "Standard_DEPRECATED",
        "DECLARE_TOBJOCAF_PERSISTENCE",
        "DEFINE_DERIVED_ATTRIBUTE",
    ):
        header_content = header_content.replace(token, f"//{token}")
    return header_content


def _strip_macros(header_content):
    """Drop attribute macros that prevent CppHeaderParser from working."""
    for token in ("DEFINE_STANDARD_ALLOC", "Standard_EXPORT", "Standard_NODISCARD"):
        header_content = header_content.replace(token, "")
    return header_content


def _rewrite_handle_parens(header_content):
    """Rewrite legacy `Handle(X)` syntax to `opencascade::handle<X>`."""
    for match in _HANDLE_PARENS_RE.findall(header_content):
        # matches are of the form ['Handle(Graphic3d_Structure)',
        # 'Handle(Graphic3d_DataStructureManager)']
        normalized = match.replace(" ", "")
        class_name = normalized.split("Handle(")[1].split(")")[0]
        if class_name == "" or not class_name[0].isupper():
            continue
        header_content = header_content.replace(
            normalized, f"opencascade::handle<{class_name}>"
        )
    return header_content


def _convert_using_to_typedef(header_content):
    """occt-800: rewrite simple C++11 `using X = Y;` aliases into classic
    `typedef Y X;` so the typedef pipeline picks them up. Many OCCT 8.0
    headers (GCE2d_MakeEllipse, ...) became `using` aliases for renamed
    classes. Skip template aliases (RHS contains '<'): they would produce SWIG
    %template instantiations against templates we don't expose."""

    def _replace(match):
        rhs = match.group(2).strip()
        if "<" in rhs:
            return match.group(0)
        return f"typedef {rhs} {match.group(1)};"

    return _USING_ALIAS_RE.sub(_replace, header_content)


def adapt_header_file(header_content):
    """Pre-process an OCCT header so CppHeaderParser can parse it.

    - Skips OCCT 8.0 deprecated alias headers entirely.
    - Collects DEFINE_STANDARD_HANDLE / DEFINE_STANDARD_RTTI* / DEFINE_HARRAY*
      / DEFINE_HSEQUENCE declarations into the corresponding global registries.
    - Strips or //comments out macros that the parser cannot handle.
    - Normalizes `occ::handle` and `Handle(X)` to `opencascade::handle<X>`.
    - Rewrites simple `using X = Y;` aliases to `typedef Y X;`.
    """
    if ("Deprecated alias to moved class" in header_content) or (
        "Alias to moved class" in header_content
    ):
        return ""

    _collect_handle_macros(header_content)
    _collect_harray_macros(header_content)
    header_content = _comment_out_macros(header_content)
    header_content = _strip_macros(header_content)
    # occ::handle must be normalized before using-to-typedef (a `using X =
    # occ::handle<Z>;` is template-aliased and intentionally skipped by the
    # rewrite); Handle(X) rewriting comes last because it introduces template
    # syntax that earlier passes don't expect.
    header_content = header_content.replace("occ::handle", "opencascade::handle")
    header_content = _convert_using_to_typedef(header_content)
    header_content = _rewrite_handle_parens(header_content)
    return header_content


def parse_header(header_filename):
    """Use CppHeaderParser module to parse header_filename"""
    with open(header_filename, "r", encoding="utf-8") as header_content:
        adapted_header_content = adapt_header_file(header_content.read())
        try:
            cpp_header = CppHeaderParser.CppHeader(adapted_header_content, "string")
        except CppHeaderParser.CppParseError as e:
            error_message = f"Error: cannot parse {header_filename}\n"
            error_message += f"Reason: {e}"
            raise RuntimeError(error_message) from e
    return cpp_header


def filter_typedefs(typedef_dict):
    """Remove some strange thing that generated SWIG
    errors
    """
    if "{" in typedef_dict:
        del typedef_dict["{"]
    if ":" in typedef_dict:
        del typedef_dict[":"]
    for key in list(typedef_dict):
        if key in TYPEDEF_TO_EXCLUDE:
            del typedef_dict[key]
            continue
        # remove typedefs that ends with function callbacks
        if key.endswith("Function"):
            logging.info("Skip typedef %s because ends with 'Function'", key)
            del typedef_dict[key]
            continue
        # remove typedefs tha ends with _fp (means function pointer?)
        if key.endswith("_fp"):
            logging.info("Skip typedef %s because ends with '_fp'", key)
            del typedef_dict[key]
            continue
        # remove typedefs tha ends with Func (function pointer)
        if key.endswith("Func"):
            logging.info("Skip typedef %s because ends with 'Func'", key)
            del typedef_dict[key]
            continue
        # occt-800: skip pointer typedefs (e.g. typedef NCollection_List<X>* Plos)
        # SWIG cannot generate %template(...) Foo<X>*; with a pointer
        if typedef_dict[key].rstrip().endswith("*"):
            logging.info("Skip typedef %s because target is a pointer type", key)
            del typedef_dict[key]
    for key in list(typedef_dict):
        typedef_dict[key] = typedef_dict[key].replace(" ::", "::")
        typedef_dict[key] = typedef_dict[key].replace(" , ", ", ")
    return typedef_dict


def get_type_for_ncollection_array(ncollection_array: str) -> str:
    """input : NCollection_Array1<Standard_Real>
    output : Standard_Real
    """
    return ncollection_array.split("<")[1].split(">")[0].strip()


def process_templates_from_typedefs(list_of_typedefs):
    """ """
    wrapper_str = "/* templates */\n"
    pyi_str = ""
    for t in list_of_typedefs:
        template_name = t[1].replace(" ", "")
        template_type = t[0]
        if "unsigned" not in template_type and "const" not in template_type:
            template_type = template_type.replace(" ", "")
        # we must include
        if not (
            template_type.endswith("::Iterator") or template_type.endswith("::Type")
        ):  # it's not an iterator
            wrap_template = all(
                forbidden_template not in template_type
                for forbidden_template in TEMPLATES_TO_EXCLUDE
            )
            if template_name in TEMPLATES_TO_EXCLUDE:
                continue
            # sometimes the template name is weird (parenthesis, comma etc.)
            # don't consider this
            if "_" not in template_name:
                wrap_template = False
                # del typedef_dict[key]
            if wrap_template:
                # wrapper_str += f"%template({template_name}) {template_type};\n"
                # if a NCollection_Array1, extend this template to benefit from pythonic methods
                # All "Array1" classes are considered as python arrays
                # TODO : it should be a good thing to use decorators here, to avoid code duplication
                basetype_hint = adapt_type_for_hint(
                    get_type_for_ncollection_array(template_type)
                )
                if "NCollection_Array1" in template_type:
                    # in this cas, we use the Array1ExtendIter(T) macro by default
                    # if the NCollection_Array1 involves Standard_Integer or Standard_Real
                    # then the NCollection_Array1 can be wrapped as a numpy array and the
                    # macro Array1NumpyTemplate is used.
                    base_type = template_type[:-1].split("NCollection_Array1<")[1]
                    # occt-800 typedefs use plain `double`/`int`/`float` instead
                    # of the Standard_* aliases; treat both forms identically
                    if base_type in ("Standard_ShortReal", "float"):
                        wrapper_str += "%apply (float* IN_ARRAY1, int DIM1) { (float* numpyArray1, int nRows1) };\n"
                        wrapper_str += "%apply (float* ARGOUT_ARRAY1, int DIM1) { (float* numpyArray1Argout, int nRows1Argout) };\n"
                        wrapper_str += f"Array1NumpyTemplate({template_name}, float, {base_type})\n"
                    elif base_type in ("Standard_Real", "double"):
                        wrapper_str += "%apply (double* IN_ARRAY1, int DIM1) { (double* numpyArray1, int nRows1) };\n"
                        wrapper_str += "%apply (double* ARGOUT_ARRAY1, int DIM1) { (double* numpyArray1Argout, int nRows1Argout) };\n"
                        wrapper_str += f"Array1NumpyTemplate({template_name}, double, {base_type})\n"
                    elif base_type in ("Standard_Integer", "int"):
                        wrapper_str += "%apply (long long* IN_ARRAY1, int DIM1) { (long long* numpyArray1, int nRows1) };\n"
                        wrapper_str += "%apply (long long* ARGOUT_ARRAY1, int DIM1) { (long long* numpyArray1Argout, int nRows1Argout) };\n"
                        wrapper_str += f"Array1NumpyTemplate({template_name}, long long, {base_type})\n"
                    elif base_type == "Poly_Triangle":
                        wrapper_str += "%apply (long long* IN_ARRAY2, int DIM1, int DIM2) { (long long* numpyArray2, int nRows2, int nDims2) };\n"
                        wrapper_str += "%apply (long long* ARGOUT_ARRAY1, int DIM1) { (long long* numpyArray2Argout, int aSizeArgout) };\n"
                        wrapper_str += f"Array1OfTriaNumpyTemplate({template_name}, Poly_Triangle)\n\n"

                    # 2D elements, i.e. that provides X() and Y() methods
                    elif base_type in ["gp_XY", "gp_Vec2d", "gp_Pnt2d", "gp_Dir2d"]:
                        wrapper_str += "%apply (double* IN_ARRAY2, int DIM1, int DIM2) { (double* numpyArray2, int nRows2, int nDims2) };\n"
                        wrapper_str += "%apply (double* ARGOUT_ARRAY1, int DIM1) { (double* numpyArray2Argout, int aSizeArgout) };\n"
                        wrapper_str += (
                            f"Array1Of2DNumpyTemplate({template_name}, {base_type})\n"
                        )
                    # 3D elements, i.e. that provides X(), Y() and Z() methods
                    elif base_type in ["gp_XYZ", "gp_Vec", "gp_Pnt", "gp_Dir"]:
                        wrapper_str += "%apply (double* IN_ARRAY2, int DIM1, int DIM2) { (double* numpyArray2, int nRows2, int nDims2) };\n"
                        wrapper_str += "%apply (double* ARGOUT_ARRAY1, int DIM1) { (double* numpyArray2Argout, int aSizeArgout) };\n"
                        wrapper_str += (
                            f"Array1Of3DNumpyTemplate({template_name}, {base_type})\n"
                        )
                    else:  # no numpy support
                        wrapper_str += f"%template({template_name}) {template_type};\n"
                        wrapper_str += f"Array1ExtendIter({base_type})\n\n"
                    pyi_str += NCOLLECTION_ARRAY1_EXTEND_TEMPLATE_PYI.substitute(
                        {
                            "NCollection_Array1_Template_Instanciation": template_name,
                            "Type_T": f"{basetype_hint}",
                        }
                    )
                elif "NCollection_Array2" in template_type:
                    # same than NCollection_Array1
                    base_type = template_type.split("NCollection_Array2<")[1].split(
                        ">"
                    )[0]
                    # occt-800: typedefs use plain `double`/`int`/`float`
                    if base_type in ("Standard_ShortReal", "float"):
                        wrapper_str += "%apply (float* IN_ARRAY2, int DIM1, int DIM2) { (float* numpyArray2, int nRows2, int nCols2) };\n"
                        wrapper_str += "%apply (float* ARGOUT_ARRAY1, int DIM1) { (float* numpyArray2Argout, int aSizeArgout) };\n"
                        wrapper_str += f"Array2NumpyTemplate({template_name}, float, {base_type})\n"
                    elif base_type in ("Standard_Real", "double"):
                        wrapper_str += "%apply (double* IN_ARRAY2, int DIM1, int DIM2) { (double* numpyArray2, int nRows2, int nCols2) };\n"
                        wrapper_str += "%apply (double* ARGOUT_ARRAY1, int DIM1) { (double* numpyArray2Argout, int aSizeArgout) };\n"
                        wrapper_str += f"Array2NumpyTemplate({template_name}, double, {base_type})\n"
                    elif base_type in ("Standard_Integer", "int"):
                        wrapper_str += "%apply (long long* IN_ARRAY2, int DIM1, int DIM2) { (long long* numpyArray2, int nRows2, int nCols2) };\n"
                        wrapper_str += "%apply (long long* ARGOUT_ARRAY1, int DIM1) { (long long* numpyArray2Argout, int aSizeArgout) };\n"
                        wrapper_str += f"Array2NumpyTemplate({template_name}, long long, {base_type})\n"
                    # 2D elements
                    elif base_type in ["gp_XY", "gp_Vec2d", "gp_Pnt2d", "gp_Dir2d"]:
                        wrapper_str += "%apply (double* IN_ARRAY3, int DIM1, int DIM2, int DIM3) { (double* numpyArray3, int nRows3, int nCols3, int nDims3) };\n"
                        wrapper_str += "%apply (double* ARGOUT_ARRAY1, int DIM1) { (double* numpyArray3Argout, int aSizeArgout) };\n"
                        wrapper_str += (
                            f"Array2Of2DNumpyTemplate({template_name}, {base_type})\n"
                        )
                    # 3D elements
                    elif base_type in ["gp_XYZ", "gp_Vec", "gp_Pnt", "gp_Dir"]:
                        wrapper_str += "%apply (double* IN_ARRAY3, int DIM1, int DIM2, int DIM3) { (double* numpyArray3, int nRows3, int nCols3, int nDims3) };\n"
                        wrapper_str += "%apply (double* ARGOUT_ARRAY1, int DIM1) { (double* numpyArray3Argout, int aSizeArgout) };\n"
                        wrapper_str += (
                            f"Array2Of3DNumpyTemplate({template_name}, {base_type})\n"
                        )
                    else:
                        wrapper_str += f"%template({template_name}) {template_type};\n"
                elif "NCollection_List" in template_type:
                    wrapper_str += f"%template({template_name}) {template_type};\n"
                    # derive the matching ListIterator typedef name from the
                    # list typedef (TopTools_ListOfShape -> TopTools_ListIteratorOfListOfShape)
                    list_iter_name = template_name.replace(
                        "ListOf", "ListIteratorOfListOf", 1
                    )
                    wrapper_str += NCOLLECTION_LIST_EXTEND_TEMPLATE.substitute(
                        {
                            "NCollection_List_Template_Instanciation": template_type,
                            "NCollection_ListIterator_Name": list_iter_name,
                        }
                    )
                    pyi_str += NCOLLECTION_LIST_EXTEND_TEMPLATE_PYI.substitute(
                        {
                            "NCollection_List_Template_Instanciation": template_name,
                            "Type_T": f"{basetype_hint}",
                        }
                    )
                elif "NCollection_Sequence" in template_type:
                    wrapper_str += f"%template({template_name}) {template_type};\n"
                    wrapper_str += NCOLLECTION_SEQUENCE_EXTEND_TEMPLATE.substitute(
                        {"NCollection_Sequence_Template_Instanciation": template_type}
                    )
                    pyi_str += NCOLLECTION_SEQUENCE_EXTEND_TEMPLATE_PYI.substitute(
                        {
                            "NCollection_Sequence_Template_Instanciation": template_name,
                            "Type_T": f"{basetype_hint}",
                        }
                    )
                elif "NCollection_DataMap" in template_type:
                    # NCollection_Datamap is similar to a Python dict,
                    # it's a (key, value) store. Defined as
                    # template < class TheKeyType,
                    # class TheItemType,
                    # class Hasher = NCollection_DefaultHasher<TheKeyType> >
                    # some occt methods return such an object, but the iterator can't be accessed
                    # through Python. Se we extend this class with a Keys() method that iterates over
                    # NCollection_DataMap keys and returns a Python list of key objects.
                    # Note : works for standard_Integer keys only so far
                    # occt-800: ignore Items()/KeyValues() returning ItemsView<...>
                    # which is non-default-constructible and cannot be wrapped by SWIG
                    wrapper_str += f"%ignore {template_type}::Items;\n"
                    wrapper_str += f"%ignore {template_type}::KeyValues;\n"
                    wrapper_str += f"%template({template_name}) {template_type};\n"
                    if "<Standard_Integer" in template_type or "<int" in template_type:
                        wrapper_str += NCOLLECTION_DATAMAP_EXTEND_TEMPLATE.substitute(
                            {
                                "NCollection_DataMap_Template_Instanciation": template_type,
                                "NCollection_DataMap_Template_Name": template_name,
                            }
                        )
                elif (
                    "NCollection_IndexedMap" in template_type
                    or "NCollection_IndexedDataMap" in template_type
                ):
                    # occt-800: NCollection_IndexedMap/IndexedDataMap expose
                    # IndexedItems()/Items()/KeyValues() returning a non-default-
                    # constructible View<...>. SWIG cannot wrap them.
                    wrapper_str += f"%ignore {template_type}::Items;\n"
                    wrapper_str += f"%ignore {template_type}::KeyValues;\n"
                    wrapper_str += f"%ignore {template_type}::IndexedItems;\n"
                    # occt-800rc5 bug: Contained() references a non-existent
                    # IndexedDataMapNode::Key field (should be Key1)
                    wrapper_str += f"%ignore {template_type}::Contained;\n"
                    wrapper_str += f"%template({template_name}) {template_type};\n"
                elif (
                    template_type.startswith("NCollection_HArray1<")
                    or template_type.startswith("NCollection_HArray2<")
                    or template_type.startswith("NCollection_HSequence<")
                ):
                    # occt-800: NCollection_HArray1/HArray2/HSequence are now
                    # plain template classes deriving from Standard_Transient.
                    # Register the typedef -> ALL_HARRAY{1,2}/HSEQUENCE so that
                    # process_handles emits %wrap_handle and process_harrayN
                    # emits the fake class definition + %make_alias (the same
                    # path used in OCCT 7.9 with the DEFINE_HARRAY1 macro).
                    inner = template_type.split("<", 1)[1].rsplit(">", 1)[0].strip()
                    if template_type.startswith("NCollection_HArray1<"):
                        state.all_harray1[template_name] = (
                            f"NCollection_Array1<{inner}>"
                        )
                    elif template_type.startswith("NCollection_HArray2<"):
                        state.all_harray2[template_name] = (
                            f"NCollection_Array2<{inner}>"
                        )
                    else:
                        state.all_hsequence[template_name] = (
                            f"NCollection_Sequence<{inner}>"
                        )
                else:
                    wrapper_str += f"%template({template_name}) {template_type};\n"

        elif (
            template_name.endswith("Iter") or "_ListIteratorOf" in template_name
        ):  # it's a lst iterator, we use another way to wrap the template
            # #%template(TopTools_ListIteratorOfListOfShape) NCollection_TListIterator<TopTools_ListOfShape>;
            if "IteratorOf" in template_name:
                if "::handle" not in template_type:
                    typ = (template_type.split("<")[1]).split(">")[0]
                else:
                    h_typ = (template_type.split("<")[2]).split(">")[0]
                    typ = f"opencascade::handle<{h_typ}>"
            else:  # template_name.endswith("Iter") — guaranteed by the elif above
                typ = template_name.split("Iter")[0]
            wrapper_str += (
                f"%template({template_name}) NCollection_TListIterator<{typ}>;\n"
            )
    wrapper_str += "/* end templates declaration */\n"
    return wrapper_str, pyi_str


def adapt_type_for_hint_typedef(typedef_type_str):
    typedef_type_str = typedef_type_str.replace(" *", "")
    typedef_type_str = typedef_type_str.replace("&OutValue", "")
    typedef_type_str = typedef_type_str.replace("class", "")
    if "char" in typedef_type_str or "Char" in typedef_type_str:
        typedef_type_str = "str"
    if (
        "_int" in typedef_type_str
        or " int" in typedef_type_str
        or " long" in typedef_type_str
    ):
        typedef_type_str = "int"
    if "double" in typedef_type_str:
        typedef_type_str = "float"
    if (
        "void" in typedef_type_str
        or "VOID" in typedef_type_str
        and "avoid" not in typedef_type_str
    ):
        typedef_type_str = "None"
    if "GUID" in typedef_type_str:
        typedef_type_str = "str"
    if "size_t" in typedef_type_str:
        typedef_type_str = "int"
    if "struct" in typedef_type_str:
        typedef_type_str = "int"
    return typedef_type_str


def str_in(list_of_patterns, a_string):
    """a utility function that returns True if any of the item
    of the list patterns is in the a_string"""
    return any(patt in a_string for patt in list_of_patterns)


def process_typedefs(typedefs_dict):
    """Take a typedef dictionary and returns a SWIG definition string"""
    templates_str = ""
    typedef_pyi_str = ""  # NewTypes related to typedef aliases
    # pythoncode for typedef aliases, to be inserted at the end of the swig interface file
    typedef_aliases_str = "/* class aliases */\n%pythoncode {\n"

    typedef_str = "/* typedefs */\n"
    templates = []
    # careful, there might be some strange things returned by CppHeaderParser
    # they should not be taken into account
    filtered_typedef_dict = filter_typedefs(typedefs_dict)
    # we check if there is any type def type that relies on an opencascade::handle
    # if this is the case, we must add the corresponding python module
    # as a dependency otherwise it leads to a runtime issue

    for template_type in filtered_typedef_dict.values():
        if "opencascade::handle" in template_type:  # we must add a PYTHON DEPENDENCY
            if template_type.count("<") == 2:
                h_typ = (template_type.split("<")[2]).split(">")[0]
            elif template_type.count("<") == 1:
                h_typ = (template_type.split("<")[1]).split(">")[0]
            else:
                logging.warning(
                    "This template type cannot be handled: %s", template_type
                )
                continue
            module = h_typ.split("_")[0]
            if module != state.current_module:
                # need to be added to the list of dependent object
                if (module not in state.python_module_dependency) and (
                    is_module(module)
                ):
                    state.python_module_dependency.append(module)

    sorted_list_of_typedefs = sorted(filtered_typedef_dict.keys())
    for typedef_value in sorted_list_of_typedefs:
        # some occttype defs are actually templated classes,
        # for instance
        # typedef NCollection_Array1<Standard_Real> TColStd_Array1OfReal;
        # this must be wrapped as a typedef but rather as an instaicated class
        # the good way to proceed is:
        # %{include "NCollection_Array1.hxx"}
        # %template(TColStd_Array1OfReal) NCollection_Array1<Standard_Real>;
        # we then check if > or < are in the typedef string then we process it.
        typedef_type = filtered_typedef_dict[typedef_value]
        typedef_str += f"typedef {typedef_type} {typedef_value};\n"
        #
        # Check if the typedef is a template
        #
        if str_in(["<", ">"], f"{typedef_type}"):
            templates.append([typedef_type, typedef_value])
        #
        # Check if it's just a class alias
        #
        elif not str_in(["*", ":", " ", "Standard"], f"{typedef_type}"):
            # we create the alias in python
            # e.g.
            # BRepOffsetAPI_= BRepAlgoAPI_Cut
            # only if the type is a module class (exclude char, Standard_Real etc.)
            #
            typedef_module_name = typedef_type.split("_")[0]
            if is_module(typedef_module_name):
                if state.current_module == typedef_module_name:
                    typedef_aliases_str += f"{typedef_value}={typedef_type}\n"
                else:
                    typedef_aliases_str += f"{typedef_value}=OCC.Core.{typedef_module_name}.{typedef_type}\n"
        check_dependency(typedef_type.split()[0])
        # Define a new type, only for aliases
        type_to_define = typedef_type
        match_1 = [
            "<",
            ":",
            "struct",
            "union",
            ")",
            "NCollection_Array1",
            "NCollection_List",
            "NCollection_DataMap",
            "NCollection_Sequence",
        ]
        if (
            all(match not in type_to_define for match in match_1)
            and type_to_define is not None
            and ")" not in typedef_value
        ):
            type_to_define = adapt_type_for_hint_typedef(type_to_define)
            typedef_pyi_str += (
                f'\n{typedef_value} = NewType("{typedef_value}", {type_to_define})'
            )
        elif (
            ")" not in typedef_value
            and "(" not in typedef_value
            and ":" not in typedef_value
            and "NCollection_Array1" not in type_to_define
            and "NCollection_List" not in type_to_define
            and "NCollection_DataMap" not in type_to_define
            and "NCollection_Sequence" not in type_to_define
        ):
            typedef_pyi_str += "\n# the following typedef cannot be wrapped as is"
            typedef_pyi_str += f'\n{typedef_value} = NewType("{typedef_value}", Any)'

    typedef_pyi_str += "\n"
    typedef_str += "/* end typedefs declaration */\n\n"
    # then we process templates
    # at this stage, we get a list as follows
    templates_def, templates_pyi = process_templates_from_typedefs(templates)
    templates_str += templates_def
    templates_str += "\n"
    # close aliases
    typedef_aliases_str += "}\n"
    return (
        templates_str + typedef_str,
        typedef_pyi_str + templates_pyi,
        typedef_aliases_str,
    )


def adapt_enum_value(enum_value):
    """Take for example Graphic3d_TextureSetBits.hxx

    //! Standard texture units combination bits.
    enum Graphic3d_TextureSetBits
    {
      Graphic3d_TextureSetBits_NONE              = 0,
      Graphic3d_TextureSetBits_BaseColor         = (unsigned int )(1 << int(Graphic3d_TextureUnit_BaseColor)),
      Graphic3d_TextureSetBits_Emissive          = (unsigned int )(1 << int(Graphic3d_TextureUnit_Emissive)),
      Graphic3d_TextureSetBits_Occlusion         = (unsigned int )(1 << int(Graphic3d_TextureUnit_Occlusion)),
      Graphic3d_TextureSetBits_Normal            = (unsigned int )(1 << int(Graphic3d_TextureUnit_Normal)),
      Graphic3d_TextureSetBits_MetallicRoughness = (unsigned int )(1 << int(Graphic3d_TextureUnit_MetallicRoughness)),
    };

    The values (unsigned int )(1 << int(Graphic3d_TextureUnit_BaseColor)) cannot be processed as is by SWIG.
    We transform them to Graphic3d_TextureUnit_BaseColor
    """
    if isinstance(enum_value, int) or "int (" not in enum_value:
        return enum_value

    return enum_value.split("int ( ")[1].split(")")[0].strip()


def process_enums(enums_list):
    """Take an enum list and generate a compliant SWIG string
    Then create a python class that mimics the enum
    for instance, from the TopAbs_Orientation.hxx header, we have
    enum TopAbs_Orientation
    {
    TopAbs_FORWARD,
    TopAbs_REVERSED,
    TopAbs_INTERNAL,
    TopAbs_EXTERNAL
    };

    In SWIG, this will be wrapped in the interface file as

    enum TopAbs_Orientation {
      TopAbs_FORWARD = 0,
      TopAbs_REVERSED = 1,
      TopAbs_INTERNAL = 2,
      TopAbs_EXTERNAL = 3,
    };

    However, python does not know anything about TopAbs_Orientation, he only knows TopAbs_FORWARD
    So we also create a python class that mimics the enum and let python know about the TopAbs_Orientation type

    %pythoncode {
    class TopAbs_Orientation:
        TopAbs_FORWARD = 0
        TopAbs_REVERSED = 1
        TopAbs_INTERNAL = 2
        TopAbs_EXTERNAL = 3
    }

    Then, from python, it's possible to use:
    >>> TopAbs_Orientation.TopAbs_FORWARD

    Note: this only makes sense for named enums
    """
    enum_str = "/* public enums */\n"

    enum_python_proxies = "/* python proxy classes for enums */\n" + "%pythoncode {\n"
    enum_pyi_str = ""
    # loop over enums
    for enum in enums_list:
        number_of_string_aliases = 0
        # count the number of lines such
        # as Quantity_NOC_GREEN1 = Quantity_NOC_GREEN
        # in this case, the integers must ne be incremented
        # in the wrapper otherwise ther's an offset
        alias_str = ""
        python_proxy = True
        if "name" not in enum:
            enum_name = ""
            python_proxy = False
        else:
            enum_name = enum["name"]
            if enum_name not in state.all_enums:
                state.all_enums.append(enum_name)

        if enum_name in ENUMS_TO_EXLUDE:
            logging.info("Skipping Enum: %s", enum_name)
            continue

        # occt-800: respect "enum class X" (scoped enum) so values like
        # gp_Dir::D::X don't collide with member functions like gp_Dir::X()
        is_enum_class = enum.get("isclass", False)
        enum_keyword = "enum class" if is_enum_class else "enum"
        logging.info("Enum: %s", enum_name)
        enum_str += f"{enum_keyword} {enum_name}" + " {\n"
        if python_proxy:
            enum_python_proxies += f"\nclass {enum_name}(IntEnum):\n"
            enum_pyi_str += f"\nclass {enum_name}(IntEnum):\n"
        for enum_value in enum["values"]:
            adapted_enum_value = adapt_enum_value(enum_value["value"])
            if state.current_module == "Quantity":
                # special case for Quantity_Color
                if isinstance(adapted_enum_value, str):
                    # if adapted_enum_value.isalpha():
                    number_of_string_aliases += 1
                else:
                    adapted_enum_value -= number_of_string_aliases
            enum_str += f"\t{enum_value['name']} = {adapted_enum_value},\n"
            if python_proxy:
                # occt-800: rename enum members that collide with Python
                # keywords (e.g. `None` in GProp_PEquation::Type)
                py_name = enum_value["name"]
                if py_name in keyword.kwlist:
                    py_name = f"{py_name}_"
                enum_python_proxies += f"\t{py_name} = {adapted_enum_value}\n"
                enum_pyi_str += f"    {py_name}: int = ...\n"
                # then, in both proxy and stub files, we create the alias for each named enum,
                # for instance
                # gp_IntrisicXYZ = gp_EulerSequence.gp_IntrinsicXYZ
                alias_str += f"{py_name} = {enum_name}.{py_name}\n"
        enum_python_proxies += alias_str
        enum_pyi_str += "\n" + alias_str
        enum_str += "};\n\n"

    enum_python_proxies += "};\n"
    enum_str += "/* end public enums declaration */\n\n"
    enum_python_proxies += "/* end python proxy for enums */\n\n"
    return enum_str + enum_python_proxies, enum_pyi_str


def is_return_type_enum(return_type):
    """This method returns True is an enum is returned. For instance:
    BRepCheck_Status &
    BRepCheck_Status
    """
    return any(r in state.all_enums for r in return_type.split())


def _apply_typedef_rewrites(text):
    """Repeatedly substitute canonical NCollection template forms with
    their typedef aliases until the string stabilises. Multiple passes are
    required because nested templates are usually defined in terms of
    other typedefs (e.g. NCollection_List<TopoDS_Shape> -> TopTools_ListOfShape
    must run before the IndexedDataMap that contains it can match)."""
    if not state.harray_typedef_rewrites:
        return text
    # CppHeaderParser emits ">>" as "> >" - collapse the gap so the rewrite
    # keys (which are normalized) match.
    text = re.sub(r">\s+>", ">>", text)
    for _ in range(5):  # bounded loop, 5 nesting levels is more than enough
        prev = text
        for tpl, name in state.harray_typedef_rewrites:
            if tpl in text:
                text = text.replace(tpl, name)
        if text == prev:
            break
    return text


def adapt_param_type(param_type):
    param_type = param_type.strip()
    # occt-800: rewrite canonical NCollection<...> forms back to the typedef
    # alias so SWIG type tags match across modules. The list is built from
    # TopTools_/TColgp_/TColStd_/... headers in scan_typedef_aliases().
    param_type = _apply_typedef_rewrites(param_type)
    if "CString" in param_type:
        param_type = param_type.replace("const Standard_CString", "Standard_CString")
        param_type = param_type.replace("Standard_CString &", "Standard_CString")
    param_type = param_type.replace("DrawType", "NIS_Drawer::DrawType")
    if param_type == "const TCollection_AsciiString &":
        param_type = "TCollection_AsciiString"
    if param_type == "const TCollection_ExtendedString &":
        param_type = "TCollection_ExtendedString"
    # some enums are type defs and not properly handled by swig
    # these are Standard_Integer
    for pattern in STANDARD_INTEGER_TYPEDEF:
        if pattern in param_type:
            if "const" in param_type and "&" in param_type:
                # const pattern is wrapped as an integer
                param_type = param_type.replace(pattern, "int")
                param_type = param_type.replace("const", "")
                param_type = param_type.replace("&", "")
            elif "const" in param_type:
                param_type = param_type.replace("const", "")
                param_type = param_type.replace(pattern, "int")
            elif "&" in param_type:  # pattern & is an out value
                param_type = param_type.replace("&", "")
                param_type = param_type.replace(pattern, "Standard_Integer &OutValue")
            elif pattern == param_type:
                param_type = param_type.replace(pattern, "int")
            else:
                logging.warning("Unknown pattern in Standard_Integer typedef")
    # replace Standard_IStream with std::istream
    # so that SWIG template can apply
    param_type = param_type.replace("Standard_IStream", "std::istream")
    param_type = param_type.replace("Standard_SStream", "std::stringstream")
    param_type = param_type.strip()
    check_dependency(param_type)
    return param_type


def adapt_param_type_and_name(param_type_and_name):
    """We sometime need to replace some argument type and name
    to properly deal with byref values
    """
    # bool, int and double passed by reference in c++
    if (
        ("Standard_Real &" in param_type_and_name)
        or ("Quantity_Parameter &" in param_type_and_name)
        or ("Quantity_Length &" in param_type_and_name)
        or ("V3d_Coordinate &" in param_type_and_name)
        or (param_type_and_name.startswith("double &"))
    ) and "const" not in param_type_and_name:
        adapted_param_type_and_name = "Standard_Real &OutValue"
    elif (
        ("Standard_ShortReal &" in param_type_and_name)
        or (param_type_and_name.startswith("float &"))
    ) and "const" not in param_type_and_name:
        adapted_param_type_and_name = "Standard_ShortReal &OutValue"
    elif (
        ("Standard_Integer &" in param_type_and_name)
        or (param_type_and_name.startswith("int &"))
    ) and "const" not in param_type_and_name:
        adapted_param_type_and_name = "Standard_Integer &OutValue"
    elif (
        "Standard_OStream&" in param_type_and_name
        or "Standard_OStream &" in param_type_and_name
        or "std::ostream&" in param_type_and_name
        or "std::ostream &" in param_type_and_name
    ):
        adapted_param_type_and_name = "std::ostream &OutValue"
    elif (
        ("Standard_Boolean &" in param_type_and_name)
        or (param_type_and_name.startswith("bool &"))
    ) and "const" not in param_type_and_name:
        adapted_param_type_and_name = "Standard_Boolean &OutValue"
    elif (
        "opencascade::handle<TCollection_HAsciiString> &" in param_type_and_name
    ) and "const" not in param_type_and_name:
        adapted_param_type_and_name = (
            "opencascade::handle<TCollection_HAsciiString> &OutValue"
        )
    # some enums can also be passed as reference, among them
    # we look for getenirc patterns such as
    # TopAbs_Orientation &Or
    # FairCurve_AnalysisCode &Code
    # etc.
    elif (param_type_and_name.split()[0] in state.all_enums) and (
        param_type_and_name.split()[1].startswith("&")
    ):
        enum_name = param_type_and_name.split()[0]
        if enum_name not in state.all_byref_enums:
            state.all_byref_enums.append(enum_name)
        logging.info(
            "Enum passed by reference: %s changed to %s &OutValue",
            param_type_and_name,
            enum_name,
        )
        adapted_param_type_and_name = f"{enum_name} &OutValue"
    else:
        adapted_param_type_and_name = param_type_and_name
    if "& &" in adapted_param_type_and_name:
        adapted_param_type_and_name = adapted_param_type_and_name.replace("& &", "&")
    return adapted_param_type_and_name


def check_dependency(item):
    """For any type or class name passe to this function,
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
    filt = [
        "const ",
        "static ",
        "virtual ",
        "clocale_t",
        "pointer",
        "size_type",
        "void",
        "reference",
        "const_",
        "inline ",
    ]
    for f in filt:
        item = item.replace(f, "")
    if not item:  # if item list is empty
        return False
    # the element can be either a template ie Handle(Something) else Something_
    # or opencascade::handle<Some_Class>
    if item.startswith("Handle ("):
        item = item.split("Handle ( ")[1].split(")")[0].strip()
        module = item.split("_")[0]
    elif item.startswith("Handle_"):
        module = item.split("_")[1]
    elif item.startswith("opencascade::handle<"):
        item = item.split("<")[1].split(">")[0].strip()
        module = item.split("_")[0]
    elif item.startswith("occ::handle<"):
        # occt-800 introduced the occ::handle alias for opencascade::handle
        item = item.split("<")[1].split(">")[0].strip()
        module = item.split("_")[0]
    elif item.count("_") > 0:  # Standard_Integer or NCollection_CellFilter_InspectorXYZ
        module = item.split("_")[0]
    else:  # do nothing, it's a trap
        return False
    # we strip the module, who knows, there maybe trailing spaces
    module = module.strip()
    # TODO : is the following line really necessary ?
    if module == "Font":  # forget about Font dependencies, issues with FreeType
        return True
    if module != state.current_module:
        # need to be added to the list of dependent object
        if (module not in state.python_module_dependency) and (is_module(module)):
            state.python_module_dependency.append(module)
    return module


def adapt_return_type(return_type):
    """adapt the type definition"""
    replaces = [
        "public",
        "protected : private",  # TODO: CppHeaderParser may badly parse these methods
        "DEFINE_NCOLLECTION_ALLOC :",
        "DEFINE_NCOLLECTION_ALLOC",
    ]
    for replace in replaces:
        return_type = return_type.replace(replace, "")
    return_type = return_type.strip()
    # occt-800: rewrite canonical NCollection<...> forms back to typedef alias
    return_type = _apply_typedef_rewrites(return_type)

    if (
        "const" in return_type
        and "&" in return_type
        and ("Surface" in return_type or "Curve" in return_type)
        and "handle" not in return_type
    ):
        logging.warning("%s wrapped as a copy", return_type)
        return_type = return_type.replace("const", "")
        return_type = return_type.replace("&", "")
        return_type = return_type.strip()
        return return_type
    # replace Standard_CString with char *
    return_type = return_type.replace("const Standard_CString", "Standard_CString")
    return_type = return_type.replace("Standard_CString &", "Standard_CString")
    # remove const if const virtual double *
    return_type = return_type.replace(": static", "static")
    return_type = return_type.replace(": const", "const")
    return_type = return_type.replace("const virtual double *", "virtual double *")
    return_type = return_type.replace(
        "TAncestorMap", "TopTools_IndexedDataMapOfShapeListOfShape"
    )
    # for instance "const TopoDS_Shape & -> ["const", "TopoDS_Shape", "&"]
    # opencascade::handle may contain extra spaces, that has to be removed
    if "opencascade::handle" in return_type:
        return_type = return_type.replace(" >", ">")
    if (("gp" in return_type) and "TColgp" not in return_type) or (
        "TopoDS" in return_type
    ):
        return_type = return_type.replace("&", "").strip()
    check_dependency(return_type)
    # check is it is an enum
    if is_return_type_enum(return_type) and "&" in return_type:
        # remove the reference
        return_type = return_type.replace("&", "")
    return return_type


def adapt_function_name(f_name):
    """Some function names may result in errors with SWIG"""
    f_name = f_name.replace("operator", "operator ")
    return f_name


def get_module_docstring(module_name):
    """The module docstring is not provided anymore in cdl files since
    opencascade 7 and higher was released.
    Instead, the link to the official package documentation is
    used, for instance, for the gp package:
    https://www.opencascade.com/doc/occt-7.4.0/refman/html/package_gp.html
    """
    module_docstring = f"{module_name} module, see official documentation at\n"
    module_docstring += f"{DOC_URL}/package_{module_name.lower()}.html"
    return module_docstring


def process_function_docstring(f):
    """Create the docstring, for the function f,
    that will be used by the wrapper.
    For that, first check the function parameters and type
    then add the doxygen value.
    We use the numpy doc docstring convention see
    https://numpydoc.readthedocs.io/en/latest/format.html
    """
    function_name = f["name"]
    function_name = adapt_function_name(function_name)
    string_to_return = '\t\t%feature("autodoc", "'
    # the returns
    ret = []
    # first process parameters
    parameters_string = ""
    if f["parameters"]:  # at least one element in the list, i.e. at least one parameter
        # we add a "Parameters section"
        parameters_string += "\nParameters\n----------\n"
        for param in f["parameters"]:
            param_type = adapt_param_type(param["type"])
            # remove const and &
            param_type = fix_type(param_type)
            # we change opencascade::handle<XXX> & to XXX
            if "opencascade::handle" in param_type:
                param_type = param_type.split("opencascade::handle<")[1].split(">")[0]
            # in the docstring, we don't care about the "&"
            # it's not the matter of a python user
            param_type = param_type.replace("&", "")
            # same for the const
            param_type = param_type.replace("const", "")
            param_type = param_type.strip()
            # a TCollection_AsciiString expects a str
            if param_type in ["TCollection_AsciiString", "TCollection_ExtendedString"]:
                param_type = "str"
            # check the &OutValue
            the_type_and_name = param["type"] + param["name"]
            if "OutValue" in adapt_param_type_and_name(the_type_and_name):
                # this parameter has to be added to the
                # returns, not the parameters of the python method
                ret.append(f'{param["name"]}: {param_type}')
                continue
            # add the parameter to the list
            parameters_string += f'{param["name"]}: {param_type}'
            if "defaultValue" in param:
                def_value = adapt_default_value(param["defaultValue"])
                parameters_string += f" (optional, default to {def_value})"
            parameters_string += "\n"
        parameters_string += "\n"

    # return types:
    returns_string = "Return\n-------\n"
    method_return_type = adapt_return_type(f["rtnType"])
    if ret:  # at least on by ref parameter
        for r in ret:
            returns_string += f"{r}\n"
    elif method_return_type != "void":
        method_return_type = method_return_type.replace("&", "")
        # ret = ret.replace("virtual", "")
        method_return_type = fix_type(method_return_type)
        method_return_type = method_return_type.replace(": static ", "")
        method_return_type = method_return_type.replace("static ", "")
        method_return_type = method_return_type.strip()
        returns_string += f"{method_return_type}\n"
    else:
        returns_string += "None\n"
    returns_string += "\n"

    # process doxygen strings
    doxygen_string = "No available documentation.\n"
    # since occt-7.9.0, doxygen strings are slightly changed
    # have to remove the first line //@name if ever it is present
    if "doxygen" in f:
        doxygen_string = f["doxygen"]
        if doxygen_string.startswith("//! @name "):
            doxy_lines = doxygen_string.split("\n")
            doxygen_string = "\n".join(doxy_lines[1:])
    if "doxygen" not in f or len(doxygen_string) <= 5:
        doxygen_string = "No available documentation.\n"
    else:  # process doxygen string
        # remove comment separator
        doxygen_string = doxygen_string.replace("//! ", "")
        # replace " with '
        doxygen_string = doxygen_string.replace('"', "'")
        # remove ??/ that causes a compilation issue in InterfaceGraphic
        doxygen_string = doxygen_string.replace("??", "")
        # remove <br>
        # first, a strange thing in BSplClib
        doxygen_string = doxygen_string.replace("\\ <br>", " ")
        doxygen_string = doxygen_string.replace("<br>", "")
        # replace <me> with <self>, which is more pythonic
        doxygen_string = doxygen_string.replace("<me>", "<self>")
        # make '\r' correctly processed
        doxygen_string = doxygen_string.replace(r"\\return", "Return")
        doxygen_string = doxygen_string.replace("\\r", "")
        # replace \n with space
        doxygen_string = doxygen_string.replace("\n", " ")
        doxygen_string = doxygen_string.replace("'\\n'", "A newline")
        # replace TRUE and FALSE with True and False
        doxygen_string = doxygen_string.replace("TRUE", "True")
        doxygen_string = doxygen_string.replace("FALSE", "False")
        # misc
        doxygen_string = doxygen_string.replace("@return", "\nReturn:")
        # the input parameters
        doxygen_string = doxygen_string.replace("@param[in]", "\nInput parameter:")
        doxygen_string = doxygen_string.replace("@param ", "\nParameter ")
        # see also
        doxygen_string = doxygen_string.replace("@sa", "\nSee also:")
        # replace the extra spaces
        doxygen_string = doxygen_string.replace("    ", " ")
        doxygen_string = doxygen_string.replace("   ", " ")
        doxygen_string = doxygen_string.replace("  ", " ")
        doxygen_string = doxygen_string.replace(" : ", ": ")
        if not doxygen_string.endswith("."):
            doxygen_string = f"{doxygen_string}."
        # then remove spaces from start and end
        doxygen_string = doxygen_string.strip() + "\n"
    # concatenate everything
    final_string = (
        parameters_string
        + returns_string
        + "Description\n-----------\n"
        + doxygen_string
    )
    string_to_return += f'{final_string}") {function_name};\n'
    return string_to_return


def adapt_default_value(def_value):
    """adapt default value"""
    def_value = def_value.replace(" ", "")
    def_value = def_value.replace('"', "'")
    def_value = def_value.replace("''", '""')
    if def_value == "0L":  # only in VrmlData
        def_value = "0"
    return def_value


def adapt_default_value_parmlist(param):
    """adapts default value to be used in swig parameter list"""
    def_value = param["defaultValue"]
    return def_value.replace(" ", "")


def filter_member_functions(
    class_name, class_public_methods, member_functions_to_exclude, class_is_abstract
):
    """This functions removes member function to exclude from
    the class methods list. Some of the members functions have to be removed
    because they can't be wrapped (usually, this results in a linkage error)

    The member function to exclude are defined by their names or their
    md5 signature. The latter allows selecting which method to exclude
    if there are several different signatures for one same method name.
    """
    # split wrapped methods into two lists
    constructors = []
    other_methods = []

    for public_method in class_public_methods:
        method_name = public_method["name"]
        public_method_signature = get_function_md5_signature(public_method)
        if (method_name in member_functions_to_exclude) or (
            "".join([method_name, "::", public_method_signature])
            in member_functions_to_exclude
        ):
            logging.info(
                "    explicitly excluded method %s::%s",
                class_name,
                public_method_signature,
            )
            continue
        if class_is_abstract and public_method["constructor"]:
            logging.info("    Constructor skipped for abstract class %s", class_name)
            continue
        if "<" in method_name:
            logging.info("    %s skipped because invalid name", method_name)
            continue
        # finally, we add this method to process in the correct list
        if public_method["constructor"]:
            constructors.append(public_method)
        else:
            other_methods.append(public_method)
    return constructors, other_methods


def adapt_type_for_hint(type_str):
    """convert c++ types to python types, for type hints
    Returns False if there's no possible type
    """
    if type_str == "0":  # huu ? in XCAFDoc, skip it
        logging.warning("    [TypeHint] Skipping unknown type, 0")
        return False
    if "void" in type_str or type_str in [""]:
        return "None"
    if " int" in type_str:  # const int, unsigned int etc.
        return "int"
    if "char *" in type_str or "CString" in type_str:
        return "str"
    if "bool" in type_str:
        return "bool"
    if "float" in type_str:
        return "float"
    if "integer *" in type_str:
        return "int"
    if "doublereal" in type_str:
        return "float"
    if type_str == "int":
        return "int"
    if type_str == "int *":
        return "int"
    if type_str == "double":
        return "float"
    if type_str == "const double":
        return "float"
    if type_str == "double *":
        return "float"
    if type_str == "opencascade::handle<TCollection_HAsciiString> &OutValue":
        return "str"
    if type_str == "std::istream &":
        return "str"
    if "std::ostream &" in type_str:
        return "str"
    if "_" not in type_str:  # TODO these are special cases, e.g. nested classes
        logging.warning("    [TypeHint] Skipping type %s, should contain _", type_str)
        return False  # returns a boolean to prevent type hint creation, the type will not be found
    # we only keep what is
    for tp in type_str.split(" "):
        if "_" in tp:
            type_str = tp.strip()
            break

    type_str = type_str.replace("Standard_Integer", "int")
    type_str = type_str.replace("Standard_Real", "float")
    type_str = type_str.replace("Standard_ShortReal", "float")
    type_str = type_str.replace("Standard_Boolean", "bool")
    type_str = type_str.replace("Standard_Character", "str")
    type_str = type_str.replace("Standard_Byte", "str")
    type_str = type_str.replace("Standard_Address", "None")
    type_str = type_str.replace("Standard_Size", "int")
    type_str = type_str.replace("Standard_Time", "float")

    # transform opencascade::handle<Message_Alert> to return Message_Alert
    if type_str.startswith("opencascade::handle<"):
        type_str = type_str[20:].split(">")[0].strip()
    if ":" in type_str:
        logging.warning("    [TypeHint] Skip type %s, because of trailing :", type_str)
        return False
    if "_" in type_str and not is_module(type_str.split("_")[0]):
        logging.warning(
            "    [TypeHint] Skipping unknown type %s, %s not in module list",
            type_str,
            type_str.split("_")[0],
        )
        return False
    if type_str.count("<") >= 1:  # at least one <, it's a template
        logging.warning(
            "    [TypeHint] Skipping type %s, seems to be a template", type_str
        )
        return False

    if type_str in ["TCollection_AsciiString", "TCollection_ExtendedString"]:
        type_str = "str"

    return type_str


def get_classname_from_handle(handle_name):
    """input : opencascade::handle<Something>
    returns: Something
    """
    if handle_name.startswith("opencascade::handle<"):
        return handle_name[20:].split(">")[0].strip()
    raise AssertionError(
        f"Should be an opencascade handle, you provided a {handle_name}"
    )


def adapt_type_hint_parameter_name(param_name_str):
    """some parameter names may conflict with python keyword,
    for instance with, False etc.
    Returns the modified name, and whether to take it into account"""
    if keyword.iskeyword(param_name_str):
        new_param_name = f"{param_name_str}_"
        success = True
    elif param_name_str in ["", "&"]:
        # some parameter names maybe missing
        # for example
        # Standard_EXPORT static int mma1her_(const integer *  ,
        #            doublereal * ,
        #            integer *   );
        logging.warning(
            "    [TypeHint] param name missing or '&', skip method type hint"
        )
        new_param_name = ""
        success = False
    else:  # default
        new_param_name = param_name_str
        success = True
    if "[" in new_param_name:
        param_name = new_param_name.split("[")[0]
        param_name = param_name.replace(")", "")
        if param_name == "":
            success = False
        else:
            new_param_name = f"{param_name}_list"
            success = True
    return new_param_name, success


def adapt_type_hint_default_value(default_value_str):
    """default values such as Standard_True etc. must be
    converted to correct python values
    """
    if default_value_str == "Standard_True":
        new_default_value_str = "True"
    elif default_value_str == "Standard_False":
        new_default_value_str = "False"
    elif "Precision::" in default_value_str:
        new_default_value_str = default_value_str.replace("Precision::", "Precision.")
    elif default_value_str == "NULL":
        new_default_value_str = "None"
    elif "opencascade::handle" in default_value_str:
        # case opencascade::handle<Message_ProgressIndicator>()
        # should be Message_ProgressIndicator()
        classname = get_classname_from_handle(default_value_str)
        if (
            classname == "Message_ProgressIndicator"
        ):  # no constructor defined, abstract class
            new_default_value_str = "'Message_ProgressIndicator()'"
        else:
            new_default_value_str = classname + default_value_str.split(">")[1]
    elif default_value_str.endswith(
        "f"
    ):  # some float values are defined as 0.0f or 0.1f
        str_removed_final_f = default_value_str[:-1]
        try:
            float(str_removed_final_f)
            is_float = True
        except ValueError:
            is_float = False
        new_default_value_str = str_removed_final_f if is_float else default_value_str
    elif default_value_str == "0L":
        new_default_value_str = "0"
    else:
        new_default_value_str = default_value_str
    success = True
    return new_default_value_str, success


def get_function_md5_signature(f):
    """
    Computes the MD5 hash of a function's signature provided in the input dictionary.

    The function's signature is normalized by removing all whitespace and converting
    all characters to lowercase before calculating the MD5 hash. This normalization
    process ensures that insignificant differences in formatting do not affect the
    hash value, providing a consistent identifier for function signatures across
    different releases of tools like cppheaderparser.

    Parameters:
    - f (dict): A dictionary representing the function, where the function's signature
      is expected to be associated with the 'debug' key. The signature is a string
      that typically includes the function's name, return type, and parameter types.

    Returns:
    - str: The MD5 hash of the normalized function signature as a hexadecimal string.

    Note:
    This function is used for excluding specific function signature from
    the wrapper.

    Example:
    >>> function_info = {"debug": "int add(int a, int b)"}
    >>> get_function_md5_signature(function_info)
    '9b74c9897bac770ffc029102a200c5de'
    """
    function_signature = f["debug"]
    # remove spaces, capital letters etc.
    # this id done to prevent the function signature to change
    # between two different releases of cppheaderparser
    # remove all white spaces
    function_signature = "".join(function_signature.split())
    # then lower
    function_signature = function_signature.lower()
    return hashlib.md5(bytes(function_signature, encoding="utf8")).hexdigest()


_OPERATOR_WRAPPERS = {
    "+": None,  # wrapped by SWIG, no need for a custom template
    "-": None,
    "*": None,
    "/": None,
    "==": TEMPLATE__EQ__,
    "!=": TEMPLATE__NE__,
    "+=": TEMPLATE__IADD__,
    "*=": TEMPLATE__IMUL__,
    "-=": TEMPLATE__ISUB__,
    "/=": TEMPLATE__ITRUEDIV__,
}

_PRIMITIVE_BY_REF_RETURNS = {
    "Standard_Integer &",
    "Standard_Real &",
    "Standard_Boolean &",
    "Standard_Integer&",
    "Standard_Real&",
    "Standard_Boolean&",
}


def _wrap_operator(f, function_name, parent_class_name):
    """If f is a wrappable C++ operator, return (swig_str, '') or ('', ''); None
    if function_name is not an operator at all."""
    if "operator" not in function_name:
        return None
    operand = function_name.split("operator ")[1].strip()
    if operand not in _OPERATOR_WRAPPERS:
        logging.info("    operand %s cannot be wrapped", operand)
        return "", ""
    template = _OPERATOR_WRAPPERS[operand]
    if template is None:
        return None  # SWIG handles +,-,*,/ natively
    param_type = f["parameters"][0]["type"].replace("&", "").strip()
    return (
        template.substitute({"TYPE": param_type, "CLASS": parent_class_name}),
        "",
    )


def _build_getter_setter_pair(f, function_name, return_type):
    """Generate a Get*/Set* pair when a method returns a primitive by-ref.
    Returns (swig_str, type_hint_str)."""
    logging.info("    Creating Get and Set methods for method %s", function_name)
    modified_return_type = return_type.split(" ")[0]
    getter_params_type_and_names = []
    getter_params_only_names = []
    getter_param_hints = ["self"]
    for param in f["parameters"]:
        adapted_type = adapt_param_type(param["type"])
        getter_params_type_and_names.append(f"{adapted_type} {param['name']}")
        getter_params_only_names.append(param["name"])
        getter_param_hints.append(
            f"{param['name']}: {adapt_type_for_hint(adapted_type)}"
        )

    setter_params_type_and_names = getter_params_type_and_names + [
        f"{modified_return_type} value"
    ]
    hint_output_type = adapt_type_for_hint(modified_return_type)
    setter_param_hints = getter_param_hints + [f"value: {hint_output_type}"]

    swig_str = TEMPLATE_GETTER_SETTER.substitute(
        {
            "Return_Type": modified_return_type,
            "Function_Name": function_name,
            "Getter_Parameters_Types_Names": ",".join(getter_params_type_and_names),
            "Getter_Parameters_Names": ",".join(getter_params_only_names),
            "Setter_Parameters_Types_Names": ",".join(setter_params_type_and_names),
        }
    )
    getter_hint_str = TEMPLATE_GETTER_PYI.substitute(
        {
            "Function_Name": function_name,
            "Getter_Parameters_Hints": ", ".join(getter_param_hints),
            "Hint_Output_Type": hint_output_type,
        }
    )
    setter_hint_str = TEMPLATE_SETTER_PYI.substitute(
        {
            "Function_Name": function_name,
            "Setter_Parameters_Hints": ", ".join(setter_param_hints),
        }
    )
    return swig_str, getter_hint_str + setter_hint_str


def _compute_return_type(f):
    """Derive the SWIG-ready return type, accounting for constructors,
    virtual, and static modifiers."""
    if f["constructor"]:
        return_type = ""
    else:
        return_type = adapt_return_type(f["rtnType"])
    if f["virtual"]:
        return_type = "virtual " + return_type
    if f["static"] and "static" not in return_type:
        return_type = "static " + return_type
    if f["static"] and f["parent"] is None:
        return_type = "static " + return_type
    return return_type


def _build_swig_parameter_list(f):
    """Build the SWIG parameter list for a function. Returns
    (parameters_types_and_names, parameters_definition_strs, has_handle_t_ref).
    has_handle_t_ref = True means this function should be skipped entirely."""
    parameters_types_and_names = []
    parameters_definition_strs = []
    for param in f["parameters"]:
        param_type = adapt_param_type(param["type"])
        if "Handle_T &" in param_type:
            # something like a template; would raise a compilation exception
            return None, None, True

        if "array_size" in param:
            # entries are [type, name] or [type, name, default_value]
            param_type_and_name = [
                param_type,
                f"{param['name']}[{param['array_size']}]",
            ]
        else:
            param_type_and_name = [param_type, param["name"]]

        param_string = adapt_param_type_and_name(" ".join(param_type_and_name))
        if "defaultValue" in param:
            def_value = adapt_default_value_parmlist(param)
            param_string += f" = {def_value}"
            param_type_and_name.append(def_value)

        parameters_types_and_names.append(param_type_and_name)
        parameters_definition_strs.append(param_string)
    return parameters_types_and_names, parameters_definition_strs, False


def _build_typehint(
    f,
    function_name,
    parameters_types_and_names,
    return_type,
    parent_class_name,
    overload,
):
    """Build the .pyi type-hint string for a function."""
    if "operator" in function_name:
        return ""

    str_typehint = ""
    # f"" wrap preserves a string even when adapt_type_for_hint returns False;
    # downstream str.join would otherwise blow up.
    types_returned = [f"{adapt_type_for_hint(return_type)}"]
    all_parameters_type_hint = ["self"]

    if overload:
        str_typehint += "    @overload\n"
    if f["constructor"]:
        str_typehint += "    def __init__("
    else:
        if f["static"]:
            str_typehint += "    @staticmethod\n"
            all_parameters_type_hint = []  # static methods don't take self
            if (
                parent_class_name is not None
                and "<" not in parent_class_name
                and function_name.isalnum()
            ):
                state.deprecated_static_functions.append(
                    (parent_class_name, function_name)
                )
        str_typehint += f"    def {function_name}("

    canceled = False
    for par in parameters_types_and_names:
        par_typ = adapt_type_for_hint(par[0])
        if not par_typ:
            canceled = True
            break
        ov = adapt_param_type_and_name(" ".join(par))
        if "OutValue" in ov:
            type_to_add = f"{adapt_type_for_hint(ov)}"
            if types_returned[0] == "None":
                types_returned[0] = type_to_add
            else:
                types_returned.append(type_to_add)
            continue
        # if there's a default value, the type becomes Optional[type] = value
        if len(par) == 3:
            hint_def_value, adapted = adapt_type_hint_default_value(par[2])
            par_typ = (
                f"Optional[{par_typ}] = {hint_def_value}"
                if adapted
                else f"Optional[{par_typ}]"
            )
        par_nam, success = adapt_type_hint_parameter_name(par[1])
        if not success:
            canceled = True
        if par_nam.endswith("_list"):
            par_typ = f"List[{par_typ}]"
        all_parameters_type_hint.append(f"{par_nam}: {par_typ}")

    if canceled:
        return ""

    str_typehint += ", ".join(all_parameters_type_hint)
    if len(types_returned) == 1:
        returned_type_hint = types_returned[0]
    elif len(types_returned) > 1:
        returned_type_hint = f"Tuple[{', '.join(types_returned)}]"
    else:
        raise AssertionError("Method should at least have one returned type.")
    str_typehint += f") -> {returned_type_hint}: ...\n"
    return str_typehint


def _should_skip_function(f, function_name):
    """Early-return cases where the function should not be wrapped at all."""
    if f["destructor"] or f["returns"] == "~":
        return True
    if "TYPENAME" in f["rtnType"]:  # something in NCollection
        return True
    if function_name in ("DEFINE_STANDARD_RTTIEXT", "Handle"):
        # Handle (something) func can not be handled by swig
        return True
    return False


def process_function(f, overload=False):
    """Generate SWIG bindings + a .pyi type hint for a single C++ function.

    Returns (swig_str, type_hint_str). Either may be empty when the function
    is intentionally skipped; swig_str may be False when the function would
    cause a SWIG compilation error.
    """
    function_signature_md5 = get_function_md5_signature(f)
    if f["template"]:
        return False, ""
    function_name = adapt_function_name(f["name"])

    if _should_skip_function(f, function_name):
        return "", ""

    if f["static"] and f["parent"] is not None:
        parent_class_name = f["parent"]["name"]
        if parent_class_name == state.current_module:
            parent_class_name = parent_class_name.lower()
    else:
        parent_class_name = None

    operator_result = _wrap_operator(f, function_name, parent_class_name)
    if operator_result is not None:
        return operator_result

    state.nb_total_methods += 1

    if function_name == "DumpJson":
        return TEMPLATE_DUMPJSON, TEMPLATE_DUMPJSON_PYI
    if function_name == "InitFromJson":
        return TEMPLATE_INITFROMJSON, TEMPLATE_INITFROMJSON_PYI

    # only wrap free functions that live in the current module's namespace
    function_namespace = f["namespace"]
    function_parent_class_name = f["parent"]["name"] if f["parent"] is not None else ""
    if (
        function_namespace[:-2] != state.current_module
        and function_parent_class_name == ""
    ):
        return "", ""

    # Build the docstring before _compute_return_type so the order of
    # check_dependency() calls (which append to state.python_module_dependency)
    # matches the legacy single-block implementation: parameter deps land
    # before return-type deps.
    docstring = process_function_docstring(f)
    return_type = _compute_return_type(f)
    if return_type in _PRIMITIVE_BY_REF_RETURNS:
        return _build_getter_setter_pair(f, function_name, return_type)

    # SWIG declaration prefix
    str_function = (
        f"\t\t/****** {function_parent_class_name}::{function_name} ******/\n"
        f"\t\t/****** md5 signature: {function_signature_md5} ******/\n"
        f'\t\t%feature("compactdefaultargs") {function_name};\n'
        + docstring
        + f"\t\t{return_type} {function_name}"
    )

    parameters_types_and_names, parameters_definition_strs, skip = (
        _build_swig_parameter_list(f)
    )
    if skip:
        return False, ""

    str_function += "(" + ", ".join(parameters_definition_strs) + ");\n"
    str_typehint = _build_typehint(
        f,
        function_name,
        parameters_types_and_names,
        return_type,
        parent_class_name,
        overload,
    )

    # collapse occasional duplicate "const const" produced by adapt_return_type
    str_function = str_function.replace("const const", "const") + "\n"
    return str_function, str_typehint


def process_free_functions(free_functions_list):
    """process a string for free functions"""
    str_free_functions = ""
    sorted_free_functions_list = sorted(free_functions_list, key=itemgetter("name"))
    for free_function in sorted_free_functions_list:
        # skip namespaced free functions, SWIG would emit them at file scope
        # and the C++ compiler would not find the symbol (occt-800 introduces
        # several functions in inner namespaces such as BVH::EncodeMortonCode)
        if free_function.get("namespace", ""):
            logging.info(
                "    Skipping namespaced free function %s%s",
                free_function.get("namespace", ""),
                free_function["name"],
            )
            continue
        ok_to_wrap = process_function(free_function)
        if ok_to_wrap:
            str_free_functions += ok_to_wrap
    return str_free_functions


def process_constructors(constructors_list):
    """this function process constructors.
    The constructors_list is a list of constructors
    """
    # first, assume that all methods are constructors
    for c in constructors_list:
        if not c["constructor"]:
            raise AssertionError("This method is not a constructor")
    # then we count the number of available constructors
    number_of_constructors = len(constructors_list)
    # if there are more than one constructor, then the __init__ method
    # has to be tagged as overloaded using the @overload decorator
    need_overload = False
    if number_of_constructors > 1:
        need_overload = True
        logging.info(
            "    [TypeHint] More than 1 constructor, @overload decorator needed."
        )
    # then process the constructors
    str_functions = ""
    type_hints = ""
    for constructor in constructors_list:
        ok_to_wrap, ok_hints = process_function(constructor, need_overload)
        if ok_to_wrap:
            str_functions += ok_to_wrap
            type_hints += ok_hints
    return str_functions, type_hints


def process_methods(methods_list):
    """process a list of public process_methods"""
    str_functions = ""
    type_hints = ""
    # sort methods according to the method name
    sorted_methods_list = sorted(methods_list, key=itemgetter("name"))
    # create a dict to map function names and the number of occurrences,
    # to determine whether or not use the @overload decorator
    for function in sorted_methods_list:
        # Skip free functions that live in a namespace different from
        # state.current_module: SWIG would emit them at file scope but the underlying
        # C symbol lives in the namespace, so the call would fail to link
        # (occt-800: e.g. BVH::EncodeMortonCode in BVH_RadixSorter.hxx).
        # When the namespace matches state.current_module, the .i file emits
        # `using namespace X;` so the unqualified call is fine
        # (e.g. namespace TopoDS::Wire/Edge/Face etc).
        if not function.get("parent"):
            ns = function.get("namespace", "").rstrip(":")
            if ns and ns != state.current_module:
                continue
        # don't process friend methods
        need_overload = False
        if not function["friend"]:
            # check if this method is many times in the function list
            names_count = 0
            function_name = function["name"]
            for f in sorted_methods_list:
                if f["name"] == function_name:
                    names_count += 1
            if names_count > 1:
                need_overload = True
            ok_to_wrap, ok_hints = process_function(function, need_overload)
            if ok_to_wrap:
                str_functions += ok_to_wrap
                type_hints += ok_hints
    return str_functions, type_hints


def must_ignore_default_destructor(klass):
    """Some classes, like for instance BRepFeat_MakeCylindricalHole
    has a protected destructor that must explicitly be ignored
    This is done by the directive
    %ignore Class::~Class() just before the wrapper definition
    """
    class_protected_methods = klass["methods"]["protected"]
    for protected_method in class_protected_methods:
        if protected_method["destructor"]:
            return True
    class_private_methods = klass["methods"]["private"]
    # finally, return True, the default constructor can be safely defined
    for private_method in class_private_methods:
        if private_method["destructor"]:
            return True
    return False


def class_can_have_default_constructor(klass):
    """Check if the class can have a defaultctor wrap
    or, if not, return False if the %nodefaultctor is required
    """
    if klass["name"] in NODEFAULTCTOR:
        return False
    # class must not be an abstract class
    if klass["abstract"]:
        logging.info("    Class %s is abstract, using %%nodefaultctor.", klass["name"])
        return False
    # check if the class has at least one public constructor defined
    has_one_public_constructor = False
    class_public_methods = klass["methods"]["public"]
    for public_method in class_public_methods:
        if public_method["constructor"] and public_method["name"] == klass["name"]:
            has_one_public_constructor = True
    # we have to ensure that no private or protected constructor is defined
    # we look for protected () constructor
    has_one_protected_constructor = False
    class_protected_methods = klass["methods"]["protected"]
    for protected_method in class_protected_methods:
        if (
            protected_method["constructor"]
            and protected_method["name"] == klass["name"]
        ):
            has_one_protected_constructor = True
    # check for private constructor
    has_one_private_constructor = False
    class_private_methods = klass["methods"]["private"]
    for private_method in class_private_methods:
        if private_method["constructor"] and private_method["name"] == klass["name"]:
            has_one_private_constructor = True
    if (has_one_private_constructor and not has_one_public_constructor) or (
        has_one_protected_constructor and not has_one_public_constructor
    ):
        return False
    # finally returns True, no need to use the %nodefaultctor
    return True


def build_inheritance_tree(classes_dict):
    """From the classes dict, return a list of classes
    with the class ordered from the most abstract to
    the more specialized. The more abstract will be
    processed first.
    """
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
        # the same. Anyway, if there are two ancestors (only a few cases),
        # one of the two ancestors come from another module.
        elif nbr_upper_classes == 1:
            upper_class_name = upper_classes[0]["class"]
            # if the upper class depends on another module
            # add it to the level 0 list.
            if upper_class_name.split("_")[0] != state.current_module:
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
            if class_1_module == upper_class_name_2 == state.current_module:
                logging.warning(
                    "This is a special case, where the 2 ancestors belong the same module. Class %s skipped.",
                    class_name,
                )
            if class_1_module == state.current_module:
                inheritance_dict[class_name] = upper_class_name_1
            elif class_2_module == state.current_module:
                inheritance_dict[class_name] = upper_class_name_2
            elif (
                upper_class_name_1 == upper_class_name_2
            ):  # the samemodule, but external, not the current one
                level_0_classes.append(class_name)
            inheritance_dict[class_name] = upper_class_name_1
        else:
            # prevent multiple inheritance: OCCT only has single
            # inheritance
            logging.warning(
                "Class %s has %s ancestors and is skipped.",
                class_name,
                nbr_upper_classes,
            )

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
    for class_name, _ in sorted(
        inheritance_depth.items(), key=lambda kv: (kv[1], kv[0])
    ):
        if class_name in classes_dict:  # TODO: should always be the case!
            class_list.append(classes_dict[class_name])
    # Then we build the list of all classes that inherit from Standard_Transient
    # at some point. These classes will need the %wrap_handle and %make_alias_macros
    for klass in class_list:
        upper_class = klass["inherits"]
        class_name = klass["name"]
        if upper_class:
            upper_class_name = klass["inherits"][0]["class"]
            if upper_class_name in state.all_standard_transients:
                # this class inherits from a Standard_Transient base class
                # so we add it to the state.all_standard_transients list:
                if klass not in state.all_standard_transients:
                    state.all_standard_transients.append(class_name)
    return class_list


def fix_type(type_str):
    """used in docstrings"""
    type_str = type_str.replace("Standard_Boolean &", "bool")
    type_str = type_str.replace("Standard_Boolean", "bool")
    type_str = type_str.replace("Standard_Real", "float")
    type_str = type_str.replace("Standard_ShortReal", "float")
    type_str = type_str.replace("Standard_Integer", "int")
    type_str = type_str.replace("Standard_CString", "str")
    type_str = type_str.replace("std::istream &", "str")
    type_str = type_str.replace("const", "")
    type_str = type_str.replace("& &", "&")
    return type_str


def process_harray1():
    """special wrapper for NCollection_HArray1
    Returns both the definition and the hint
    """
    wrapper_str = "/* harray1 classes */\n"
    pyi_str = "\n# harray1 classes\n"
    for HClassName in state.all_harray1:
        if HClassName.startswith(state.current_module + "_"):
            array1_type = state.all_harray1[HClassName]
            wrapper_str += HARRAY1_TEMPLATE.substitute(
                {"HClassName": f"{HClassName}", "Array1Type": f"{array1_type}"}
            )
            # type hint
            pyi_str += HARRAY1_TEMPLATE_PYI.substitute(
                {"HClassName": f"{HClassName}", "Array1Type": f"{array1_type}"}
            )
    return wrapper_str, pyi_str


def process_harray2():
    wrapper_str = "/* harray2 classes */"
    pyi_str = "# harray2 classes\n"
    for HClassName in state.all_harray2:
        if HClassName.startswith(state.current_module + "_"):
            array2_type = state.all_harray2[HClassName]
            wrapper_str += HARRAY2_TEMPLATE.substitute(
                {"HClassName": f"{HClassName}", "Array2Type": f"{array2_type}"}
            )
            # type hint
            pyi_str += HARRAY2_TEMPLATE_PYI.substitute(
                {"HClassName": f"{HClassName}", "Array2Type": f"{array2_type}"}
            )
    wrapper_str += "\n"
    return wrapper_str, pyi_str


def process_hsequence():
    wrapper_str = "/* hsequence classes */"
    pyi_str = "# hsequence classes\n"
    for HClassName in state.all_hsequence:
        if HClassName.startswith(state.current_module + "_"):
            sequence_type = state.all_hsequence[HClassName]
            wrapper_str += HSEQUENCE_TEMPLATE.substitute(
                {"HClassName": f"{HClassName}", "SequenceType": f"{sequence_type}"}
            )
            # type hint
            pyi_str += HSEQUENCE_TEMPLATE_PYI.substitute(
                {"HClassName": f"{HClassName}", "SequenceType": f"{sequence_type}"}
            )
    wrapper_str += "\n"
    pyi_str += "\n"
    return wrapper_str, pyi_str


def process_handles(classes_dict, exclude_classes):
    """Check whether a class has to be wrapped as a handle
    using the wrap_handle swig macro.
    This code is a bit redundant with process_classes, but this step
    appeared to be placed before typedef and templates definition
    """
    wrap_handle_str = "/* handles */\n"
    if exclude_classes == ["*"]:  # don't wrap any class
        return ""
    inheritance_tree_list = build_inheritance_tree(classes_dict)
    # occt-800: propagate "needs handle" through the inheritance chain. Many
    # 8.0 classes (e.g. XCAFDoc_ShapeTool) have no DEFINE_STANDARD_RTTI* of
    # their own but inherit from a Standard_Transient subclass via several
    # levels - their handle is still required for the typemaps.
    inherited_handle_classes = set()
    for klass in inheritance_tree_list:
        cn = klass["name"]
        for base in klass.get("inherits", []):
            base_name = base.get("class") if isinstance(base, dict) else base
            if base_name and (
                base_name in state.all_standard_handles
                or base_name in state.all_standard_transients
                or base_name in inherited_handle_classes
            ):
                inherited_handle_classes.add(cn)
                if cn not in state.all_standard_handles:
                    state.all_standard_handles.append(cn)
                break
    for klass in inheritance_tree_list:
        # class name
        class_name = klass["name"]
        if class_name in exclude_classes:
            # if the class has to be excluded,
            # we go on with the next one to be processed
            continue
        if check_has_related_handle(class_name) or class_name == "Standard_Transient":
            wrap_handle_str += f"%wrap_handle({class_name})\n"
    for HClassName in state.all_harray1:
        if HClassName.startswith(state.current_module + "_"):
            wrap_handle_str += f"%wrap_handle({HClassName})\n"
    for HClassName in state.all_harray2:
        if HClassName.startswith(state.current_module + "_"):
            wrap_handle_str += f"%wrap_handle({HClassName})\n"
    for HClassName in state.all_hsequence:
        if HClassName.startswith(state.current_module + "_"):
            wrap_handle_str += f"%wrap_handle({HClassName})\n"
    wrap_handle_str += "/* end handles declaration */\n\n"
    return wrap_handle_str


_PRIMITIVE_REF_TO_CTYPE = {
    "Standard_Real": "double",
    "double": "double",
    "Standard_Integer": "int",
    "int": "int",
    "Standard_Boolean": "bool",
    "bool": "bool",
}


def _synthesize_primitive_ref_getter_setters(class_name, other_methods):
    """occt-800: synthesize SetXxx/GetXxx pairs for parameterless methods that
    return a reference to a primitive (Standard_Real&, Standard_Integer&,
    Standard_Boolean&). OCCT 8.0 dropped the explicit setters, exposing only
    a `Type& Foo()` accessor that Python cannot assign through. Restores the
    API pythonocc has exposed since 2014 (commit 78c320c3)."""
    out = ""
    for m in other_methods:
        rtype = (m.get("rtnType") or "").strip()
        if "&" not in rtype or m.get("parameters"):
            continue
        if rtype.startswith("const") or " const " in rtype:
            continue
        base = rtype.replace("&", "").strip()
        cpp_type = _PRIMITIVE_REF_TO_CTYPE.get(base)
        if cpp_type is None:
            continue
        mname = m["name"]
        if mname == class_name or mname.startswith("~"):
            continue
        out += "\t\t%extend{\n"
        out += f"\t\t\t{cpp_type} Get{mname}() {{ return self->{mname}(); }}\n"
        out += (
            f"\t\t\tvoid Set{mname}({cpp_type} value) {{ self->{mname}() = value; }}\n"
        )
        out += "\t\t};\n"
    return out


def _class_specific_extensions(class_name):
    """Return (extra_def_str, extra_pyi_str) for classes that need ad-hoc SWIG
    extensions (TDF_Label name accessor, BRepTools serialization, math_*
    setters, TopoDS_Shape pickling, ...)."""
    extra_def, extra_pyi = "", ""
    if class_name in ("BRepTools", "BRepTools_ShapeSet"):
        extra_def += BREPTOOLS_WRITE_READ_FROM_STRING
        extra_pyi += BREPTOOLS_WRITE_READ_FROM_STRING_PYI
    if class_name == "TDF_Label":
        extra_def += '%feature("autodoc", "Returns the label name") GetLabelName;\n'
        extra_def += "\t\t%extend{\n"
        extra_def += "\t\t\tstd::string GetLabelName() {\n"
        extra_def += "\t\t\tstd::string txt;\n"
        extra_def += "\t\t\tHandle(TDataStd_Name) name;\n"
        extra_def += "\t\t\tif (!self->IsNull() && self->FindAttribute(TDataStd_Name::GetID(),name)) {\n"
        extra_def += "\t\t\tTCollection_ExtendedString extstr = name->Get();\n"
        extra_def += "\t\t\tchar* str = new char[extstr.LengthOfCString()+1];\n"
        extra_def += "\t\t\textstr.ToUTF8CString(str);\n"
        extra_def += "\t\t\ttxt = str;\n"
        extra_def += "\t\t\tdelete[] str;}\n"
        extra_def += "\t\t\treturn txt;}\n"
        extra_def += "\t\t};\n"
    # occt-800: StlAPI_Writer dropped SetASCIIMode and exposes the flag
    # through `bool& ASCIIMode()`. Add a Python-friendly setter shim.
    if class_name == "StlAPI_Writer":
        extra_def += "\t\t%extend{\n"
        extra_def += (
            "\t\t\tvoid SetASCIIMode(bool theMode) { self->ASCIIMode() = theMode; }\n"
        )
        extra_def += "\t\t};\n"
    # occt-800: math_Matrix / math_Vector still expose mutable Value() returning
    # a reference but Python cannot assign through it - add Get/SetValue shims.
    if class_name == "math_Matrix":
        extra_def += "\t\t%extend{\n"
        extra_def += "\t\t\tdouble GetValue(int row, int col) const { return self->Value(row, col); }\n"
        extra_def += "\t\t\tvoid SetValue(int row, int col, double v) { self->Value(row, col) = v; }\n"
        extra_def += "\t\t};\n"
    if class_name == "math_Vector":
        extra_def += "\t\t%extend{\n"
        extra_def += (
            "\t\t\tdouble GetValue(int idx) const { return self->Value(idx); }\n"
        )
        extra_def += (
            "\t\t\tvoid SetValue(int idx, double v) { self->Value(idx) = v; }\n"
        )
        extra_def += "\t\t};\n"
    return extra_def, extra_pyi


def _render_excluded_classes_proxies(exclude_classes):
    """Emit Python placeholders that raise ClassNotWrapped at use time, plus
    matching .pyi entries. Skips classes that NCollection.i actually wraps,
    since the placeholder would shadow them."""
    if not exclude_classes:
        return "", ""
    def_str = "/* python proxy for excluded classes */\n%pythoncode {\n"
    pyi_str = ""
    for excluded_class in exclude_classes:
        if excluded_class in NCOLLECTION_WRAPPED_CLASSES:
            continue
        def_str += f"@classnotwrapped\nclass {excluded_class}:\n\tpass\n\n"
        pyi_str += f"\n#classnotwrapped\nclass {excluded_class}: ...\n"
    def_str += "}\n/* end python proxy for excluded classes */\n"
    return def_str, pyi_str


def process_classes(classes_dict, exclude_classes, exclude_member_functions):
    """Generate the SWIG string for the class wrapper.
    Works from a dictionary of all classes, generated with CppHeaderParser.
    All classes but the ones in exclude_classes are wrapped.
    excludes_classes is a list with the class names to exclude_classes
    exclude_member_functions is a dict with classes names as keys and member
    function names as values
    """
    if exclude_classes == ["*"]:  # don't wrap any class
        # that is to say we add all classes to the list of exclude_member_functions
        new_exclude_classes = []
        for klass in classes_dict:
            class_name_to_exclude = klass.split("::")[0]
            class_name_to_exclude = class_name_to_exclude.split("<")[0]
            if class_name_to_exclude not in new_exclude_classes:
                new_exclude_classes.append(class_name_to_exclude)
        exclude_classes = new_exclude_classes.copy()

    class_def_str = ""  # the string for class definition
    class_pyi_str = ""  # the string for class type hints

    inheritance_tree_list = build_inheritance_tree(classes_dict)
    for klass in inheritance_tree_list:
        # class name
        class_name = klass["name"]
        # header
        stars = "".join(["*" for i in range(len(class_name) + 9)])
        class_def_str += f"/{stars}\n* class {class_name} *\n{stars}/\n"
        #
        if class_name in exclude_classes:
            # if the class has to be excluded,
            # we go on with the next one to be processed
            continue
        # occt-800: skip class templates without an explicit instantiation,
        # they cannot be wrapped by SWIG and produce invalid C++ casts
        if klass.get("template", ""):
            logging.info("    %s skipped because it is a class template", class_name)
            continue
        # ensure the class returned by CppHeader is defined in this module
        # otherwise we go on with the next class
        if not class_name.startswith(state.current_module):
            continue
        # we rename the class if the module is the same name
        # for instance TopoDS is both a module and a class
        # then we rename the class with lowercase
        logging.info("Class: %s", class_name)
        # the class type hint
        class_name_for_pyi = class_name.split("<")[0]

        if class_name == state.current_module:
            class_def_str += f"%rename({class_name.lower()}) {class_name};\n"
            class_name_for_pyi = class_name_for_pyi.lower()
        # then process the class itself
        if not class_can_have_default_constructor(klass):
            class_def_str += f"%nodefaultctor {class_name};\n"
        if must_ignore_default_destructor(klass):
            # check if the destructor is protected or private
            class_def_str += f"%ignore {class_name}::~{class_name}();\n"
        # then defines the wrapper
        class_def_str += f"class {class_name}"
        class_pyi_str += f"\nclass {class_name_for_pyi}"  # type hints
        # inheritance process
        inherits_from = klass["inherits"]
        if inherits_from:  # at least 1 ancestor
            inheritance_name = inherits_from[0]["class"]
            check_dependency(inheritance_name)
            inheritance_access = inherits_from[0]["access"]
            class_def_str += f" : {inheritance_access} {inheritance_name}"
            class_pyi_str += "("
            if "::" not in inheritance_name and "<" not in inheritance_name:
                class_pyi_str += f"{inheritance_name}"
            if len(inherits_from) == 2:  ## 2 ancestors
                inheritance_name_2 = inherits_from[1]["class"]
                check_dependency(inheritance_name_2)
                inheritance_access_2 = inherits_from[1]["access"]
                class_def_str += f", {inheritance_access_2} {inheritance_name_2}"
                class_pyi_str += f", {inheritance_name_2}"
            class_pyi_str += ")"
        class_pyi_str += ":\n"
        class_pyi_str += "    pass\n"  # TODO CHANGE
        class_def_str += " {\n"
        # process class typedefs here
        typedef_str = "\tpublic:\n"
        for typedef_value in list(klass["typedefs"]["public"]):
            if ")" in typedef_value:
                continue
            if typedef_value in TYPEDEF_TO_EXCLUDE:
                continue
            # CppHeaderParser exposes the typedef name list publicly via
            # klass["typedefs"]["public"] but only the underscore-prefixed
            # _public_typedefs dict carries the resolved type strings.
            typedef_type = klass._public_typedefs[typedef_value]  # noqa: SLF001
            typedef_str += f"typedef {typedef_type} {typedef_value};\n"
        class_def_str += typedef_str
        # process class enums here
        class_enums_list = klass["enums"]["public"]
        ###### Nested classes
        nested_classes = klass["nested_classes"]
        for n in nested_classes:
            nested_class_name = n["name"]
            # skip anon structs, for instance in AdvApp2Var_SysBase
            # or Graphic3d_TransformPers
            if "anon" in nested_class_name:
                continue
            logging.info("    Wrap nested class %s::%s", class_name, nested_class_name)
            class_def_str += "\t\tclass " + nested_class_name + " {};\n"
        ####### class enums
        if class_enums_list:
            class_enum_def, _ = process_enums(class_enums_list)
            class_def_str += class_enum_def
        # process class properties here
        properties_str = ""
        if state.current_module == "Graphic3d":
            for property_value in list(klass["properties"]["public"]):
                # TODO : cppheaderparser fails at finding private class properties
                if (
                    "NCollection_Vec2" in property_value["type"]
                ):  # issue in Aspect_Touch
                    logging.warning("Wrong type in class property : NCollection_Vec2")
                    continue
                if "using" in property_value["type"]:
                    logging.warning("Wrong type in class property : using")
                    continue
                if "return" in property_value["type"]:
                    logging.warning("Wrong type in class property : return")
                    continue
                if "std::map<" in property_value["type"]:
                    logging.warning("Wrong type in class property std::map")
                    continue
                if (
                    property_value["constant"]
                    or "virtual" in property_value["raw_type"]
                    or "allback" in property_value["raw_type"]
                ):
                    continue
                if "array_size" in property_value:
                    temp = f"\t\t{fix_type(property_value['type'])} {property_value['name']}[{property_value['array_size']}];\n"
                else:
                    temp = f"\t\t{fix_type(property_value['type'])} {property_value['name']};\n"
                properties_str += temp
        # @TODO : wrap class typedefs (for instance BRepGProp_MeshProps)
        class_def_str += properties_str
        # process methods here
        class_public_methods = klass["methods"]["public"]
        # remove, from this list, all functions that
        # are excluded
        try:
            members_functions_to_exclude = exclude_member_functions[class_name]
        except KeyError:
            members_functions_to_exclude = []
        # if ever the header defines DEFINE STANDARD ALLOC
        # then we wrap a copy constructor. Very convenient
        # to create python classes that inherit from OCCT ones!
        if class_name in ["TopoDS_Shape", "TopoDS_Vertex"]:
            class_def_str += '\t\t%feature("autodoc", "1");\n'
            class_def_str += f"\t\t{class_name}(const {class_name} arg0);\n"
        methods_to_process = filter_member_functions(
            class_name,
            class_public_methods,
            members_functions_to_exclude,
            klass["abstract"],
        )
        # amons all methods, we first process constructors, than the others
        constructors, other_methods = methods_to_process
        # first constructors
        constructors_definitions, constructors_type_hints = process_constructors(
            constructors
        )
        class_def_str += constructors_definitions
        class_pyi_str += constructors_type_hints
        # and the other methods
        other_method_definitions, other_method_type_hints = process_methods(
            other_methods
        )
        class_def_str += other_method_definitions
        class_pyi_str += other_method_type_hints
        class_def_str += _synthesize_primitive_ref_getter_setters(
            class_name, other_methods
        )

        # after that change, we remove the "pass" if it appears to be unnecessary
        # for example
        # class gp_Ax22d:
        #    pass
        #    def Location
        # should be
        # class gp_Ax22d:
        #    def Location
        class_pyi_str = class_pyi_str.replace("pass\n    @overload", "@overload")
        class_pyi_str = class_pyi_str.replace("pass\n    def", "def")
        class_pyi_str = class_pyi_str.replace(
            "pass\n    @staticmethod", "@staticmethod"
        )

        extra_def, extra_pyi = _class_specific_extensions(class_name)
        class_def_str += extra_def
        class_pyi_str += extra_pyi
        # then terminate the class definition
        class_def_str += "};\n\n"
        #
        # at last, check if there is a related handle
        # if yes, we integrate it into it's shadow class
        # TODO: check that the following is not restricted
        # to protected destructors !
        class_def_str += "\n"
        if check_has_related_handle(class_name) or class_name == "Standard_Transient":
            # Extend class by GetHandle method
            class_def_str += f"%make_alias({class_name})\n\n"
        if class_name == "Standard_Transient":
            # Extend the class with eq/neq/hash operators
            class_def_str += STANDARD_TRANSIENT_OPERATORS_TEMPLATE
        # hashing TopoDS_Shape . TODO: do it far all other classes that need to be hashed
        if class_name == "TopoDS_Shape":
            class_def_str += HASH_TOPODS_SHAPE_TEMPLATE
        if class_name == "ShapeAnalysis_FreeBounds":
            class_def_str += SHAPE_ANALYSIS_FREE_BOUNDS_TEMPLATE
            class_pyi_str += SHAPE_ANALYSIS_FREE_BOUNDS_TEMPLATE_PYI
        # if shape can be serialized as a Json, both get/set, implement pickling
        if (
            "DumpJson" in class_def_str
            and "InitFromJson" in class_def_str
            and class_name != "TopoDS_Shape"
        ):
            class_def_str += GETSTATE_TEMPLATE.substitute({"CLASSNAME": class_name})
            class_def_str += SETSTATE_TEMPLATE.substitute({"CLASSNAME": class_name})
        # We add pickling for TopoDS_Shapes
        if class_name == "TopoDS_Shape":
            class_def_str += TOPODS_SHAPE_PICKLE_TEMPLATE

        # for each class, overload the __repr__ method to avoid things like:
        # >>> print(box)
        # <OCC.TopoDS.TopoDS_Shape; proxy of <Swig Object of type 'TopoDS_Shape *' at 0x02
        # BCF770> >
        class_def_str += f"%extend {class_name} " + "{\n"
        class_def_str += "\t%" + "pythoncode {\n"
        class_def_str += "\t__repr__ = _dumps_object\n"
        # we process methods that are excluded from the wrapper
        # they used to be skipped, but it's better to explicitly
        # raise a MethodNotWrappedError exception
        for excluded_method_name in members_functions_to_exclude:
            if (
                excluded_method_name != "Handle"
                and "::" not in excluded_method_name
                and "Connect" not in excluded_method_name
            ):
                class_def_str += "\n\t@methodnotwrapped\n"
                class_def_str += f"\tdef {excluded_method_name}(self):\n\t\tpass\n"
        class_def_str += "\t}\n};\n\n"
        #
        # Special extents
        #
        if class_name == "Geom2d_Curve":  # see ticket #1381, numpy support
            class_def_str += "// numpy support for Geom2d_Curve\nCurve2dArrayEvalExtend(Geom2d_Curve)\n\n"
        if class_name == "Geom_Curve":  # see ticket #1381, numpy support
            class_def_str += (
                "// numpy support for Geom_Curve\nCurveArrayEvalExtend(Geom_Curve)\n\n"
            )
        if class_name == "Geom_Surface":  # see ticket #1381, numpy support
            class_def_str += "// numpy support for Geom_Surface\nSurfaceArrayEvalExtend(Geom_Surface)\n\n"
        # increment global number of classes
        state.nb_total_classes += 1
    excluded_def, excluded_pyi = _render_excluded_classes_proxies(exclude_classes)
    class_def_str += excluded_def
    class_pyi_str += excluded_pyi
    return class_def_str, class_pyi_str


def process_deprecated(list_of_classes_methods):
    """takes a list of tuples"""
    if not list_of_classes_methods:  # empty list
        return ""
    str_to_return = "/* deprecated methods */\n%pythoncode {\n"
    for class_name, method_name in list_of_classes_methods:
        str_to_return += "@deprecated\n"
        str_to_return += f"def {class_name}_{method_name}(*args):\n"
        str_to_return += f"\treturn {class_name}.{method_name}(*args)\n\n"
    str_to_return += "}\n"
    return str_to_return


def is_module(module_name):
    """Checks if the name passed as a parameter is
    (or is not) a module that aims at being wrapped.
    'Standard' should return True
    'inj' or whatever should return False
    """
    for mod in OCCT_MODULES:
        if mod[0] == module_name:
            return True
    return False


def parse_module(module_name):
    """A module is defined by a set of headers. For instance AIS,
    gp, BRepAlgoAPI etc. For each module, generate three or more
    SWIG files. This parser returns :
    module_enums, module_typedefs, module_classes
    """
    module_headers = glob.glob(f"{OCCT_INCLUDE_DIR}/{module_name}_*.hxx")
    module_headers += glob.glob(f"{OCCT_INCLUDE_DIR}/{module_name}.hxx")
    module_headers.sort()
    # check if there are some files
    if len(module_headers) == 0:
        logging.warning(
            "No file for module %s. Please check that the module name is part of occt.",
            module_name,
        )

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
    def __init__(
        self,
        module_name,
        additional_dependencies,
        exclude_classes,
        exclude_member_functions,
    ):
        # Reinit global variables
        state.current_module = module_name
        state.deprecated_static_functions = []
        # CURRENT_MODULE_PYI_STATIC_METHODS_ALIASES = ""
        # all modules depend, by default, upon Standard, NCollection and others
        if module_name not in ["Standard", "NCollection"]:
            state.python_module_dependency = ["Standard", "NCollection"]
            reset_header_depency()
        else:
            state.python_module_dependency = []

        logging.info("## Processing module %s", module_name)
        self._module_name = module_name
        self._module_docstring = get_module_docstring(module_name)
        # parse
        typedefs, enums, classes, free_functions = parse_module(module_name)
        # enums
        self._enums_str, self._enums_pyi_str = process_enums(enums)
        # handles
        self._wrap_handle_str = process_handles(classes, exclude_classes)
        # templates and typedefs
        (
            self._typedefs_str,
            self._typedefs_pyi_str,
            self._typedef_aliases_str,
        ) = process_typedefs(typedefs)
        # classes
        self._classes_str, self._classes_pyi_str = process_classes(
            classes, exclude_classes, exclude_member_functions
        )
        # special classes for NCollection_HArray1, NCollection_HArray2 and NCollection_HSequence
        harray1_def_str, harray1_pyi_str = process_harray1()
        self._classes_str += harray1_def_str
        self._classes_pyi_str += harray1_pyi_str

        harray2_def_str, harray2_pyi_str = process_harray2()
        self._classes_str += harray2_def_str
        self._classes_pyi_str += harray2_pyi_str

        hsequence_def_str, hsequence_pyi_str = process_hsequence()
        self._classes_str += hsequence_def_str
        self._classes_pyi_str += hsequence_pyi_str

        # free functions
        self._free_functions_str, self._free_functions_pyi_str = process_methods(
            free_functions
        )
        # other dependencies
        self._additional_dependencies = (
            additional_dependencies + state.header_dependency
        )

        # deprecated static functions after move to swig-4.1.1
        self._deprecated_swig_static_functions_str = process_deprecated(
            state.deprecated_static_functions
        )

    # Module-specific header injections (matched on module name).
    _MODULE_TEMPLATE_INJECTIONS = {
        "NCollection": NCOLLECTION_HEADER_TEMPLATE,
        "math": MATH_HEADER_TEMPLATE,
        "BVH": BVH_HEADER_TEMPLATE,
        "Prs3d": PRS3D_HEADER_TEMPLATE,
        "Graphic3d": GRAPHIC3D_DEFINE_HEADER,
        "BRepAlgoAPI": BREPALGOAPI_HEADER,
    }

    _COMMON_INCLUDES = (
        "CommonIncludes",
        "ExceptionCatcher",
        "FunctionTransformers",
        "EnumTemplates",
        "Operators",
        "OccHandle",
        "IOStream",
        "ArrayMacros",
    )

    _NUMPY_MODULES = {"Geom", "Geom2d", "Poly", "TColStd", "TColgp", "TShort"}

    def generate_SWIG_files(self):
        if GENERATE_SWIG_FILES:
            self._write_module_header_file()
            self._write_swig_interface_file()
        self._write_pyi_stub_file()

    def _write_module_header_file(self):
        """Generate <module>_module.hxx, the C++ aggregate header included by .i."""
        path = os.path.join(HEADERS_OUTPUT_PATH, f"{self._module_name}_module.hxx")
        module_headers = glob.glob(f"{OCCT_INCLUDE_DIR}/{self._module_name}_*.hxx")
        module_headers += glob.glob(f"{OCCT_INCLUDE_DIR}/{self._module_name}.hxx")
        module_headers.sort()
        with open(path, "w", encoding="utf8") as f:
            f.write(LICENSE_HEADER)
            f.write(f"#ifndef {self._module_name.upper()}_HXX\n")
            f.write(f"#define {self._module_name.upper()}_HXX\n\n\n")
            if self._module_name == "XCAFDoc":
                f.write("#include<TDF_Label.hxx>\n")
            for module_header in filter_header_list(
                module_headers, HXX_TO_EXCLUDE_FROM_BEING_INCLUDED
            ):
                basename = os.path.basename(module_header)
                if basename not in HXX_TO_EXCLUDE_FROM_BEING_INCLUDED:
                    f.write(f"#include<{basename}>\n")
            f.write(f"\n#endif // {self._module_name.upper()}_HXX\n")

    def _write_swig_interface_file(self):
        """Generate <module>.i, the SWIG interface file."""
        path = os.path.join(SWIG_OUTPUT_PATH, f"{self._module_name}.i")
        with open(path, "w", encoding="utf8") as f:
            self._write_swig_preamble(f)
            self._write_swig_cxx_includes(f)
            self._write_swig_python_imports(f)
            self._write_swig_module_specific_templates(f)
            self._write_swig_body(f)
            if self._module_name == "TopoDS":
                f.write(TOPODS_CLASS)

    def _write_swig_preamble(self, f):
        f.write(LICENSE_HEADER)
        # for instance: define GPDOCSTRING
        docstring_macro = f"{self._module_name.upper()}DOCSTRING"
        f.write(f"%define {docstring_macro}\n")
        f.write(f'"{self._module_docstring}"\n')
        f.write("%enddef\n")
        f.write(
            f'%module (package="OCC.Core", docstring={docstring_macro}) {self._module_name}\n\n'
        )
        f.write(WIN_PRAGMAS)
        for include in self._COMMON_INCLUDES:
            f.write(f"%include ../common/{include}.i\n")
        f.write("\n\n")

    def _write_swig_cxx_includes(self, f):
        """Write the %{ ... %} block: C++ includes, dependencies, namespace using."""
        f.write("%{\n")
        if self._module_name == "AdvApp2Var":  # windows compilation issues
            f.write("#if defined(_WIN32)\n#include <windows.h>\n#endif\n")
        # Issue with opencascade TopoDSToStep_Builder.hxx header
        if self._module_name in ["TopoDSToStep", "StepToTopoDS"]:
            f.write("#include<StepData_Factors.hxx>\n")
        if self._module_name == "ShapeProcess":
            f.write("#include <bitset>\nusing namespace std;\n")
        f.write(f"#include<{self._module_name}_module.hxx>\n")
        f.write("\n//Dependencies\n")
        for dep in state.python_module_dependency:
            f.write(f"#include<{dep}_module.hxx>\n")
        for add_dep in self._additional_dependencies:
            f.write(f"#include<{add_dep}_module.hxx>\n")
        # occt-800: BVH inner namespace also exposes free functions
        # (e.g. BVH::EncodeMortonCode) that get wrapped by SWIG
        if state.current_module in ["TopoDS", "BVH"]:
            f.write(f"using namespace {state.current_module};\n")
        f.write("%};\n")

    def _write_swig_python_imports(self, f):
        if self._module_name in self._NUMPY_MODULES:
            f.write(NUMPY_INIT_TEMPLATE)
        for dep in state.python_module_dependency:
            if is_module(dep):
                f.write(f"%import {dep}.i\n")
        f.write("\n%pythoncode {\n")
        f.write("from enum import IntEnum\n")
        f.write("from OCC.Core.Exception import *\n")
        f.write("};\n\n")

    def _write_swig_module_specific_templates(self, f):
        """Inject NCollection / math / BVH / Prs3d / Graphic3d / BRepAlgoAPI blocks."""
        template = self._MODULE_TEMPLATE_INJECTIONS.get(self._module_name)
        if template is not None:
            f.write(template)

    def _write_swig_body(self, f):
        f.write(self._enums_str)
        f.write(self._wrap_handle_str)
        f.write(self._typedefs_str)
        f.write(self._classes_str)
        f.write(self._typedef_aliases_str)
        f.write(self._deprecated_swig_static_functions_str)
        f.write(self._free_functions_str)

    def _write_pyi_stub_file(self):
        path = os.path.join(SWIG_OUTPUT_PATH, f"{self._module_name}.pyi")
        with open(path, "w", encoding="utf8") as f:
            f.write("from enum import IntEnum\n")
            f.write("from typing import overload, NewType, Optional, Tuple\n\n")
            for dep in state.python_module_dependency:
                if is_module(dep):
                    f.write(f"from OCC.Core.{dep} import *\n")
            # NewTypes for typedefs that are plain aliases (e.g. Prs3d_Presentation
            # is just an alias for Graphic3d_Structure):
            #   Prs3d_Presentation = NewType("Prs3d_Presentation", Graphic3d_Structure)
            f.write(self._typedefs_pyi_str)
            f.write(self._enums_pyi_str)
            f.write(self._classes_pyi_str)
            if self._module_name == "TopoDS":
                f.write(TOPODS_CLASS_PYI)


def scan_typedef_aliases():
    """occt-800: scan a curated subset of OCCT headers for
    `typedef NCollection_X<...> Y;` declarations and populate
    state.harray_typedef_rewrites. The rewrite is applied to parameter and return
    types so SWIG type tags stay consistent across modules - e.g.
    NCollection_IndexedDataMap<TopoDS_Shape, TopTools_ListOfShape, ...>
    is rewritten to TopTools_IndexedDataMapOfShapeListOfShape.

    Also pre-populate state.all_harray1 / state.all_harray2 / state.all_hsequence for every
    `typedef NCollection_HArrayN<X> Y;` so that process_handles emits a
    %wrap_handle and process_harrayN emits the fake-class definition that
    used to be supplied by the (removed) DEFINE_HARRAYN macro.

    We scan only a small set of "leaf" container modules. Scanning every
    header was tried but introduces too many cross-module typedef
    equivalences and causes SWIG to emit cast tables for C++ types
    unavailable in the importing module.
    """
    target_modules = (
        "TopTools_",
        "TColgp_",
        "TColStd_",
        "TColGeom_",
        "TColGeom2d_",
        "TColQuantity_",
        "TShort_",
        "Quantity_",
        "Poly_",
        "Storage_",
        "Interface_",
        "TDF_",
        "TDataStd_",
    )
    nc_pattern = re.compile(
        r"\btypedef\s+(NCollection_(?:H?Array1|H?Array2|H?Sequence|"
        r"DataMap|IndexedMap|IndexedDataMap|DoubleMap|Map|List|Vector|"
        r"DynamicArray|Buffer|FlatDataMap|OrderedDataMap|PackedMap)"
        r"<[^;]+?>)\s+([A-Za-z_]\w*)\s*;"
    )
    seen = {}
    # sorted: glob order depends on the filesystem, and both the registries
    # order and which alias wins for a given template depend on it
    for header_path in sorted(glob.glob(os.path.join(OCCT_INCLUDE_DIR, "*.hxx"))):
        basename = os.path.basename(header_path)
        if not any(basename.startswith(prefix) for prefix in target_modules):
            continue
        try:
            with open(header_path, "r", encoding="utf8", errors="replace") as f:
                content = f.read()
        except OSError:
            continue
        content = content.replace("Handle(", "opencascade::handle<").replace(
            "occ::handle", "opencascade::handle"
        )
        for match in nc_pattern.finditer(content):
            tpl = re.sub(r"\s+", "", match.group(1))
            if tpl.count("<") != tpl.count(">"):
                continue
            name = match.group(2)
            # Skip "local" typedefs that aren't a fully-qualified
            # `Module_Something` alias (e.g. `VectorOfPoint` in
            # BRepBuilderAPI_VertexInspector.hxx) - they aren't visible
            # outside their declaring header.
            if "_" not in name:
                continue
            if tpl not in seen:
                seen[tpl] = name
                seen[tpl.replace(",", ", ")] = name
            # Also register HArrayN typedefs into ALL_HARRAY{1,2} / state.all_hsequence
            # so process_handles / process_harray* generate the right wrapping.
            if tpl.startswith("NCollection_HArray1<"):
                inner = tpl[len("NCollection_HArray1<") : -1]
                if name not in state.all_harray1:
                    state.all_harray1[name] = f"NCollection_Array1<{inner}>"
            elif tpl.startswith("NCollection_HArray2<"):
                inner = tpl[len("NCollection_HArray2<") : -1]
                if name not in state.all_harray2:
                    state.all_harray2[name] = f"NCollection_Array2<{inner}>"
            elif tpl.startswith("NCollection_HSequence<"):
                inner = tpl[len("NCollection_HSequence<") : -1]
                if name not in state.all_hsequence:
                    state.all_hsequence[name] = f"NCollection_Sequence<{inner}>"
    state.harray_typedef_rewrites.extend(
        sorted(seen.items(), key=lambda kv: -len(kv[0]))
    )
    logging.info(
        "Built %d typedef rewrite mappings from OCCT headers",
        len(state.harray_typedef_rewrites),
    )


def write_enum_templates_file():
    """Generate common/EnumTemplates.i, shared by all modules. Must be called
    once every module has been processed, since state.all_byref_enums is
    filled in along the way."""
    path = os.path.join(COMMON_OUTPUT_PATH, "EnumTemplates.i")
    with open(path, "w", encoding="utf8") as f:
        for enum_name in state.all_byref_enums:
            f.write(BYREF_ENUM_TEMPLATE % enum_name)


def process_module(module_name, write_files=True):
    """Process a module, then write its files if write_files is True.

    Processing a module always updates the shared state (enums, handles,
    transients, ...) that the modules processed after it rely on."""
    for module in OCCT_MODULES:
        if module[0] == module_name:
            module_additionnal_dependencies = module[1]
            module_exclude_classes = module[2]
            if len(module) == 4:
                modules_exclude_member_functions = module[3]
            else:
                modules_exclude_member_functions = {}
            wrapper = ModuleWrapper(
                module_name,
                module_additionnal_dependencies,
                module_exclude_classes,
                modules_exclude_member_functions,
            )
            if write_files:
                wrapper.generate_SWIG_files()
            return
    raise NameError(f"Module {module_name} not defined")


def process_toolkit(toolkit_name, modules_to_write=None):
    """Generate wrappers for modules depending on a toolkit
    For instance : TKernel, TKMath etc.
    If modules_to_write is given, only these modules' files are written.
    """
    modules_list = TOOLKITS[toolkit_name]
    logging.info("Processing toolkit %s ===", toolkit_name)
    for module in sorted(modules_list):
        process_module(
            module, modules_to_write is None or module in modules_to_write
        )


def process_all_toolkits(modules_to_write=None):
    """Process every toolkit, in modules.yaml order. If modules_to_write is
    given, all modules are still processed, so that the shared state is the
    same as in a full run, but only these modules' files are written."""
    # don't sort the toolkits, otherwise dependencies maybe skipped
    for toolkit in TOOLKITS:
        process_toolkit(toolkit, modules_to_write)
    # modules declared in modules.yaml but not part of any toolkit are only
    # generated when explicitly requested
    toolkit_modules = {m for modules in TOOLKITS.values() for m in modules}
    for module in modules_to_write or ():
        if module not in toolkit_modules:
            process_module(module)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate pythonocc-core SWIG interface files and stubs."
    )
    parser.add_argument(
        "modules",
        nargs="*",
        help="OCCT modules to write (default: all toolkits). All modules are "
        "processed anyway, so that the output is the same as in a full run.",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="path to the configuration file (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    unknown_modules = [m for m in args.modules if not is_module(m)]
    if unknown_modules:
        parser.error(f"unknown module(s): {', '.join(unknown_modules)}")
    if args.config != DEFAULT_CONFIG_PATH:
        load_config(args.config)
    check_paths()
    setup_logging()
    # occt-800: pre-pass to map canonical NCollection template forms back
    # to the typedef aliases pythonocc actually wraps. Without this, modules
    # that take a parameter typed as `NCollection_X<...>` cannot be passed a
    # Python object of the corresponding TopTools_/TColgp_/... typedef.
    scan_typedef_aliases()
    logging.info(get_log_header())
    start_time = time.perf_counter()
    process_all_toolkits(set(args.modules) if args.modules else None)
    if GENERATE_SWIG_FILES:
        write_enum_templates_file()
    end_time = time.perf_counter()
    total_time = end_time - start_time
    # footer
    logging.info(get_log_footer(total_time))
    logging.info("Number of classes: %s", state.nb_total_classes)
    logging.info("Number of methods: %s", state.nb_total_methods)


if __name__ == "__main__":
    main()
