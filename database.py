from peewee import *
from dateutil import parser
from datetime import datetime
from dateutil.relativedelta import relativedelta
from api import TMDB, PirateBay
from settings import API_KEY
import json

db = SqliteDatabase('data.db', threadlocals=True)
api = TMDB(API_KEY)
pb = PirateBay()
from transmissionrpc import Client
trans = Client("localhost", port=9090)

EXTS = ["mp4", "mkv", "avi", "mov"]

airdateparse = lambda ad: datetime.strptime(ad, "%Y-%m-%d")

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
            "state": {
                "done": 60,
                "getting": 15,
                "other": 0,
            }
        }

    def getEpisodes(self, season=None):
        print Episode.select().get().seasonid
        if season == None:
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
                    Episode.new(self, season_data, ep)



class Episode(BaseModel):
    show = ForeignKeyField(Show)
    seasonid = IntegerField()
    episodeid = IntegerField()
    name = CharField()
    desc = CharField()
    image = CharField(null=True)
    airdate = DateTimeField(null=True)
    path = CharField(default="")

    tran_id = IntegerField(default=-1)

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
        e.save()
        return e

    def queue(self):
        print "Queueing episode %s" % self.id
        ep = pb.find_episode(self.show, self.seasonid, self.episodeid)
        if not ep:
            raise Exception("Error trying to Queue show %s, no TPB link found..." % self.id)
        for torrent in trans.get_torrents():
            if torrent.magnetLink == ep.magnet_link:
                print "Already Queued!"
        t = trans.add_torrent(ep.magnet_link)
        self.tran_id = t.id
        self.path = self.getPath()
        self.save()
        return True

    def getFile(self):
        results = []
        for f in trans.get_torrent(self.tran_id).files().values():
            if f['name'][-3:] in EXTS and 'sammple' not in f['name']:
                results.append(f['name'])
        
        if len(results) == 1:
            return results[0]
        raise Exception("Could not find results for episode %s" % self.id)

    def getPath(self):
        return trans.get_torrent(self.tran_id).downloadDir

    def getStatus(self):
        if self.tran_id == -1:
            return {
                "done": False,
                "pc": 0
            }
        t = trans.get_torrent(self.tran_id)
        if t.doneDate:
            return {
                "done": True,
                "pc": 100,
            }
        else:
            return {
                "done": False,
                "pc": t.percentDone*100
            }

    def getAPI(self):
        return api.getEpisode(self.show.extid, self.seasonid, self.episodeid)

    def getState(self):
        if self.tran_id != -1 and not self.path:
            return "getting"
        elif self.tran_id != -1:
            return "have"
        elif not self.airdate or self.airdate > datetime.now():
            return "unavail"
        return "none"

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

def schedule():
    return
    for ep in Episode.select().where(Episode.path == ""):
        if airdateparse(ep.getAPI()['air_date']) <= datetime.now():
            if ep.tran_id != -1: print ep.getFile()
            try:ep.queue()
            except Exception as e: print e

def check_show(show):
    show_entry = Show.select().where(Show.extid == show['id']).get()

    show_data = {
        "seasons": []
    }

    # Locally index the episodes
    for season in show['seasons']:
        season_data = api.getSeason(show_entry.extid, season['season_number'])

        episodes = []

        for ep in season_data['episodes']:
            print show_entry.shouldTrack(ep)
            q = Episode.getByEpisodeID(show, ep['episode_number'])
            print ep['air_date']
            if q:
                ep['path'] = q.getPath()
                ep['status'] = q.getStatus()
            elif show_entry.shouldTrack(ep):
                e = Episode.new(show_entry, season_data, ep)
                ep['path'] = ""
                ep['status'] = e.getStatus()
            else:
                ep['path'] = ""
                ep['status'] = ""
            episodes.append(ep)

        season_data['episodes'] = episodes
        show_data['seasons'].append(season_data)

    show.update(show_data)
    return show

def init_db():
    Show.create_table()
    Episode.create_table()
    Show.new("10283")

if __name__ == "__main__":
    import os
    os.popen("rm data.db")
    init_db()