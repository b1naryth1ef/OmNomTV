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
        print "tv/%s/season/%s/episode/%s" % (show, season, ep)
        return self.get("tv/%s/season/%s/episode/%s" % (show, season, ep))

    def getEpisodeImages(self, show, season, ep):
        return self.get("tv/%s/season/%s/episode/%s/images" % (show, season, ep))

class PirateBay(object):
    OK_USERS = ['eztv']

    def __init__(self):
        self.t = TPB('https://thepiratebay.org')

    def find_episode(self, show, season, episode):
        print "%02d" % (1,)
        print '%s S%02dE%02d' % (show.name, season, episode)
        s = self.t.search('%s S%02dE%02d' % (show.name, season, episode), category=CATEGORIES.VIDEO.TV_SHOWS)
        s.order(ORDERS.SEEDERS.DES)

        for item in s.page(1):
            if item.user in self.OK_USERS:
                return item

            if item.seeders >= 50:
                return item

        return None

