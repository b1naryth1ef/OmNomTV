import requests, operator, os, logging
from transmissionrpc import Client
trans = Client("localhost", port=9090)

from tpb import TPB
from tpb import CATEGORIES, ORDERS

# make a file named settings.py, put a TMDB api key in var API_KEY
from settings import config
from fs import getValidFiles

log = logging.getLogger("api")

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
    return TMDB(config.get("TMDB_API_KEY"))

class PirateBay(object):
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
            item = self.search(gen(episode),
                best_exts=config['torrents']['best_formats'],
                best_users=config['torrents']['best_users'],
                min_seeders=config['torrents']['min_seeders'],
                max_seeders=config['torrents']['max_seeders'])
            if item:
                return item
        return None

    def search(self, query, min_seeders=35, max_seeders=10000, best_users=[], best_exts=["mkv"]):
        """
        A pirate bay search function that takes a query, and trys to find
        an optimal torrent based on a few options. It implements a basic
        ranking algorithim to help decided which torrents are the bets, an
        allows format preference, seeder amount preference, and a list of
        preferred users.
        """
        log.info("Searching for %s" % query)
        s = self.t.search(query, category=CATEGORIES.VIDEO.TV_SHOWS)
        s.order(ORDERS.SEEDERS.DES)

        results = {}
        for item in s.page(1):
            log.debug("Valuating result %s" % item)
            rank = 0

            if item.seeders <= 0:
                continue

            if item.user.lower() in best_users:
                log.debug("\tIs ranked user!")
                rank += 1

            if min_seeders <= item.seeders <= max_seeders:
                log.debug("\tHas good amount of seeders")
                rank += 1

            for term in config['torrents']['terms']:
                if term in item.name:
                    log.debug("\tHas search term `%s`" % term)
                    rank += 1

            files = getValidFiles([k for k in item.files.keys()])

            if len(files) != 1:
                continue

            for f in files:
                if os.path.splitext(f)[-1][1:] in best_exts:
                    log.debug("\tFile has preferred format")
                    rank += 1

            results[item] = rank

        best = sorted(results.iteritems(), key=operator.itemgetter(1))
        if len(best):
            return best[-1][0]

        return None
