from flask import Flask, jsonify, request, send_file, send_from_directory
import os
import json
import genera_playlist_auto
import requests
from datetime import datetime, timedelta, timezone
import random
from flask_cors import CORS
from supabase import create_client, Client

SUPABASE_URL = "https://uoqhmrlcswcefgvgigwt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVvcWhtcmxjc3djZWZndmdpZ3d0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI3NjUyOTAsImV4cCI6MjA2ODM0MTI5MH0.lbB6UOQmG9aASXou8tTuk3sC9gJ7X15Nnoaq2kBsdUI"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")

app = Flask(__name__)

# ✅ Specifica i domini permessi invece di "*"
allowed_origins = ["http://localhost:8080", "https://playlist-frontend.onrender.com"]

CORS(app, resources={r"/*": {"origins": allowed_origins}}, supports_credentials=True)

# ✅ Fix per CORS
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
    return response

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

# ✅ Nuova rotta per servire songs_min2.json
@app.route("/songs")
def get_songs():
    if os.path.exists("songs_min2.json"):
        return send_file("songs_min2.json", mimetype="application/json")
    return jsonify({"error": "songs_min2.json non trovato"}), 404

# ============================
# ⬇️ (da qui in poi resta tutto il tuo codice identico)
# ============================

@app.route("/log", methods=["POST"])
def log_ascolto():
    data = request.json
    user_id = data.get("userId")
    song_file = data.get("songFile")
    artist = data.get("artist")
    album = data.get("album", "")
    timestamp_str = data.get("timestamp")

    if not user_id or not song_file or not artist or not timestamp_str:
        return jsonify({"error": "Dati incompleti"}), 400

    try:
        from dateutil import parser
        timestamp = parser.isoparse(timestamp_str)
    except Exception as e:
        print(f"⚠️ Errore parsing timestamp: {e}")
        return jsonify({"error": "Timestamp non valido"}), 400

    try:
        res = supabase.table("listening_history").insert({
            "user_id": user_id,
            "artist": artist,
            "album": album,
            "song_file": song_file,
            "timestamp": timestamp.isoformat()
        }).execute()
        return jsonify({"status": "✅ Ascolto salvato su Supabase"})
    except Exception as e:
        print(f"❌ Errore inserimento Supabase: {e}")
        return jsonify({"error": "❌ Errore salvataggio"}), 500


