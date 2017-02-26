import warnings
import json
warnings.filterwarnings("ignore")
from dejavu import Dejavu

with open("dejavu.cnf.SAMPLE") as f:
    config = json.load(f)

if __name__ == '__main__':

	# create a Dejavu instance
	djv = Dejavu(config)
	# Fingerprint all the mp3's in the directory we give it
	djv.fingerprint_directory("mp3", [".mp3"])