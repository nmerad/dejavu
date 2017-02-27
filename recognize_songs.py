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
		ids = []
		for arg in args: 
			print "Start recognization from file %s ...\n" % arg
			recognization = djv.recognize(FileRecognizer, arg)
			print "From %s we recognized :" % arg
			print json.dumps(recognization[0], sort_keys=True, indent=4)
			recognizations.append(recognization[1])
			ids.append(recognization[0][Dejavu.SONG_ID])

		print ids
		if len(recognizations) > 0:
			recommandation = None
			maxConfidence = -1
			for rec in recognizations:
				if (rec[Dejavu.CONFIDENCE] > maxConfidence) and (rec[Dejavu.SONG_ID] not in ids):
					recommandation = rec
					maxConfidence = rec[Dejavu.CONFIDENCE]

			print "\nFollowing the analysis of previous songs, we recommand :"
			print json.dumps(recommandation, sort_keys=True, indent=4)