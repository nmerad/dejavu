import warnings
import json
import sys
warnings.filterwarnings("ignore")
from dejavu import Dejavu
from dejavu.recognize import FileRecognizer, MicrophoneRecognizer

# load config from a JSON file (or anything outputting a python dictionary)
with open("dejavu.cnf.SAMPLE") as f:
    config = json.load(f)

if __name__ == '__main__':

	args = sys.argv
	args.remove(args[0])

	if len(args) == 0:
		print "No song specified as argument"
	else:
		# create a Dejavu instance
		djv = Dejavu(config)

		recognizations = []
		for arg in args: 
			print "Start recognization from file %s ...\n" % arg
			recognization = djv.recognize(FileRecognizer, arg)
			print "From %s we recognized %s\n" % (arg, recognization[0])
			recognizations.append(recognization[1])

		if len(recognizations) > 0:
			recommandation = recognization[1]
			for rec in recognizations:
				if rec[Dejavu.CONFIDENCE] > recommandation[Dejavu.CONFIDENCE]:
					recommandation = rec

			print "Following the analysis of previous songs, we recommand %s" % recommandation