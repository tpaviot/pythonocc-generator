import os
import glob

OCCT_DIRECTORY = "/home/thomas/Téléchargements/OCCT-7_8_1_ii/" 
OCCT_SRC_PATH = os.path.join(OCCT_DIRECTORY, "src")

# load all TK folders
all_toolkits = glob.glob(OCCT_SRC_PATH, "TK*")
print(all_toolkits)