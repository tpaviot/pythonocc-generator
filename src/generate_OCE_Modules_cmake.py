from Modules import *

oce_toolkits = [TOOLKIT_Foundation,
                TOOLKIT_Modeling,
                TOOLKIT_Visualisation,
                TOOLKIT_DataExchange,
                TOOLKIT_OCAF]

oce_toolkit = oce_toolkits[0]
print("LIST(APPEND OCE_TOOLKIT_MODEL\n")
packages = oce_toolkit.keys()
for package in packages:
    print("# %s" % package)
    for module in oce_toolkit[package]:
        print("\t%s" % module)

oce_toolkit = oce_toolkits[1]
packages = oce_toolkit.keys()
for package in packages:
    print("# %s" % package)
    for module in oce_toolkit[package]:
        print("\t%s" % module)
print(")\n")
print("LIST(APPEND OCE_TOOLKIT_VISUALIZATION\n")
oce_toolkit = oce_toolkits[2]
packages = oce_toolkit.keys()
for package in packages:
    print("# %s" % package)
    for module in oce_toolkit[package]:
        print("\t%s" % module)
print(")\n")
print("LIST(APPEND OCE_TOOLKIT_DATAEXCHANGE\n")
oce_toolkit = oce_toolkits[3]
packages = oce_toolkit.keys()
for package in packages:
    print("# %s" % package)
    for module in oce_toolkit[package]:
        print("\t%s" % module)
print(")\n")
print("LIST(APPEND OCE_TOOLKIT_OCAF\n")
oce_toolkit = oce_toolkits[4]
packages = oce_toolkit.keys()
for package in packages:
    print("# %s" % package)
    for module in oce_toolkit[package]:
        print("\t%s" % module)
print(")\n")
