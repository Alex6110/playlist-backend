import json
import os
from collections import defaultdict

# === CONFIG ===
SONGS_FILE = "songs.json"
PLAYLIST_FOLDER = "playlist_utenti"  # una cartella per contenere le playlist per utente

# === UTILS ===
def normalize_artist(artist_name):
    return artist_name.strip().lower()

def normalize_genre(genre):
    return genre.strip().lower()

def normalize_year(year_str):
    try:
        return int(year_str[:4])
    except:
        return None

def get_period_label(year):
    if not year:
        return "Anni sconosciuti"
    if year < 1970:
        return "Anni '60 e prima"
    elif year < 1980:
        return "Anni '70"
    elif year < 1990:
        return "Anni '80"
    elif year < 2000:
        return "Anni '90"
    elif year < 2010:
        return "Anni 2000"
    elif year < 2020:
        return "Anni 2010"
    else:
        return "Anni 2020"

# === FUNZIONE PRINCIPALE ===
def genera_playlist_per_utente(user_id):
    if not os.path.exists(SONGS_FILE):
        print(f"❌ File '{SONGS_FILE}' non trovato.")
        return []

    with open(SONGS_FILE, "r", encoding="utf-8") as f:
        songs = json.load(f)

    # 🔁 FUTURO: filtra canzoni ascoltate da questo utente, per ora usa tutte
    playlist_map = defaultdict(list)

    for song in songs:
        if song["artist"]:
            artist_name = normalize_artist(song["artist"][0])
            playlist_map[f"Artista: {artist_name.title()}"].append(song["file"])

        if song["genre"]:
            genre = normalize_genre(song["genre"])
            playlist_map[f"Genere: {genre.title()}"].append(song["file"])

        year = normalize_year(song["year"])
        period = get_period_label(year)
        playlist_map[f"Periodo: {period}"].append(song["file"])

    playlist_output = []
    for name, files in playlist_map.items():
        if len(files) >= 3:
            playlist_output.append({
                "name": name,
                "description": f"Playlist generata automaticamente: {name}",
                "tracks": files
            })

    # 📁 Salva in file separati per utente
    os.makedirs(PLAYLIST_FOLDER, exist_ok=True)
    user_playlist_path = os.path.join(PLAYLIST_FOLDER, f"{user_id}.json")

    with open(user_playlist_path, "w", encoding="utf-8") as f:
        json.dump(playlist_output, f, indent=2, ensure_ascii=False)

    print(f"✅ Playlist per '{user_id}' salvate in '{user_playlist_path}'")
    return playlist_output

# === DEFAULT ===
def main():
    return genera_playlist_per_utente("default")