@app.route("/recently-played/<user_id>")
def recently_played(user_id):
    try:
        response = supabase.table("listening_history") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("timestamp", desc=True) \
            .limit(20) \
            .execute()
        # ✅ anche se non ci sono ascolti ritorna lista vuota
        return jsonify(response.data or [])
    except Exception as e:
        print(f"❌ Errore recently-played: {e}")
        return jsonify([]), 200

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
        "limit": 100  # ✅ MASSIMO accettato da Last.fm
    }
    try:
        r = requests.get(url, params=params)
        data = r.json()
        similars = data.get("similarartists", {}).get("artist", [])

        print(f"🎯 {len(similars)} artisti suggeriti da Last.fm per {artist_name}")

        # 🔁 Shuffle per ottenere varietà
        random.shuffle(similars)

        # 🧹 Ritorna solo quelli con nome e immagine valida
        return [
            {
                "name": a["name"],
                "image": next((img["#text"] for img in a.get("image", []) if img["#text"]), "img/note.jpg")
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
    suggestions_dir = f"suggestions_cache/{user_id}"
    suggerimenti = {}
    visti = set()
    artisti = []

    # 🎧 STEP 1: Leggi gli ascolti da Supabase
    try:
        response = supabase.table("listening_history") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("timestamp", desc=True) \
            .execute()
        ascolti = response.data
    except Exception as e:
        print(f"❌ Errore nel recupero ascolti da Supabase: {e}")
        return jsonify({"error": "Errore Supabase"}), 500

    # 🎯 Estrai fino a 3 artisti unici più recenti
    seen = set()
    for entry in ascolti:
        artist = entry.get("artist")
        if artist and artist not in seen:
            artisti.append(artist)
            seen.add(artist)
        if len(artisti) >= 3:
            break

    token = get_spotify_token()

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

        if token:
            artist_id = search_artist_id(artista, token)
            if artist_id:
                suggeriti_artist = get_related_artists(artist_id, token)

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
            salva_cache(user_id, artista, suggeriti_artist)

    # 🧪 STEP 3: fallback cache
    if not suggerimenti and os.path.exists(suggestions_dir):
        for filename in os.listdir(suggestions_dir):
            if filename.endswith(".json"):
                artista = filename.replace(".json", "")
                try:
                    with open(os.path.join(suggestions_dir, filename)) as f:
                        cached_data = json.load(f)
                        blocco = cached_data.get("suggestions", [])
                        random.shuffle(blocco)
                        blocco_filtrato = [s for s in blocco if s["name"] not in visti][:8]
                        if blocco_filtrato:
                            suggerimenti[artista] = blocco_filtrato
                            for s in blocco_filtrato:
                                visti.add(s["name"])
                except Exception as e:
                    print(f"⚠️ Errore lettura cache per {artista}: {e}")

    print("✅ Suggerimenti finali (anche da cache):", list(suggerimenti.keys()))
    return jsonify(suggerimenti)

@app.route("/refresh_suggestions", methods=["POST"])
def refresh_suggestions_all():
    print("🔁 Inizio aggiornamento suggerimenti...")
    results = {}

    try:
        # Prende tutti gli user_id unici da Supabase
        response = supabase.table("listening_history") \
            .select("user_id") \
            .execute()

        user_ids = list(set([r["user_id"] for r in response.data if "user_id" in r]))

        for user_id in user_ids:
            try:
                result = aggiorna_suggerimenti(user_id)
                results[user_id] = result.get("status", "✅")
            except Exception as e:
                print(f"⚠️ Errore per {user_id}: {str(e)}")
                results[user_id] = f"❌ {str(e)}"

        return jsonify(results)

    except Exception as main_err:
        print(f"🔥 Errore generale: {main_err}")
        return jsonify({"error": str(main_err)}), 500

def aggiorna_suggerimenti(user_id):
    cache_dir = f"suggestions_cache/{user_id}"
    os.makedirs(cache_dir, exist_ok=True)

    try:
        response = supabase.table("listening_history") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("timestamp", desc=True) \
            .execute()
        ascolti = response.data
    except Exception as e:
        print(f"❌ Errore Supabase per {user_id}: {e}")
        return {"error": str(e)}, 500

    from datetime import timezone
    now = datetime.now(timezone.utc)
    one_week_ago = now - timedelta(days=7)

    artisti_con_data = []
    visti = set()
    for entry in ascolti:
        artist = entry.get("artist")
        timestamp_str = entry.get("timestamp")
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", ""))
        except:
            continue
        if artist and artist not in visti:
            artisti_con_data.append((artist, timestamp))
            visti.add(artist)

    if not artisti_con_data:
        return {"error": "Nessun artista valido trovato"}

    # Carica artisti già presenti in cache
    artisti_in_cache = []
    if os.path.exists(cache_dir):
        for file in os.listdir(cache_dir):
            if file.endswith(".json"):
                artista = file.replace(".json", "")
                artisti_in_cache.append(artista)

    nuovi = []
    mantenuti = []

    for artist, timestamp in artisti_con_data:
        if timestamp >= one_week_ago and artist not in artisti_in_cache:
            nuovi.append(artist)
        elif artist in artisti_in_cache:
            mantenuti.append(artist)

    # ♻️ Nessun nuovo ascolto → rigenero artisti già in cache
    if not nuovi and mantenuti:
        for artist in mantenuti:
            suggeriti = get_lastfm_similar_artists(artist)
            random.shuffle(suggeriti)
            salva_cache(user_id, artist, suggeriti)
        return {"status": "♻️ Nessun nuovo ascolto – rigenerati suggerimenti per gli stessi artisti"}

    # ➕ Suggerimenti per i nuovi
    for artist in nuovi:
        suggeriti = get_lastfm_similar_artists(artist)
        random.shuffle(suggeriti)
        salva_cache(user_id, artist, suggeriti)

    # 🧹 Mantieni max 5 blocchi
    tutti = nuovi + mantenuti
    if len(tutti) > 5:
        da_tenere = tutti[-5:]
        da_rimuovere = [a for a in artisti_in_cache if a not in da_tenere]
        for artista in da_rimuovere:
            path = os.path.join(cache_dir, f"{artista}.json")
            try:
                os.remove(path)
            except:
                pass

    return {"status": "✅ Suggerimenti aggiornati", "attivi": tutti[-5:]}

@app.route("/debug/update_suggestions/<user_id>")
def test_aggiorna(user_id):
    result = aggiorna_suggerimenti(user_id)
    return jsonify(result)

@app.route("/suggested_albums/<user_id>")
def suggerisci_album(user_id):
    token = get_spotify_token()
    if not token:
        return jsonify({"error": "Token Spotify mancante"}), 500

    try:
        res = suggerimenti_per_artista(user_id)
        if isinstance(res, tuple):
            suggeriti = res[0].get_json()
        else:
            suggeriti = res.get_json()
    except Exception as e:
        print(f"❌ Errore nel recupero suggeriti: {e}")
        return jsonify({"error": "Errore suggerimenti"}), 500

    albums = []
    visti_album = set()

    for artista, artist_suggestions in suggeriti.items():
        for a in artist_suggestions:
            nome_artista = a.get("name")

            try:
                r = requests.get(
                    "https://api.spotify.com/v1/search",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "q": nome_artista,
                        "type": "album",
                        "limit": 20,
                        "offset": random.randint(0, 20)  # 🔁 più varietà!
                    }
                )
                data = r.json()
                items = data.get("albums", {}).get("items", [])

                random.shuffle(items)

                for album in items:
                    nome_album = album["name"]
                    if nome_album in visti_album:
                        continue

                    albums.append({
                        "album": nome_album,
                        "artist": album["artists"][0]["name"],
                        "cover": album["images"][0]["url"] if album.get("images") else "img/note.jpg",
                        "spotify_url": album.get("external_urls", {}).get("spotify", "")
                    })
                    visti_album.add(nome_album)

            except Exception as e:
                print(f"⚠️ Errore richiesta album per {nome_artista}: {e}")

    random.shuffle(albums)      # 🔁 mescola tutta la lista
    albums = albums[:10]        # ✅ mostra solo 10 album finali
    print("✅ Album suggeriti (totale):", len(albums))
    return jsonify(albums)


# ============================
# 👤 Gestione utenti
# ============================

@app.route("/user/<user_id>", methods=["GET"])
def get_user(user_id):
    """Recupera i dati utente da Supabase, oppure lo crea se non esiste"""
    try:
        response = supabase.table("users").select("*").eq("id", user_id).execute()
        if response.data:
            return jsonify(response.data[0])
        else:
            # Se non esiste lo creo "vuoto"
            new_user = {
                "id": user_id,
                "likedSongs": [],
                "playlists": [],
                "searchHistory": [],
                "suggestedAlbums": []
            }
            supabase.table("users").insert(new_user).execute()
            return jsonify(new_user)
    except Exception as e:
        print(f"❌ Errore get_user: {e}")
        return jsonify({"error": "Errore nel recupero utente"}), 500


@app.route("/user/<user_id>", methods=["PUT"])
def update_user(user_id):
    """Aggiorna o crea i dati utente su Supabase"""
    data = request.json
    try:
        response = supabase.table("users").upsert(data, on_conflict=["id"]).execute()
        return jsonify({"status": "✅ Utente aggiornato", "data": response.data})
    except Exception as e:
        print(f"❌ Errore update_user: {e}")
        return jsonify({"error": "Errore aggiornamento utente"}), 500
