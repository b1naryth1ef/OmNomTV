from flask import Flask, render_template, request, jsonify, make_response
from database import *
from api import getTMDBAPI

# Wtf python has this library?
import mimetypes

app = Flask(__name__)

tmdb = getTMDBAPI()

@app.route("/")
def index():
    return render_template("base.html")

@app.route("/api/template")
def api_template():
    name = request.values.get("name")
    try:
        return jsonify({
            "content": render_template(name)
        })
    except Exception as e:
        return jsonify({
            "error": "Invalid Template Name (%s)" % e
        })

@app.route("/api/search")
def api_search():
    query = request.values.get("query", "")
    if not query:
        return jsonify({"error": "No Search Query!"})
    return jsonify(tmdb.searchTV(query))

# list, get, delete
@app.route("/api/show/<action>")
def api_shows(action=None):
    if action == "list":
        result = {
            "shows": []
        }
        for s in Show.select():
            result['shows'].append(s.json())
        return jsonify(result)

    if action == "add":
        Show.new(request.values.get("show"))
        return jsonify({
            "success": True
        })

    if action == "delete":
        try:
            # TODO: delete data
            s = Show.select().where(Show.extid == request.values.get("show")).get()
            Episode.delete().where(Episode.show == s).execute()
            Show.delete().where(Show.extid == request.values.get("show")).execute()
        except Exception as e:
            return jsonify({"error": "Error deleting show: %s" % e})
        return jsonify({"success": True})

@app.route("/api/season/<show>/<season>/<action>")
def api_seasons(show=None, season=None, action=None):
    if action == "get":
        show = Show.select().where(Show.extid == show).get()
        episodes = show.getEpisodes(season=season)

        data = {}
        data['id'] = season
        data['show'] = show.extid
        data['episodes'] = [e.json() for e in episodes]

        return jsonify({
            "season": data
        })

@app.route("/api/episode/<action>")
def api_episode(action=None):
    try:
        show = Show.select().where(Show.extid == request.values.get("show")).get()
        episode = Episode.select().where(
            (Episode.episodeid == request.values.get("episode")) &
            (Episode.show == show) &
            (Episode.seasonid == request.values.get("season"))).get()
    except Exception as e:
        return jsonify({
            "error": "Invalid show or episode id! (%s)" % e
        })

    if action == "get":
        if episode.getState() != "none":
            return jsonify({"error": "Cannot get that episode right now!"})
        try:
            episode.queue()
        except Exception as e:
            return jsonify({"error": "Error queueing the episode! (%s)" % e})
        return jsonify({"success": True})

    # Stop and delete the torrent including local data
    if action == "delete":
        try:
            episode.remove_torrent(delete_data=True)
            episode.torrentid = ""
            if episode.path:
                # In this case, we need to remove this data
                pass
            episode.save()
        except Exception as e:
            return jsonify({"error": "Error deleting torrent: %s" % e})
        return jsonify({"success": True})
        #return make_response(open(episode.path).read())

@app.route("/file/<eid>/<mode>/<junk>")
@app.route("/file/<eid>/<mode>")
def app_file(eid, mode, junk=None):
    episode = Episode.select().where(Episode.id == eid).get()
    res = make_response(open(episode.path).read())
    if mode == "dl":
        res.content_type = "application/octet-stream"
    elif mode == "play":
        res.content_type, _ = mimetypes.guess_type(episode.path)
    return res


if __name__ == '__main__':
    app.run(host="localhost", debug=True)
