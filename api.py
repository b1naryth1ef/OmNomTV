import requests
from transmissionrpc import Client
trans = Client("localhost", port=9090)

from tpb import TPB
from tpb import CATEGORIES, ORDERS

# make a file named settings.py, put a TMDB api key in var API_KEY
from settings import API_KEY

class TMDB(object):
    def __init__(self, key):
        self.key = key

    def get(self, url, data={}):
        data['api_key'] = self.key
        r = requests.get("https://api.themoviedb.org/3/%s" % url, params=data)
        r.raise_for_status()
        return r.json()

    def searchTV(self, query):
        return self.get("search/tv", {"query": query})

    def getShow(self, id):
        return self.get("tv/%s" % id)

    def getShowImages(self, id):
        return self.get("tv/%s/images" % id)

    def getPopularShows(self):
        return self.get("tv/popular")

    def getSeason(self, show, season):
        return self.get("tv/%s/season/%s" % (show, season))

    def getSeasonImages(self, show, season):
        return self.get("tv/%s/season/%s/images" % (show, season))

    def getEpisode(self, show, season, ep):
        return self.get("tv/%s/season/%s/episode/%s" % (show, season, ep))

    def getEpisodeImages(self, show, season, ep):
        return self.get("tv/%s/season/%s/episode/%s/images" % (show, season, ep))

def getTMDBAPI():
    return TMDB(API_KEY)

class PirateBay(object):
    OK_USERS = ['eztv']

    def __init__(self):
        self.t = TPB('https://thepiratebay.org')

    # This is the generic "Name S00E00" format seen on TPB
    def gen_query_generic(self, ep):
        return '%s S%02dE%02d' % (ep.show.name, ep.seasonid, ep.episodeid)

    # This format should help with episodes that don't really fall under S00E00
    def gen_query_simple(self, ep):
        return '%s %s' % (ep.show.name, ep.name)

    def find_episode(self, episode):
        item = None
        for gen in [self.gen_query_generic, self.gen_query_simple]:
            item = self.search(gen(episode))
            if item:
                return item
        return None

    def search(self, query):
        print "Searching for %s" % query
        s = self.t.search(query, category=CATEGORIES.VIDEO.TV_SHOWS)
        s.order(ORDERS.SEEDERS.DES)

        for item in s.page(1):
            if item.user in self.OK_USERS:
                return item

            if item.seeders >= 25:
                return item

        return None
