from flask import Flask, jsonify, request, send_file
import os
import json
import genera_playlist_auto
from flask_cors import CORS

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
    timestamp = data.get("timestamp", "")

    if not user_id or not song_file:
        return jsonify({"error": "Dati incompleti"}), 400

    os.makedirs("ascolti", exist_ok=True)
    ascolti_path = f"ascolti/{user_id}.json"

    ascolti = []
    if os.path.exists(ascolti_path):
        with open(ascolti_path, "r") as f:
            ascolti = json.load(f)

    ascolti.append({"songFile": song_file, "timestamp": timestamp})
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
