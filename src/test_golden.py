"""Golden test: compare the generator output with a versioned snapshot.

A few representative modules are generated into a temporary directory and
compared byte-for-byte with golden/SWIG_files/. The snapshot depends on the
OCCT headers it was generated from, whose version is stored in
golden/OCCT_VERSION:
- if the headers found through the configuration have another version, the
  test is skipped, unless GOLDEN_REQUIRED=1 is set (as in the CI), in which
  case it fails;
- after an intended change of the output, refresh the snapshot with
  `UPDATE_GOLDEN=1 pytest test_golden.py` and review the diff before
  committing it.

The generator runs in a subprocess: its state is global to the process.
"""

import ast
import difflib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from generate_wrapper import OCCT_INCLUDE_DIR

SRC_DIR = Path(__file__).parent
GOLDEN_DIR = SRC_DIR / "golden"
GOLDEN_SWIG_FILES = GOLDEN_DIR / "SWIG_files"
GOLDEN_VERSION_FILE = GOLDEN_DIR / "OCCT_VERSION"

# Chosen to cover the special cases of the generator: handles and
# Standard_Transient (Standard), templates and HArray/HSequence (NCollection,
# TColStd, TColgp, TopTools, Storage), operators (gp), class-specific
# templates and pickling (TopoDS), numpy extensions (Geom), by-ref enums from
# another module (Geom2dGcc), primitive-ref getters/setters (math), handles
# inherited through several levels (XCAFDoc) and typical APIs (BRepPrimAPI,
# BRepAlgoAPI).
GOLDEN_MODULES = [
    "Standard",
    "NCollection",
    "TColStd",
    "TColgp",
    "TopTools",
    "Storage",
    "gp",
    "TopoDS",
    "Geom",
    "Geom2dGcc",
    "math",
    "XCAFDoc",
    "BRepPrimAPI",
    "BRepAlgoAPI",
]


def get_occt_version(include_dir):
    """Return OCC_VERSION_COMPLETE from Standard_Version.hxx, None if missing."""
    version_header = Path(include_dir) / "Standard_Version.hxx"
    if not version_header.is_file():
        return None
    for line in version_header.read_text(encoding="utf8").splitlines():
        if line.startswith("#define OCC_VERSION_COMPLETE"):
            return line.split('"')[1].strip()
    return None


def generate(output_dir):
    """Run the generator on GOLDEN_MODULES, return the SWIG_files directory."""
    config_path = output_dir / "golden.conf"
    config_path.write_text(
        "[OCCT]\n"
        f"include_dir: {OCCT_INCLUDE_DIR}\n"
        "[pythonocc-core]\n"
        "version: golden\n"
        f"path: {output_dir}\n",
        encoding="utf8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(SRC_DIR / "generate_wrapper.py"),
            "--config",
            str(config_path),
            *GOLDEN_MODULES,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    swig_files = output_dir / "src" / "SWIG_files"
    # the log holds timestamps and absolute paths
    (swig_files / "wrapper" / "generator.log").unlink()
    return swig_files


def list_files(directory):
    return sorted(
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file()
    )


def test_golden(tmp_path):
    occt_version = get_occt_version(OCCT_INCLUDE_DIR)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        assert occt_version, f"no OCCT headers found in {OCCT_INCLUDE_DIR}"
        swig_files = generate(tmp_path)
        shutil.rmtree(GOLDEN_SWIG_FILES, ignore_errors=True)
        shutil.copytree(swig_files, GOLDEN_SWIG_FILES)
        GOLDEN_VERSION_FILE.write_text(f"{occt_version}\n", encoding="utf8")
        pytest.skip(f"golden files updated from OCCT {occt_version} headers")

    golden_version = GOLDEN_VERSION_FILE.read_text(encoding="utf8").strip()
    if occt_version != golden_version:
        message = (
            f"golden files were generated from OCCT {golden_version} headers, "
            f"found {occt_version} in {OCCT_INCLUDE_DIR}"
        )
        if os.environ.get("GOLDEN_REQUIRED") == "1":
            pytest.fail(message)
        pytest.skip(message)

    swig_files = generate(tmp_path)
    expected_files = list_files(GOLDEN_SWIG_FILES)
    generated_files = list_files(swig_files)
    assert generated_files == expected_files

    differences = []
    for name in expected_files:
        expected = (GOLDEN_SWIG_FILES / name).read_text(encoding="utf8")
        generated = (swig_files / name).read_text(encoding="utf8")
        if generated != expected:
            diff = difflib.unified_diff(
                expected.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                f"golden/{name}",
                f"generated/{name}",
            )
            differences.append("".join(list(diff)[:40]))
    assert not differences, (
        f"{len(differences)} file(s) differ from the golden snapshot "
        "(UPDATE_GOLDEN=1 to refresh it if the change is intended):\n"
        + "\n".join(differences)
    )


@pytest.mark.parametrize(
    "stub", sorted(GOLDEN_SWIG_FILES.glob("wrapper/*.pyi")), ids=lambda p: p.name
)
def test_golden_stubs_are_valid_python(stub):
    # a single syntax error in a .pyi stops mypy for all pythonocc-core users
    ast.parse(stub.read_text(encoding="utf8"), filename=str(stub))
