"""Load OCCT toolkit / module configuration from modules.yaml.

Exposes:
    TOOLKITS       — dict[package_name -> list[module_name]], flattened
                     across all toolkits (Foundation, Modeling, ...). Order
                     is preserved from the YAML (it matters for dependency
                     resolution).
    OCCT_MODULES   — list of (name, additional_deps, exclude_classes) or
                     (name, additional_deps, exclude_classes,
                      exclude_member_functions) tuples. Same shape as the
                     legacy Modules.py constant; same order.
    KEEP_CONSTRUCTOR_ARGS — set of class names whose python proxy keeps a
                     reference to the constructor arguments, for classes
                     that store a non-owning pointer to one of them.
    MODULE_OPTIONS — dict[module_name -> dict] of the per module options
                     that do not fit in the OCCT_MODULES tuples, e.g.
                     flatten_nested_classes, include_classes.
"""

from pathlib import Path

import yaml


_YAML_PATH = Path(__file__).with_name("modules.yaml")


def _load():
    with open(_YAML_PATH, "r", encoding="utf8") as f:
        data = yaml.safe_load(f)

    toolkits = {}
    for toolkit in data["toolkits"].values():
        toolkits.update(toolkit)

    modules = []
    keep_constructor_args = set()
    module_options = {}
    for entry in data["modules"]:
        name = entry["name"]
        deps = entry.get("additional_deps", []) or []
        exclude_classes = entry.get("exclude_classes", []) or []
        exclude_member = entry.get("exclude_member_functions")
        keep_constructor_args.update(entry.get("keep_constructor_args", []) or [])
        module_options[name] = {
            "flatten_nested_classes": bool(entry.get("flatten_nested_classes", False)),
            "include_classes": list(entry.get("include_classes", []) or []),
        }
        if exclude_member:
            modules.append((name, deps, exclude_classes, exclude_member))
        else:
            modules.append((name, deps, exclude_classes))
    return toolkits, modules, keep_constructor_args, module_options


TOOLKITS, OCCT_MODULES, KEEP_CONSTRUCTOR_ARGS, MODULE_OPTIONS = _load()
