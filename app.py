from flask import Flask, jsonify, request, send_file, send_from_directory
import os
import json
import genera_playlist_auto
import requests
from datetime import datetime, timedelta
import random
from flask_cors import CORS

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")

app = Flask(__name__)
CORS(app)

# 🔧 Crea le cartelle mancanti all'avvio
os.makedirs("ascolti", exist_ok=True)
os.makedirs("suggestions_cache", exist_ok=True)

@app.route("/")
def home():
    return "🎶 Playlist Backend attivo!"

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

@app.route("/playlists/<user_id>")
def playlist_personalizzata(user_id):
    path = f"playlist_utenti/{user_id}.json"
    if os.path.exists(path):
        return send_file(path, mimetype="application/json")
    return jsonify([])

@app.route("/generate/<user_id>")
def generate_playlist_utente(user_id):
    genera_playlist_auto.genera_playlist_per_utente(user_id)
    return jsonify({"status": f"🎯 Playlist generate per {user_id}"})

@app.route("/cover/<user_id>/<filename>")
def serve_cover(user_id, filename):
    return send_from_directory("playlist_utenti/covers", f"{user_id}_{filename}")

def get_spotify_token():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("❌ Variabili SPOTIFY_CLIENT_ID o SPOTIFY_CLIENT_SECRET mancanti")
        return None

    res = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "client_credentials",
            "client_id": SPOTIFY_CLIENT_ID,
            "client_secret": SPOTIFY_CLIENT_SECRET
        }
    )

    if res.status_code != 200:
        print("❌ Errore richiesta token:", res.status_code, res.text)
        return None

    print("🎫 Token ottenuto correttamente")
    return res.json().get("access_token")

def search_artist_id(name, token):
    print(f"🎯 Cerco artista su Spotify: {name}")
    r = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": name, "type": "artist", "limit": 1}
    )

    if r.status_code != 200:
        print("❌ Errore nella ricerca artista:", r.status_code, r.text)
        return None

    items = r.json().get("artists", {}).get("items", [])
    if not items:
        print("⚠️ Nessun risultato trovato per:", name)
        return None

    print("✅ Artista trovato:", items[0]["name"], "| ID:", items[0]["id"])
    return items[0]["id"]

def get_related_artists(artist_id, token):
    url = f"https://api.spotify.com/v1/artists/{artist_id}/related-artists"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    related = r.json().get("artists", [])
    print(f"📡 Risposta raw da Spotify (related-artists): {len(related)} artisti trovati")
    return [
        {
            "name": a.get("name"),
            "image": a["images"][0]["url"] if a.get("images") and a["images"] else "img/note.jpg"
        }
        for a in related
    ]

def get_lastfm_similar_artists(artist_name):
    print(f"🎯 Cerco artisti simili su Last.fm per: {artist_name}")
    url = "http://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "artist.getsimilar",
        "artist": artist_name,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": 5
    }
    try:
        r = requests.get(url, params=params)
        data = r.json()
        similars = data.get("similarartists", {}).get("artist", [])
        print(f"🎯 Last.fm suggeriti per {artist_name}: {[a['name'] for a in similars]}")
        return [
            {
                "name": a["name"],
                "image": a["image"][-1]["#text"] if a.get("image") else "img/note.jpg"
            }
            for a in similars if a.get("name")
        ]
    except Exception as e:
        print("⚠️ Errore Last.fm:", e)
        return []

def salva_cache(user_id, artist_name, suggestions):
    os.makedirs(f"suggestions_cache/{user_id}", exist_ok=True)
    with open(f"suggestions_cache/{user_id}/{artist_name}.json", "w") as f:
        json.dump({
            "updated": datetime.utcnow().isoformat(),
            "suggestions": suggestions
        }, f, indent=2)

def carica_cache(user_id, artist_name):
    path = f"suggestions_cache/{user_id}/{artist_name}.json"
    if not os.path.exists(path):
        return None

    with open(path) as f:
        data = json.load(f)

    updated = datetime.fromisoformat(data.get("updated"))
    if datetime.utcnow() - updated > timedelta(days=7):
        return None  # cache scaduta

    return data.get("suggestions", [])


