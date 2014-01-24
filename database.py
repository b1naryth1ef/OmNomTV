from peewee import *
from dateutil import parser
from datetime import datetime
from dateutil.relativedelta import relativedelta
from settings import config
from transmissionrpc import Client
from api import TMDB, PirateBay
from fs import EXTS, get_storage_backend, getValidFiles
import json, os, math, thread, time, logging

db = SqliteDatabase('data.db', threadlocals=True)
backend = get_storage_backend(db)
api = TMDB(config["TMDB_API_KEY"])
pb = PirateBay()
trans = Client(config['transmission']['host'], config['transmission']['port'])

log = logging.getLogger("database")

# Parses a TMDB API air date
airdateparse = lambda ad: datetime.strptime(ad, "%Y-%m-%d")

# Percentifies stuff
def percent(am, total):
    if not am: return 0
    return int(100.0 / ((total * 1.0) / am))

class BaseModel(Model):
    class Meta:
        database = db

class TrackLevels(object):
    ALL = 0
    NEW = 1
    OLD = 2

class Show(BaseModel):
    name = CharField()
    extid = IntegerField()
    poster = CharField()
    seasons = CharField()  # JSON
    track_level = IntegerField(default=TrackLevels.NEW)
    subscribe = BooleanField(default=True)

    def shouldTrack(self, ep):
        if self.track_level == TrackLevels.ALL:
            return True

        if not ep['air_date']:
            return False

        date = airdateparse(ep['air_date'])
        if date <= (datetime.now()-relativedelta(days=5)):
            if self.track_level == TrackLevels.NEW:
                return False
            if self.track_level == TrackLevels.OLD:
                return True
        if self.track_level == TrackLevels.NEW:
            return True
        return False

    def getSeasons(self):
        return json.loads(self.seasons)

    def setSeasons(self, data=[]):
        self.seasons = json.dumps(data)

    @classmethod
    def new(cls, id):
        self = cls()
        data = api.getShow(id)
        self.extid = id
        self.name = data.get("name")
        self.poster = data.get("poster_path")
        self.setSeasons([i['season_number'] for i in data.get("seasons")])
        self.save()
        self.index()
        return self

    def dict(self):
        return {
            "id": self.extid,
            "poster": self.poster,
            "name": self.name,
            "seasons": self.getSeasons(),
            "num_seasons": len(self.getSeasons()),
            "state": self.stats()
        }

    def getEpisodes(self, season=None):
        if season is None:
            return Episode.select().where(Episode.show == self)
        else:
            return Episode.select().where((Episode.show == self) & (Episode.seasonid == season))

    def index(self):
        show = api.getShow(self.extid)
        for season in show['seasons']:
            print "Indexing season %s for show %s" % (season['season_number'], self.id)
            season_data = api.getSeason(self.extid, season['season_number'])

            for ep in season_data['episodes']:
                print "\tIndexing episode %s" % ep['episode_number']
                q = Episode.getByEpisodeID(show, ep['episode_number'])
                if not q:
                    e = Episode.new(self, season_data, ep)

    def stats(self):
        have, getting, none, unavail = 0, 0, 0, 0

        total = self.getEpisodes().count()
        print total
        for episode in self.getEpisodes():
            if episode.getState() == "getting":
                getting += 1
            elif episode.getState() == "have":
                have += 1
            elif episode.getState() == "unavail":
                unavail += 1
            else: none += 1
        print total, have, getting, none, unavail

        return {
            "have": percent(have, total),
            "getting": percent(getting, total),
            "none": percent(none, total),
            "unavail": percent(unavail, total)
        }

