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
    for entry in data["modules"]:
        name = entry["name"]
        deps = entry.get("additional_deps", []) or []
        exclude_classes = entry.get("exclude_classes", []) or []
        exclude_member = entry.get("exclude_member_functions")
        if exclude_member:
            modules.append((name, deps, exclude_classes, exclude_member))
        else:
            modules.append((name, deps, exclude_classes))
    return toolkits, modules


TOOLKITS, OCCT_MODULES = _load()