@app.route("/suggestions/<user_id>")
def suggerimenti_per_utente(user_id):
    ascolti_path = f"ascolti/{user_id}.json"
    if not os.path.exists(ascolti_path):
        print(f"📁 File ascolti non trovato: {ascolti_path}")
        return jsonify([])

    with open(ascolti_path) as f:
        ascolti = json.load(f)

    artisti = []
    seen = set()
    for entry in reversed(ascolti):
        artist = entry.get("artist")
        if artist and artist not in seen:
            artisti.append(artist)
            seen.add(artist)
        if len(artisti) >= 5:
            break

    print("🎧 Artisti ascoltati di recente:", artisti)

    token = get_spotify_token()
    suggeriti = []
    visti = set()

    for artista in artisti:
        suggeriti_artist = []

        if token:
            artist_id = search_artist_id(artista, token)
            if artist_id:
                suggeriti_artist = get_related_artists(artist_id, token)

        if not suggeriti_artist and LASTFM_API_KEY:
            suggeriti_artist = get_lastfm_similar_artists(artista)

        for a in suggeriti_artist:
            if a["name"] not in artisti and a["name"] not in visti:
                suggeriti.append(a)
                visti.add(a["name"])
            if len(suggeriti) >= 10:
                break
        if len(suggeriti) >= 10:
            break

    print("✅ Suggeriti finali:", [s["name"] for s in suggeriti])
    return jsonify(suggeriti)

@app.route("/debug/ascolti/<user_id>")
def debug_ascolti(user_id):
    path = f"ascolti/{user_id}.json"
    if not os.path.exists(path):
        return jsonify({"status": "❌ File non trovato"}), 404

    with open(path) as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/suggestions-by-artist/<user_id>")
def suggerimenti_per_artista(user_id):
    ascolti_path = f"ascolti/{user_id}.json"
    if not os.path.exists(ascolti_path):
        return jsonify({})

    with open(ascolti_path) as f:
        ascolti = json.load(f)

    artisti = []
    seen = set()
    for entry in reversed(ascolti):
        artist = entry.get("artist")
        if artist and artist not in seen:
            artisti.append(artist)
            seen.add(artist)
        if len(artisti) >= 3:
            break

    token = get_spotify_token()
    suggerimenti = {}
    visti = set()

    for artista in artisti:
        cached = carica_cache(user_id, artista)
        if cached:
            random.shuffle(cached)
            blocco = [a for a in cached if a["name"] not in visti][:8]
            for s in blocco:
                visti.add(s["name"])
            suggerimenti[artista] = blocco
            continue

        suggeriti_artist = []

        # Spotify
        if token:
            artist_id = search_artist_id(artista, token)
            if artist_id:
                suggeriti_artist = get_related_artists(artist_id, token)

        # Last.fm fallback
        if not suggeriti_artist or len(suggeriti_artist) < 3:
            suggeriti_artist = get_lastfm_similar_artists(artista)

        nomi_unici = []
        visti_locale = set()
        for s in suggeriti_artist:
            if s["name"] not in visti and s["name"] not in visti_locale:
                nomi_unici.append(s)
                visti_locale.add(s["name"])
            if len(nomi_unici) >= 8:
                break

        if nomi_unici:
            suggerimenti[artista] = nomi_unici
            for s in nomi_unici:
                visti.add(s["name"])
            salva_cache(user_id, artista, suggeriti_artist)  # salva cache completa

    print("✅ Suggerimenti organizzati per artista (con caching):", list(suggerimenti.keys()))
    return jsonify(suggerimenti)

@app.route("/refresh_suggestions", methods=["POST"])
def refresh_suggestions_all():
    print("🔁 Inizio aggiornamento suggerimenti...")
    users_path = "ascolti"
    results = {}

    if not os.path.exists(users_path):
        print("❌ Cartella ascolti non trovata")
        return jsonify({"error": "❌ Cartella ascolti non trovata"}), 404

    try:
        for filename in os.listdir(users_path):
            print(f"➡️ Analizzo file: {filename}")
            if filename.endswith(".json"):
                user_id = filename.replace(".json", "")
                try:
                    url = f"https://playlist-backend-97qc.onrender.com/suggestions-by-artist/{user_id}"
                    r = requests.get(url)
                    print(f"🟢 Richiesta per {user_id}: {r.status_code}")
                    if r.status_code == 200:
                        results[user_id] = "✅ aggiornato"
                    else:
                        results[user_id] = f"❌ {r.status_code}"
                except Exception as e:
                    print(f"⚠️ Errore per {user_id}: {str(e)}")
                    results[user_id] = f"❌ {str(e)}"

        print("✅ Risultato finale:", results)
        return jsonify(results)
    
    except Exception as main_err:
        print("🔥 ERRORE INTERNO NEL REFRESH:", str(main_err))
        return jsonify({"error": str(main_err)}), 500
