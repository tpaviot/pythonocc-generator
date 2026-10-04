#!/bin/bash
# Usage: check_stubs.sh <wrapper_dir>
# Lay out the .pyi files of <wrapper_dir> (pythonocc-core/src/SWIG_files/wrapper)
# as an OCC.Core package and type check mypy_classic_occ_bottle.py against it.
set -e
WRAPPER_DIR=$(realpath "$1")
CHECK_DIR=$(dirname "$(realpath "$0")")
STUBS=$(mktemp -d)
trap 'rm -rf "$STUBS"' EXIT
mkdir -p "$STUBS/OCC/Core"
touch "$STUBS/OCC/__init__.pyi" "$STUBS/OCC/Core/__init__.pyi"
cp "$WRAPPER_DIR"/*.pyi "$STUBS/OCC/Core/"
cd "$CHECK_DIR"
MYPYPATH="$STUBS" python -m mypy --no-incremental --config-file mypy.ini mypy_classic_occ_bottle.py
