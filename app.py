from flask import Flask, jsonify, request, send_file, send_from_directory
import os
import json
import genera_playlist_auto
import requests
from datetime import datetime, timedelta, timezone
import random
from supabase import create_client, Client
from flask_cors import CORS
import time
import jwt

# ✅ Forza modalità sviluppo
os.environ["FLASK_ENV"] = "development"
print("DEBUG → FLASK_ENV:", os.environ.get("FLASK_ENV"))

# ========================
# 🌱 Carica variabili ambiente (.env)
# ========================
from dotenv import load_dotenv
import pathlib

# Percorso assoluto del file .env
env_path = pathlib.Path(__file__).parent / ".env"

print("DEBUG → Percorso previsto .env:", env_path)

# Carica il file .env e mostra esito
if load_dotenv(dotenv_path=env_path):
    print("✅ File .env caricato correttamente da:", env_path)
else:
    print("⚠️ ATTENZIONE: impossibile caricare il file .env (controlla percorso e nome)")

# Mostra valori per debug
print("DEBUG SUPABASE_URL:", os.getenv("SUPABASE_URL"))
print("DEBUG SUPABASE_KEY:", "✔️ Caricata" if os.getenv("SUPABASE_KEY") else "❌ Non trovata")

# ========================
# 🔑 Supabase
# ========================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# 👀 Debug: mostra il valore esatto (inclusi caratteri invisibili)
print("DEBUG → SUPABASE_URL (repr):", repr(SUPABASE_URL))
print("DEBUG → Lunghezza KEY:", len(SUPABASE_KEY))
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========================
# 🔑 API esterne
# ========================
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY")

# ========================
# 🚀 Flask App
# ========================
app = Flask(__name__)



## ========================
# 🌍 CORS
# =========================

# ✅ Configura CORS correttamente per origini specifiche
CORS(
    app,
    resources={r"/*": {"origins": [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://playlist-frontend.onrender.com"
    ]}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["Content-Type", "Authorization"],
)

# ✅ Forza gli header CORS anche dopo la risposta
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://playlist-frontend.onrender.com"
    ]:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# ✅ Gestione preflight OPTIONS
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        origin = request.headers.get("Origin")
        if origin in [
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "https://playlist-frontend.onrender.com"
        ]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        return response, 200

# ========================
# 📂 Crea cartelle necessarie
# ========================
os.makedirs("ascolti", exist_ok=True)
os.makedirs("suggestions_cache", exist_ok=True)

# ========================
# 🏠 Rotte base
# ========================

@app.route("/")
def home():
    return "🎶 Playlist Backend attivo!"

@app.route("/generate")
def generate():
    playlist = genera_playlist_auto.main()
    if playlist:
        return jsonify({"status": "✅ Playlist generate con successo", "count": len(playlist)})
    return jsonify({"error": "❌ Errore nella generazione playlist"}), 500

@app.route("/playlists", methods=["GET", "OPTIONS"])
def playlists():
    if os.path.exists("playlist_auto.json"):
        return send_file("playlist_auto.json", mimetype="application/json")
    return jsonify({"error": "File playlist_auto.json non trovato"}), 404

@app.route("/songs", methods=["GET", "OPTIONS"])
def get_songs():
    if os.path.exists("songs_min2.json"):
        return send_file("songs_min2.json", mimetype="application/json")
    return jsonify({"error": "songs_min2.json non trovato"}), 404# ============================
# ⬇️ Tutto il resto del tuo codice invariato
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


