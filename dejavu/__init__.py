from __future__ import division
from tinytag import TinyTag
from dejavu.database import get_database, Database
import dejavu.decoder as decoder
import fingerprint
import multiprocessing
import os
import traceback
import sys
import operator

class Dejavu(object):

    SONG_ID = "song_id"
    SONG_NAME = 'song_name'
    SONG_AUTHOR = 'song_author'
    SONG_GENRE = 'song_genre'
    CONFIDENCE = 'confidence'
    MATCH_TIME = 'match_time'
    OFFSET = 'offset'
    OFFSET_SECS = 'offset_seconds'

    def __init__(self, config):
        super(Dejavu, self).__init__()

        self.config = config

        # initialize db
        db_cls = get_database(config.get("database_type", None))

        self.db = db_cls(**config.get("database", {}))
        self.db.setup()

        # if we should limit seconds fingerprinted,
        # None|-1 means use entire track
        self.limit = self.config.get("fingerprint_limit", None)
        if self.limit == -1:  # for JSON compatibility
            self.limit = None
        self.get_fingerprinted_songs()

    def get_fingerprinted_songs(self):
        # get songs previously indexed
        self.songs = self.db.get_songs()
        self.songhashes_set = set()  # to know which ones we've computed before
        for song in self.songs:
            song_hash = song[Database.FIELD_FILE_SHA1]
            self.songhashes_set.add(song_hash)

    def get_song_metadata(self, filename):
        return TinyTag.get(filename)

    def fingerprint_directory(self, path, extensions, nprocesses=None):
        # Try to use the maximum amount of processes if not given.
        try:
            nprocesses = nprocesses or multiprocessing.cpu_count()
        except NotImplementedError:
            nprocesses = 1
        else:
            nprocesses = 1 if nprocesses <= 0 else nprocesses

        pool = multiprocessing.Pool(nprocesses)

        filenames_to_fingerprint = []
        for filename, _ in decoder.find_files(path, extensions):

            # don't refingerprint already fingerprinted files
            if decoder.unique_hash(filename) in self.songhashes_set:
                print "%s already fingerprinted, continuing..." % filename
                continue

            filenames_to_fingerprint.append(filename)

        # Prepare _fingerprint_worker input
        worker_input = zip(filenames_to_fingerprint,
                           [self.limit] * len(filenames_to_fingerprint))

        # Send off our tasks
        iterator = pool.imap_unordered(_fingerprint_worker,
                                       worker_input)

        # Loop till we have all of them
        while True:
            try:
                filename, song_name, hashes, file_hash = iterator.next()
            except multiprocessing.TimeoutError:
                continue
            except StopIteration:
                break
            except:
                print("Failed fingerprinting")
                # Print traceback because we can't reraise it here
                traceback.print_exc(file=sys.stdout)
            else:
                tags = self.get_song_metadata(filename)
                title = tags.title or filename
                artist = tags.artist or ""
                genre = tags.genre or "" 
                sid = self.db.insert_song(title, artist, genre, file_hash)

                self.db.insert_hashes(sid, hashes)
                self.db.set_song_fingerprinted(sid)
                self.get_fingerprinted_songs()

        pool.close()
        pool.join()

    def fingerprint_file(self, filepath, song_name=None):
        songname = decoder.path_to_songname(filepath)
        song_hash = decoder.unique_hash(filepath)
        song_name = song_name or songname
        # don't refingerprint already fingerprinted files
        if song_hash in self.songhashes_set:
            print "%s already fingerprinted, continuing..." % song_name
        else:
            filename, song_name, hashes, file_hash = _fingerprint_worker(
                filepath,
                self.limit,
                song_name=song_name
            )
            tags = self.get_song_metadata(filename)
            title = tags.title or filename
            artist = tags.artist or ""
            genre = tags.genre or "" 
            sid = self.db.insert_song(title, artist, genre, file_hash)

            self.db.insert_hashes(sid, hashes)
            self.db.set_song_fingerprinted(sid)
            self.get_fingerprinted_songs()

    def find_matches(self, samples, Fs=fingerprint.DEFAULT_FS):
        hashes = fingerprint.fingerprint(samples, Fs=Fs)
        return self.db.return_matches(hashes)

    def align_matches(self, matches):
        """
            Finds hash matches that align in time with other matches and finds
            consensus about which hashes are "true" signal from the audio.

            Returns a dictionary with match information.
        """
        # align by diffs
        diff_counter = {}
        largest = 0
        largest_count = 0
        songs_matches_counter = {}
        nb_matches = 0
        for tup in matches:
            nb_matches += 1
            sid, diff = tup
            if diff not in diff_counter:
                diff_counter[diff] = {}
            if sid not in diff_counter[diff]:
                diff_counter[diff][sid] = 0
            if sid not in songs_matches_counter:
                songs_matches_counter[sid] = 0
            diff_counter[diff][sid] += 1
            songs_matches_counter[sid] += 1

            if diff_counter[diff][sid] > largest_count:
                largest = diff
                largest_count = diff_counter[diff][sid]

        # Sort songs by matching rate desc
        order = sorted(songs_matches_counter, key=songs_matches_counter.get, reverse=True)
        recognized_song_id = order[0]
        recommandation_id = order[1]
        recognized_song_counter = songs_matches_counter[recognized_song_id]
        recommandation_counter = songs_matches_counter[recommandation_id]

        # return match info
        nseconds = round(float(largest) / fingerprint.DEFAULT_FS *
                         fingerprint.DEFAULT_WINDOW_SIZE *
                         fingerprint.DEFAULT_OVERLAP_RATIO, 5)

        # extract idenfication
        song = self.db.get_song_by_id(recognized_song_id)
        recommandation = self.db.get_song_by_id(recommandation_id)
        if song:
            # TODO: Clarify what `get_song_by_id` should return.
            song = {
            Dejavu.SONG_ID : recognized_song_id,
            Dejavu.SONG_NAME : song.get(Dejavu.SONG_NAME, None),
            Dejavu.SONG_AUTHOR : song.get(Dejavu.SONG_AUTHOR, None),
            Dejavu.SONG_GENRE : song.get(Dejavu.SONG_GENRE, None),
            Dejavu.CONFIDENCE : recognized_song_counter / nb_matches,}
        else:
            return None

        if recommandation:
            # TODO: Clarify what `get_song_by_id` should return.
            recommandation = {
            Dejavu.SONG_ID : recommandation_id,
            Dejavu.SONG_NAME : recommandation.get(Dejavu.SONG_NAME, None),
            Dejavu.SONG_AUTHOR : recommandation.get(Dejavu.SONG_AUTHOR, None),
            Dejavu.SONG_GENRE : recommandation.get(Dejavu.SONG_GENRE, None),
            Dejavu.CONFIDENCE : recommandation_counter / nb_matches,}

        return [song, recommandation]

    def recognize(self, recognizer, *options, **kwoptions):
        r = recognizer(self)
        return r.recognize(*options, **kwoptions)


def _fingerprint_worker(filename, limit=None, song_name=None):
    # Pool.imap sends arguments as tuples so we have to unpack
    # them ourself.
    try:
        filename, limit = filename
    except ValueError:
        pass

    songname, extension = os.path.splitext(os.path.basename(filename))
    song_name = song_name or songname
    channels, Fs, file_hash = decoder.read(filename, limit)
    result = set()
    channel_amount = len(channels)

    for channeln, channel in enumerate(channels):
        # TODO: Remove prints or change them into optional logging.
        print("Fingerprinting channel %d/%d for %s" % (channeln + 1,
                                                       channel_amount,
                                                       filename))
        hashes = fingerprint.fingerprint(channel, Fs=Fs)
        print("Finished channel %d/%d for %s" % (channeln + 1, channel_amount,
                                                 filename))
        result |= set(hashes)

    return filename, song_name, result, file_hash


def chunkify(lst, n):
    """
    Splits a list into roughly n equal parts.
    http://stackoverflow.com/questions/2130016/splitting-a-list-of-arbitrary-size-into-only-roughly-n-equal-parts
    """
    return [lst[i::n] for i in xrange(n)]
