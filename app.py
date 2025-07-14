from flask import Flask, jsonify, request, send_file
import os
import json
import genera_playlist_auto
from flask_cors import CORS
from flask import send_from_directory
import requests

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "🎶 Playlist Backend attivo!"

# 🔁 Playlist generiche
@app.route("/generate")
def generate():
    playlist = genera_playlist_auto.main()
    if playlist:
        return jsonify({"status": "✅ Playlist generate con successo", "count": len(playlist)})
    return jsonify({"error": "❌ Errore nella generazione playlist"}), 500

@app.route("/playlists")
def playlists():
    if os.path.exists("playlist_auto.json"):
        return send_file("playlist_auto.json", mimetype="application/json")
    return jsonify({"error": "File playlist_auto.json non trovato"}), 404

# ✅ Salvataggio ascolti per utente
@app.route("/log", methods=["POST"])
def log_ascolto():
    data = request.json
    user_id = data.get("userId")
    song_file = data.get("songFile")
    artist = data.get("artist")
    timestamp = data.get("timestamp", "")

    if not user_id or not song_file:
        return jsonify({"error": "Dati incompleti"}), 400

    os.makedirs("ascolti", exist_ok=True)
    ascolti_path = f"ascolti/{user_id}.json"

    ascolti = []
    if os.path.exists(ascolti_path):
        with open(ascolti_path, "r") as f:
            ascolti = json.load(f)

    ascolti.append({
    "songFile": song_file,
    "artist": artist,
    "timestamp": timestamp
    })
    with open(ascolti_path, "w") as f:
        json.dump(ascolti, f, indent=2)

    return jsonify({"status": "✅ Ascolto registrato"})

# ✅ Ottieni playlist personalizzate per utente
@app.route("/playlists/<user_id>")
def playlist_personalizzata(user_id):
    path = f"playlist_utenti/{user_id}.json"  # 🔁 cartella corretta
    if os.path.exists(path):
        return send_file(path, mimetype="application/json")
    return jsonify([])
    if os.path.exists(path):
        return send_file(path, mimetype="application/json")
    return jsonify([])

# ✅ Genera playlist personalizzata per utente
@app.route("/generate/<user_id>")
def generate_playlist_utente(user_id):
    genera_playlist_auto.genera_playlist_per_utente(user_id)
    return jsonify({"status": f"🎯 Playlist generate per {user_id}"})

@app.route("/cover/<user_id>/<filename>")
def serve_cover(user_id, filename):
    return send_from_directory("playlist_utenti/covers", f"{user_id}_{filename}")

def get_spotify_token():
    res = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "client_credentials",
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET
        }
    )
    return res.json().get("access_token")

def search_artist_id(name, token):
    r = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": name, "type": "artist", "limit": 1}
    )
    items = r.json().get("artists", {}).get("items", [])
    return items[0]["id"] if items else None

def get_related_artists(artist_id, token):
    url = f"https://api.spotify.com/v1/artists/{artist_id}/related-artists"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    return [
        {
            "name": a["name"],
            "image": a["images"][0]["url"] if a.get("images") else "img/note.jpg"
        }
        for a in r.json().get("artists", [])[:5]
    ]

@app.route("/suggestions/<user_id>")
def suggerimenti_per_utente(user_id):
    ascolti_path = f"ascolti/{user_id}.json"
    if not os.path.exists(ascolti_path):
        return jsonify([])

    with open(ascolti_path) as f:
        ascolti = json.load(f)

    # Prendi solo gli ultimi 20 ascolti unici
    artisti = []
    seen = set()
    for entry in reversed(ascolti):
        artist = entry.get("artist")
        if artist and artist not in seen:
            artisti.append(artist)
            seen.add(artist)
        if len(artisti) >= 5:
            break

    token = get_spotify_token()
    suggeriti = []
    visti = set()

    for artista in artisti:
        artist_id = search_artist_id(artista, token)
        if not artist_id:
            continue
        related = get_related_artists(artist_id, token)
        for a in related:
            if a["name"] not in artisti and a["name"] not in visti:
                suggeriti.append(a)
                visti.add(a["name"])
            if len(suggeriti) >= 10:
                break
        if len(suggeriti) >= 10:
            break

    return jsonify(suggeriti)


@app.route("/debug/ascolti/<user_id>")
def debug_ascolti(user_id):
    path = f"ascolti/{user_id}.json"
    if not os.path.exists(path):
        return jsonify({"status": "❌ File non trovato"}), 404

    with open(path) as f:
        data = json.load(f)
    return jsonify(data)
