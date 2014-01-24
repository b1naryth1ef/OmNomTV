import os, mimetypes, shutil
from settings import config

EXTS = [k for k, v in mimetypes.types_map.items() if v.split("/")[0] == "video"]
[EXTS.append(i) for i in ["mkv", "mp4", "avi"]]


class StorageBackend(object):
    def __init__(self, db):
        self.db = db

        # Makes getting config values easier
        for k, v in config['storage'].items():
            setattr(self, k, v)

        self.setup()

    def setup(self):
        """
        Called when the class is first initiated, this way classes do not
        have to super any methods from the StorageBackend base class.
        """
        pass

    def storeFile(self, episode):
        """
        Gets a episode and is expected to return the new path to the file
        after storing. This path is then stored (by the db model) in episode.path.
        """
        source, name = os.path.split(episode.path)
        return os.path.join(source, self.getFormattedName(episode))

    def getFile(self, episode):
        """
        Gets an episode and is expected to return the path to it. By default
        this just returns episode.path, however it is here in case any backends
        want to use a remote system or require some kind of action before
        a file is availible on the local system.

        (NB: In the future, it may be possible for a backend to upload/download
            a file on completion, and store it at a remote location, therefore
            allowing backends to return URL's to the file instead of paths. Thus,
            this function exists.)
        """
        return episode.path

    def checkFile(self, episode):
        """
        Gets an episode that was previously stored by the backend, and is
        expected to return two values, the first is a boolean of whether
        the file still exists or not, and the second is an optional error
        message if the first value is false.
        """

        if os.path.exists(episode.path):
            return True, ""
        return False, "The file at `%s` has disappeared!" % (episode.path)

    def getFormattedName(self, episode):
        """
        Gets an episode and returns the formatted episode name based on
        the config.
        """
        return self.file_format.format(
            episode=episode.episodeid,
            season=episode.seasonid,
            show=episode.show.name,
            name_ds='.'.join(episode.name.split(" ")),
            name_us='_'.join(episode.name.split(" ")),
            name=episode.name)+os.path.splitext(episode.path)[-1]

class RecursiveStorageBackend(StorageBackend):
    def setup(self):
        if not os.path.exists(self.dir):
            raise Exception("The dir (%s) must be set to a path that exists!" %
                self.dir)

    def getPath(self, episode):
        return self.dir_format.format(
                    show=episode.show.name,
                    season=episode.seasonid)

    def storeFile(self, episode):
        path = os.path.join(self.dir, self.getPath(episode))

        if not os.path.exists(path):
            os.makedirs(path)

        dest = os.path.join(path, self.getFormattedName(episode))
        shutil.move(episode.path, dest)
        return dest

class SingleStorageBackend(StorageBackend): pass

class ArchivalStorageBackend(StorageBackend): pass

STORAGE_BACKENDS = {
    "none": StorageBackend,
    "recursive": RecursiveStorageBackend,
    "single": SingleStorageBackend,
    "archival": ArchivalStorageBackend
}


BKND = None
def get_storage_backend(db):
    global BKND
    if not BKND:
        if config['storage']['type'] not in STORAGE_BACKENDS:
            raise Exception('You must specifiy a storage backend! (%s is not valid!)' % 
                config['storage']['type'])

        BKND = STORAGE_BACKENDS[config['storage']['type']](db)
    return BKND


def getValidFiles(li):
    results = []
    for name in li:
        if name[-3:] in EXTS and 'sample' not in name:
            results.append(name)

    return results