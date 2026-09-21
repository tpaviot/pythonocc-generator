[![Build Status](https://dev.azure.com/tpaviot/pythonocc-generator/_apis/build/status/tpaviot.pythonocc-generator?branchName=master)](https://dev.azure.com/tpaviot/pythonocc-generator/_build/latest?definitionId=11)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/512945885d214293995c482e31efd0d7)](https://www.codacy.com/gh/tpaviot/pythonocc-generator/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=tpaviot/pythonocc-generator&amp;utm_campaign=Badge_Grade)

# pythonocc-generator

Generates the SWIG `.i` interface files and Python `.pyi` stubs that let
[pythonocc-core](https://github.com/tpaviot/pythonocc-core) expose the
[OpenCascade Technology](https://dev.opencascade.org) C++ API to Python.

The generator parses every OCCT public header (~14 000 files) with
[robotpy-cppheaderparser](https://github.com/robotpy/robotpy-cppheaderparser),
applies a curated set of source rewrites, and emits one `.i` + `.pyi` per OCCT
module under `pythonocc-core/src/SWIG_files/`. The exact translation rules from
C++ to Python are documented in [API_CONTRACT.md](API_CONTRACT.md).

## Status

- Targets **OpenCascade 8.0.0** (set via `wrapper_generator.conf`).
- Generates **3 915 classes** / **43 996 methods** across **318 modules** in ~10 s.

## Install

```sh
git clone https://github.com/tpaviot/pythonocc-generator.git
cd pythonocc-generator
pip install -r requirements.txt   # robotpy-cppheaderparser, pyyaml
```

You also need a local OCCT install (the generator only reads its headers, it
does not compile anything).

## Configure

Edit `src/wrapper_generator.conf`:

```ini
[OCCT]
# Where the OCCT public headers live
include_dir: /opt/occt800rc5/include/opencascade

[pythonocc-core]
version: 8.0.0
# Local checkout of pythonocc-core; .i / .pyi land under src/SWIG_files/
path: /home/you/Devel/pythonocc-core
```

## Generate

```sh
cd src
python generate_wrapper.py            # all toolkits
python generate_wrapper.py gp BRepPrimAPI   # write selected modules only (all are still processed)
python generate_wrapper.py --config other.conf   # another configuration file
```

Output goes to:

- `${pythonocc-core.path}/src/SWIG_files/wrapper/<Module>.i` — SWIG interface
- `${pythonocc-core.path}/src/SWIG_files/wrapper/<Module>.pyi` — Python type stubs
- `${pythonocc-core.path}/src/SWIG_files/headers/<Module>_module.hxx` — C++ aggregate header
- `${pythonocc-core.path}/src/SWIG_files/common/EnumTemplates.i` — by-ref enum typemaps
- `${pythonocc-core.path}/src/SWIG_files/wrapper/generator.log` — run log

## Project layout

| File | Role |
|---|---|
| `src/generate_wrapper.py` | Orchestrator. The pass that turns parsed headers into SWIG output. |
| `src/_swig_templates.py` | All SWIG / pyi template strings. Pure data. |
| `src/_exclusions.py` | Lists of headers / classes / typedefs to skip globally. |
| `src/_modules.py` | Loader for `modules.yaml`; exposes `TOOLKITS` and `OCCT_MODULES`. |
| `src/modules.yaml` | OCCT toolkit grouping + per-module exclusion config. |
| `src/wrapper_generator.conf` | Local paths + target OCCT version. |
| `src/test_generate_wrapper.py` | Pytest unit tests for the helper functions. |
| `src/generate_OCCT_Modules_cmake.py` | Emit the cmake `OCCT_TOOLKIT_*` lists from `modules.yaml`. |
| `src/check_modules_coverage.py` | Cross-check `modules.yaml` against an OCCT source tree. |

## Adding or excluding a module

`src/modules.yaml` is the single source of truth. To wrap a new OCCT module:

```yaml
modules:
  - name: MyModule
    additional_deps: [TopTools]              # extra %include in the .i
    exclude_classes: [MyModule_BadClass]     # skip these classes
    exclude_member_functions:                # skip these methods
      MyModule_FooClass: [BarMethod, BazMethod]
```

If a class or method causes a compilation failure downstream, add it to the
relevant exclusion list rather than patching the generator. The principle is to
stay as close as possible to the OCCT API — exclusions exist only to keep the
build green.

## Tests

```sh
cd src
pytest test_generate_wrapper.py
```

`test_generate_wrapper.py` covers the string-adapting helpers.
`test_golden.py` generates a few representative modules (`gp`, `TopoDS`,
`Geom`, `TColStd`, `XCAFDoc`, ...) and compares them byte-for-byte with the
snapshot stored in `src/golden/`. The snapshot depends on the OCCT headers it
was generated from (version in `src/golden/OCCT_VERSION`); with other headers
the test is skipped, unless `GOLDEN_REQUIRED=1` is set.

After an intended change of the output, refresh the snapshot and review the
diff before committing it:

```sh
UPDATE_GOLDEN=1 pytest test_golden.py
git diff --stat golden/
```

To test against another configuration file than `wrapper_generator.conf`
(e.g. other OCCT headers), set `PYTHONOCC_GENERATOR_CONFIG=/path/to/file.conf`.

## CI

Azure Pipelines (`azure-pipelines.yml`, jobs defined in `conda-build.yml`)
runs nightly and on `master` / `review/*` pushes, on Ubuntu 22.04 / 24.04
across Python 3.9 to 3.12. Each job installs the OCCT headers from conda-forge
(version set by `occt_version` in `conda-build.yml`, must match
`src/golden/OCCT_VERSION`), runs the unit and golden tests, then generates all
the modules.

## Further reading

- [API_CONTRACT.md](API_CONTRACT.md) — exact rules used to translate OCCT C++
  declarations to Python (operator handling, handles, out-parameters, enums,
  templates, NumPy interop, …).
- [Documentation.md](Documentation.md) — historical walk-through of the
  generation pipeline.

## License

GPL v3. See `LICENSE`.
