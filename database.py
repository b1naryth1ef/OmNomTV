from peewee import *
from dateutil import parser
from datetime import datetime
from dateutil.relativedelta import relativedelta
from api import TMDB, PirateBay
from settings import API_KEY
import json, os, math, thread, time

db = SqliteDatabase('data.db', threadlocals=True)
api = TMDB(API_KEY)
pb = PirateBay()
from transmissionrpc import Client
trans = Client("localhost", port=9090)

EXTS = ["mp4", "mkv", "avi", "mov"]

airdateparse = lambda ad: datetime.strptime(ad, "%Y-%m-%d")

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

    def json(self):
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
    path = CharField(default="")
    torrentid = CharField(default="")
    magnet = CharField(default="")
    track = BooleanField(default=False)

    @classmethod
    def getByEpisodeID(cls, show, id):
        try:
            return Episode.select().where(Episode.episodeid == id & Episode.show == show).get()
        except: return None

    @classmethod
    def new(cls, show, season, data):
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

    def pbFind(self):
        ep = pb.find_episode(self.show, self.seasonid, self.episodeid)
        if not ep:
            raise Exception("Error trying to Queue show %s, no TPB link found..." % self.id)
        self.magnet = ep.magnet_link
        return ep

    def queue(self):
        print "Queueing episode %s" % self.id
        if not self.magnet:
            ep = self.pbFind()
        for torrent in trans.get_torrents():
            if torrent.magnetLink == self.magnet:
                print "Already Queued!"
                return
        t = trans.add_torrent(self.magnet)
        self.torrentid = t.hashString
        self.save()
        return True

    def getFile(self):
        results = []
        for f in self.getTorrent().files().values():
            if f['name'][-3:] in EXTS and 'sammple' not in f['name']:
                results.append(f['name'])

        if len(results) == 1:
            return results[0]
        raise Exception("Could not find results for episode %s" % self.id)

    def updateStatus(self):
        if self.torrentid:
            t = self.getTorrent()
            if t.doneDate:
                self.path = os.path.join(t.downloadDir, self.getFile())

    def getStatus(self):
        if not self.torrentid:
            return {
                "done": False,
                "pc": 0
            }

        t = trans.get_torrent(self.torrentid)
        return {
            "done": True if t.doneDate else False,
            "pc": t.percentDone*100,
        }

    def getAPI(self):
        return api.getEpisode(self.show.extid, self.seasonid, self.episodeid)

    def getTorrent(self):
        return trans.get_torrent(self.torrentid)

    def getState(self):
        print self.path
        if self.torrentid and not self.path:
            return "getting"
        elif self.torrentid:
            return "have"
        elif not self.airdate or self.airdate > datetime.now():
            return "unavail"
        return "none"

    def remove_torrent(self, **kwargs):
        trans.remove_torrent(self.torrentid, **kwargs)

    def json(self):
        data = {
            "sid": self.id,
            "id": self.episodeid,
            "name": self.name,
            "desc": self.desc,
            "season": self.seasonid,
            "airdate": self.airdate,
            "state": self.getState()
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
else: thread.start_new_thread(track_new_episodes, ())
