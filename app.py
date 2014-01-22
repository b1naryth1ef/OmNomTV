from flask import Flask, render_template, request, jsonify
from database import *

app = Flask(__name__)

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
            return jsonify({
                "error": "Cannot get that episode right now!"
            })
        episode.queue()
        return jsonify({
            "success": True
        })

if __name__ == '__main__':
    app.run(host="localhost", debug=True)