class Episode(BaseModel):
    show = ForeignKeyField(Show)
    seasonid = IntegerField()
    episodeid = IntegerField()
    name = CharField()
    desc = CharField()
    image = CharField(null=True)
    airdate = DateTimeField(null=True)
    completed = DateTimeField(null=True)
    path = CharField(default="")
    torrentid = CharField(default="")
    track = BooleanField(default=False)

    @classmethod
    def getByEpisodeID(cls, show, id):
        try:
            return Episode.select().where(Episode.episodeid == id & Episode.show == show).get()
        except: return None

    @classmethod
    def new(cls, show, season, data):
        """
        Creates a new episode based on show, season, and data from the
        TMDB API.
        """
        e = cls()
        e.show = show
        e.seasonid = season['season_number']
        e.episodeid = data['episode_number']
        e.name = data['name']
        e.desc = data['overview']
        e.image = data['still_path']
        e.airdate = airdateparse(data['air_date']) if data['air_date'] else None

        if e.airdate and e.airdate > datetime.now():
            show.shouldTrack(data)
            e.track = True
        e.save()
        return e

    def onFinish(self):
        """
        Called when this episodes torrent is finished. This handles storing
        the file, and setting completed date.
        """
        self.path = backend.storeFile(self)
        self.completed = datetime.now()
        self.save()

    def findValidTorrent(self):
        """
        Attempts to find a torrent using the TPB search API. This abstracts
        any special search or behaivorial logic to the API, and will either
        return a torrent object, or none
        """
        return pb.find_episode(self)

    def queue(self):
        """
        Attempts to both find a valid magnet URL using `findValidTorrent`,
        and queue the torrent within transmission. This will fail if either
        a torrent magnet URL could not be found, or if the found magnet URL
        is already queued within transmission.

        (NB: In the future, it might make sense for this to set .torrentid,
            if the magnet url is already tracked.)
        """

        log.info("Attempting to queue episode %s for download" % self.id)
        tpb_torrent = self.findValidTorrent()
        if not tpb_torrent:
            raise Exception("Error trying to Queue show %s, no torrent found..." % self.id)

        for torrent in trans.get_torrents():
            if torrent.magnetLink == tpb_torrent.magnet_link:
                raise Exception("Epsiode torrent is already queued! (%s)" % self.id)

        # Queue the torrent and save it's hash
        t = trans.add_torrent(tpb_torrent.magnet_link)
        self.torrentid = t.hashString
        self.save()
        return True

    def getFile(self):
        """
        Attemps to find a valid video file within the torrent, ignoring
        files that do not match inside of EXTS, and files that contain
        "sample" in them. If the number of files found does not equal 1,
        an exception is thrown.

        (NB: if an extension is longer than 3 characters, this breaks)
        """
        results = getValidFiles([i['name'] for i in self.getTorrent().files().values()])

        if len(results) != 1:
            raise Exception("Could not find file for episode %s (%s)" % (self.id, self.torrentid))

        return results[0]

    def updateStatus(self):
        """
        Polls for an update from transmission on the state of this torrent,
        optionally marking it as finished internally and calling `onFinish`
        """
        if self.torrentid:
            t = self.getTorrent()

            # Only matters if we haven't already finished
            if t.doneDate and not self.path:
                self.path = os.path.join(t.downloadDir, self.getFile())
                self.onFinish()
                self.save()

    def getProgress(self):
        """
        Returns this torrents download progress if it exists within transmission,
        otherwise returns 0.
        """
        # FIXME: this should be in a scheduled task
        self.updateStatus()

        if not self.torrentid:
            return 0

        return self.getTorrent().percentDone * 199

    def getAPI(self):
        """
        Returns a TMDB data payload for this episode
        """
        return api.getEpisode(self.show.extid, self.seasonid, self.episodeid)

    def getTorrent(self):
        """
        Returns the torrent for this episode
        """
        return trans.get_torrent(self.torrentid)

    def rmvTorrent(self, **kwargs):
        """
        Removes this torrent from transmission, with the option of passing
        kw params to the transmission RPC call.

        (FIXME: For multiple torrent backends, we need to change the way
            this handles kwargs (e.g remove it))
        """
        trans.remove_torrent(self.torrentid, **kwargs)

    def getState(self):
        """
        Returns the torrents state
        """
        if self.torrentid and not self.path:
            return "getting"
        elif self.torrentid:
            return "have"
        elif not self.airdate or self.airdate > datetime.now():
            return "unavail"
        return "none"

    def dict(self):
        """
        Returns a dictionary that can be passed to the frontend as json,
        with important attributes attached.
        """
        data = {
            "sid": self.id,
            "id": self.episodeid,
            "name": self.name,
            "desc": self.desc,
            "season": self.seasonid,
            "airdate": self.airdate,
            "state": self.getState(),
            "prog": self.getProgress(),
            "path": "/file/%s/" % self.id,
            "fname": os.path.split(self.path)[-1] if self.path else ""
        }

        return data

def track_new_episodes():
    while True:
        for episode in Episode.select().where(
                (Episode.airdate < datetime.now()-relativedelta(hours=5)) & (Episode.track == True)):
            episode.queue()

# def schedule():
#     # Update Shows
#     while True:
#         for episode in Episode.select().where(Episode.need_index == True):
#             print "Indexing Pirate Bay Magnet Link"
#             for episode in show.getEpisodes():
#                 try: episode.pbFind()
#                 except: pass
#             show.need_index = False
#             show.save()

#         time.sleep(60*30)

# def schedule():
#     return
#     for ep in Episode.select().where(Episode.path == ""):
#         if airdateparse(ep.getAPI()['air_date']) <= datetime.now():
#             if ep.tran_id != -1: print ep.getFile()
#             try: ep.queue()
#             except Exception as e: print e

def init_db():
    Show.create_table()
    Episode.create_table()
    Show.new("10283")
    Show.new("1428")

if __name__ == "__main__":
    import os
    os.popen("rm data.db")
    init_db()
#else: thread.start_new_thread(track_new_episodes, ())