@app.route("/recently-played/<user_id>", methods=["GET", "POST", "OPTIONS"])
def recently_played(user_id):
    """Gestisce ascolti recenti dell'utente: lettura (GET) o aggiunta (POST)"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200  # 👈 Aggiunto
    try:
        if request.method == "POST":
            data = request.json or {}
            entry = {
                "type": data.get("type"),
                "name": data.get("name"),
                "song_file": data.get("songFile"),
                "artist": data.get("artist"),
                "album": data.get("album", ""),
                "timestamp": datetime.utcnow().isoformat()
            }

            # 🔹 Salva nel log di ascolto (tabella listening_history)
            try:
                supabase.table("listening_history").insert({
                    "user_id": user_id,
                    "artist": entry["artist"],
                    "album": entry["album"],
                    "song_file": entry["song_file"],
                    "timestamp": entry["timestamp"]
                }).execute()
            except Exception as e:
                print(f"⚠️ Errore salvataggio listening_history: {e}")

            # 🔹 Aggiorna campo recentlyPlayed dell'utente
            user_resp = supabase.table("users").select("data").eq("id", user_id).execute()
            current_data = (user_resp.data[0].get("data") if user_resp.data else {}) or {}

            recently_played = current_data.get("recentlyPlayed", [])
            recently_played = [e for e in recently_played if e.get("name") != entry["name"]]
            recently_played.insert(0, entry)
            recently_played = recently_played[:8]

            current_data["recentlyPlayed"] = recently_played
            supabase.table("users").upsert({"id": user_id, "data": current_data}).execute()

            return jsonify({"status": "✅ Aggiornato recentlyPlayed", "data": recently_played})

        # 🔹 Metodo GET → restituisce ultimi ascolti recenti
        response = supabase.table("listening_history") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("timestamp", desc=True) \
            .limit(20) \
            .execute()
        return jsonify(response.data or [])

    except Exception as e:
        print(f"❌ Errore recently_played: {e}")
        return jsonify({"error": "Errore gestione recentlyPlayed"}), 500


@app.route("/playlists/<user_id>", methods=["GET", "OPTIONS"])
def playlist_personalizzata(user_id):
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200  # 👈 Aggiunto

    try:
        path = f"playlist_utenti/{user_id}.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return jsonify({"autoPlaylists": data})

        # Nessun file → array vuoto
        return jsonify({"autoPlaylists": []})
    except Exception as e:
        print(f"❌ Errore playlist_personalizzata: {e}")
        return jsonify({"autoPlaylists": []}), 200

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

@app.route("/debug/ascolti/<user_id>", methods=["GET", "OPTIONS"])
def debug_ascolti(user_id):
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200  # 👈 Aggiunto
    path = f"ascolti/{user_id}.json"
    if not os.path.exists(path):
        return jsonify({"status": "❌ File non trovato"}), 404

    with open(path) as f:
        data = json.load(f)
    return jsonify(data)

@app.route("/suggestions-by-artist/<user_id>", methods=["GET", "OPTIONS"])
def suggerimenti_per_artista(user_id):
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200  # 👈 Aggiunto

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

@app.route("/suggested_albums/<user_id>", methods=["GET", "OPTIONS"])
def suggerisci_album(user_id):
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200  # 👈 Aggiunto
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

@app.route("/user/<user_id>", methods=["GET", "OPTIONS"])
def get_user(user_id):
    """Recupera i dati utente da Supabase, oppure lo crea se non esiste"""

    # ✅ Gestione CORS: intercetta subito le richieste OPTIONS
    if request.method == "OPTIONS":
        response = jsonify({"status": "ok"})
        response.headers.add("Access-Control-Allow-Origin", request.headers.get("Origin", "*"))
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        response.headers.add("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        return response, 200

    try:
        response = supabase.table("users").select("*").eq("id", user_id).execute()
        print("DEBUG → Supabase response:", response)

        if response.data and len(response.data) > 0:
            user = response.data[0]
            return jsonify(user.get("data", {}))
        else:
            print(f"⚠️ Utente {user_id} non trovato, lo creo...")
            new_user_data = {
                "id": user_id,
                "name": f"User_{user_id[:4]}",
                "likedSongs": [],
                "playlists": [],
                "searchHistory": [],
                "suggestedAlbums": [],
                "autoPlaylists": [],
                "autoPlaylistsUpdatedAt": None,
                "suggestionsByArtist": {}
            }
            supabase.table("users").insert({
                "id": user_id,
                "data": new_user_data
            }).execute()
            return jsonify(new_user_data)

    except Exception as e:
        print(f"❌ Errore get_user: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/user/<user_id>", methods=["PUT", "OPTIONS"])
def update_user(user_id):
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200  # 👈 Aggiunto

    """Aggiorna o crea i dati utente su Supabase"""
    
    data_in = request.json or {}

    # 🔑 Assicuriamoci che ci sia un nome
    if "name" not in data_in or not data_in["name"]:
        data_in["name"] = f"User_{user_id[:4]}"

    payload = {
        "id": user_id,
        "data": data_in
    }

    try:
        response = supabase.table("users").upsert(payload, on_conflict="id").execute()
        return jsonify({"status": "✅ Utente aggiornato", "data": response.data})
    except Exception as e:
        print(f"❌ Errore update_user: {e}")
        return jsonify({"error": "Errore aggiornamento utente"}), 500
@app.errorhandler(Exception)
def handle_error(e):
    print("🔥 ERRORE SERVER:", e)
    return jsonify({"error": str(e)}), 500

# ========================
# 👤 AUTENTICAZIONE UTENTI
# ========================

@app.route("/register", methods=["POST"])
def register():
    """Crea un nuovo account Supabase e inizializza la tabella users"""
    data = request.json
    email = data.get("email")
    password = data.get("password")
    name = data.get("name")  # 👈 AGGIUNTO

    if not email or not password:
        return jsonify({"error": "Email e password obbligatorie"}), 400

    try:
        res = supabase.auth.sign_up({"email": email, "password": password})

        # ✅ Se l'utente è già registrato
        if "User already registered" in str(res):
            return jsonify({"error": "Utente già registrato"}), 409

        # ✅ Se la registrazione ha successo
        if hasattr(res, "user") and res.user:
            user_id = res.user.id

            # 👇 Usa il nome fornito o fallback alla parte prima della @
            user_name = name if name else email.split("@")[0]

            # ✅ Salva il record nella tabella "users"
            supabase.table("users").upsert({
                "id": user_id,
                "name": user_name,
                "playlists": [],
                "likedSongs": [],
                "searchHistory": [],
                "suggestedAlbums": [],
                "data": {
                    "email": email,
                    "name": user_name
                }
            }).execute()

            print(f"✅ Creato utente {user_name} ({user_id})")
            return jsonify({
                "message": "✅ Account creato",
                "user_id": user_id,
                "name": user_name
            }), 201

        return jsonify({"error": "Errore nella creazione dell’utente"}), 500

    except Exception as e:
        if "User already registered" in str(e):
            return jsonify({"error": "Utente già registrato"}), 409
        print("❌ Errore register:", e)
        return jsonify({"error": str(e)}), 500



@app.route("/login", methods=["POST"])
def login():
    """Login utente e ritorna JWT"""
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email e password obbligatorie"}), 400

    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        print("DEBUG → Risposta Supabase login:", res)

        token = None

        # ✅ Caso 1: oggetto con .session (vecchia versione)
        if hasattr(res, "session") and res.session:
            token = res.session.access_token

        # ✅ Caso 2: nuova struttura (res è un dict)
        elif isinstance(res, dict):
            token = res.get("session", {}).get("access_token")

        # ✅ Caso 3: fallback (alcune versioni hanno direttamente res.access_token)
        elif hasattr(res, "access_token"):
            token = res.access_token

        if token:
            return jsonify({"message": "✅ Login effettuato", "token": token}), 200

        # Se non arriva nessun token → credenziali errate
        return jsonify({"error": "Credenziali non valide"}), 401

    except Exception as e:
        print("❌ Errore login:", e)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/me", methods=["GET"])
def get_me():
    """Ritorna le informazioni dell'utente autenticato"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Token mancante"}), 401

    token = auth_header.split(" ")[1]
    try:
        # verifica token (senza chiave privata, solo decode)
        payload = jwt.decode(token, options={"verify_signature": False})
        user_id = payload.get("sub")

        res = supabase.table("users").select("*").eq("id", user_id).execute()
        user = res.data[0] if res.data else None

        if not user:
            return jsonify({"error": "Utente non trovato"}), 404

        return jsonify({"user": user}), 200

    except Exception as e:
        print("❌ Errore get_me:", e)
        return jsonify({"error": str(e)}), 401
        
@app.route("/logout", methods=["POST"])
def logout():
    """Logout locale (frontend elimina token)"""
    return jsonify({"message": "✅ Logout effettuato (token invalidato client-side)"}), 200

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))  # Render imposta PORT automaticamente
    app.run(host="0.0.0.0", port=port, debug=True)
