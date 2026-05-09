from pathlib import Path

import yaml


with open(Path(__file__).with_name("modules.yaml"), "r", encoding="utf8") as f:
    toolkits = yaml.safe_load(f)["toolkits"]


def _emit_packages(packages):
    for package, modules in packages.items():
        print(f"# {package}")
        for module in modules:
            print(f"\t{module}")


print("LIST(APPEND OCCT_TOOLKIT_MODEL\n")
_emit_packages(toolkits["Foundation"])
_emit_packages(toolkits["Modeling"])
print(")\n")
print("LIST(APPEND OCCT_TOOLKIT_VISUALIZATION\n")
_emit_packages(toolkits["Visualisation"])
print(")\n")
print("LIST(APPEND OCCT_TOOLKIT_DATAEXCHANGE\n")
_emit_packages(toolkits["DataExchange"])
print(")\n")
print("LIST(APPEND OCCT_TOOLKIT_OCAF\n")
_emit_packages(toolkits["OCAF"])
print(")\n")
