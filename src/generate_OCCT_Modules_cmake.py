from Modules import *

occt_toolkits = [
    TOOLKIT_Foundation,
    TOOLKIT_Modeling,
    TOOLKIT_Visualisation,
    TOOLKIT_DataExchange,
    TOOLKIT_OCAF,
]

occt_toolkit = occt_toolkits[0]
print("LIST(APPEND OCCT_TOOLKIT_MODEL\n")
packages = occt_toolkit.keys()
for package in packages:
    print(f"# {package}")
    for module in occt_toolkit[package]:
        print("\t%s" % module)

occt_toolkit = occt_toolkits[1]
packages = occt_toolkit.keys()
for package in packages:
    print(f"# {package}")
    for module in occt_toolkit[package]:
        print("\t%s" % module)
print(")\n")
print("LIST(APPEND OCCT_TOOLKIT_VISUALIZATION\n")
occt_toolkit = occt_toolkits[2]
packages = occt_toolkit.keys()
for package in packages:
    print(f"# {package}")
    for module in occt_toolkit[package]:
        print("\t%s" % module)
print(")\n")
print("LIST(APPEND OCCT_TOOLKIT_DATAEXCHANGE\n")
occt_toolkit = occt_toolkits[3]
packages = occt_toolkit.keys()
for package in packages:
    print(f"# {package}")
    for module in occt_toolkit[package]:
        print("\t%s" % module)
print(")\n")
print("LIST(APPEND OCCT_TOOLKIT_OCAF\n")
occt_toolkit = occt_toolkits[4]
packages = occt_toolkit.keys()
for package in packages:
    print(f"# {package}")
    for module in occt_toolkit[package]:
        print("\t%s" % module)
print(")\n")
