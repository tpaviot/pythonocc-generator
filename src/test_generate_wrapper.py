"""Unit tests for generate_wrapper helper functions.

Run with `pytest test_generate_wrapper.py` from the src/ directory (so the
relative `wrapper_generator.conf` next to generate_wrapper.py is picked up
during import).
"""

import os
import sys

from _exclusions import HXX_TO_EXCLUDE_FROM_CPPPARSER
from generate_wrapper import (
    OCCT_INCLUDE_DIR,
    adapt_function_name,
    adapt_param_type_and_name,
    adapt_return_type,
    check_dependency,
    filter_header_list,
    filter_typedefs,
    get_all_module_headers,
    get_type_for_ncollection_array,
    is_module,
)


def test_filter_header_list():
    if sys.platform != "win32":
        assert filter_header_list(
            ["something", "somethingWNT"], HXX_TO_EXCLUDE_FROM_CPPPARSER
        ) == ["something"]


def test_filter_header_list_platform_headers():
    headers = [
        os.path.join(OCCT_INCLUDE_DIR, name)
        for name in (
            "WNT_Window.hxx",
            "OSD_WNT.hxx",
            "Xw_Window_X11.hxx",
            "Image_XWD.hxx",
            "Cocoa_Window.hxx",
            "Storage_StreamUnknownTypeError.hxx",
            "gp_Pnt.hxx",
        )
    ]
    assert [os.path.basename(h) for h in filter_header_list(headers, [])] == [
        "Storage_StreamUnknownTypeError.hxx",
        "gp_Pnt.hxx",
    ]


def test_filter_header_list_ignores_include_dir_path():
    # only the basename must be checked, not the directory it lives in
    headers = ["/opt/occt-X11-build/include/gp_Pnt.hxx"]
    assert filter_header_list(headers, []) == headers


def test_get_all_module_headers():
    # 'Standard' should return some files (at lease 10)
    # this number depends on the OCCT version
    headers_list_1 = get_all_module_headers("Standard")
    assert len(list(headers_list_1)) > 10
    # an empty list
    headers_list_2 = list(get_all_module_headers("something_else"))
    assert not headers_list_2


def test_filter_typedefs():
    a_dict = {"1": "one", "{": "two", "NCollection_DelMapNode": "3"}
    assert filter_typedefs(a_dict) == {"1": "one"}


def test_filter_typedefs_excluded_callback():
    # TPCallBackFunc is both in TYPEDEF_TO_EXCLUDE and ends with "Func":
    # it must be removed once, not raise a KeyError
    a_dict = {
        "TPCallBackFunc": "void (*)(int)",
        "Foo_Function": "void",
        "Foo_fp": "void",
        "Foo_Ptr": "Foo_Bar *",
        "Foo_Alias": "Foo_Bar",
    }
    assert filter_typedefs(a_dict) == {"Foo_Alias": "Foo_Bar"}


def test_get_type_for_ncollection_array() -> None:
    assert (
        get_type_for_ncollection_array("NCollection_Array1<Standard_Real>")
        == "Standard_Real"
    )


def test_adapt_param_type_and_name():
    assert adapt_param_type_and_name("Standard_Real & Xp") == "Standard_Real &OutValue"
    assert (
        adapt_param_type_and_name("Standard_Integer & I")
        == "Standard_Integer &OutValue"
    )
    assert adapt_param_type_and_name("int & j") == "Standard_Integer &OutValue"
    assert adapt_param_type_and_name("double & x") == "Standard_Real &OutValue"


def test_check_dependency():
    assert check_dependency("Handle_Geom_Curve") == "Geom"
    assert check_dependency("Handle ( Geom2d_Curve)") == "Geom2d"
    assert check_dependency("opencascade::handle<TopoDS_TShape>") == "TopoDS"
    assert check_dependency("Standard_Integer") == "Standard"


def test_adapt_return_type():
    assert adapt_return_type("gp_Dir &") == "gp_Dir"


def test_adapt_function_name():
    assert adapt_function_name("operator*") == "operator *"


def test_adapt_default_value():
    pass  # assert adapt_default_value(": : MeshDim_3D") == "MeshDim_3D"


def test_is_module():
    assert is_module("Standard") is True
    assert is_module("something") is False
