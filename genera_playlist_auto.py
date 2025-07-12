import json
import os
import re
import random
from collections import defaultdict
from PIL import Image

# === CONFIG ===
SONGS_FILE = "songs.json"
PLAYLIST_FOLDER = "playlist_utenti"  # cartella per playlist utente

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

def smart_shuffle(songs):
    if not songs:
        return []
    result = [songs.pop(0)]
    while songs:
        for i, song in enumerate(songs):
            if song["album"] != result[-1]["album"]:
                result.append(songs.pop(i))
                break
        else:
            result.append(songs.pop(0))
    return result

def create_playlist_cover(tracks, output_path):
    covers = []
    for song in tracks:
        path = song.get("cover", "")
        if os.path.exists(path):
            covers.append(Image.open(path))
        if len(covers) == 4:
            break

    if not covers:
        return ""

    collage = Image.new("RGB", (300, 300))
    size = (150, 150)

    for i, img in enumerate(covers):
        img = img.resize(size)
        x = (i % 2) * 150
        y = (i // 2) * 150
        collage.paste(img, (x, y))

    collage.save(output_path)
    return output_path

# === FUNZIONE PRINCIPALE ===
def genera_playlist_per_utente(user_id):
    if not os.path.exists(SONGS_FILE):
        print(f"❌ File '{SONGS_FILE}' non trovato.")
        return []

    with open(SONGS_FILE, "r", encoding="utf-8") as f:
        songs = json.load(f)

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
    os.makedirs(PLAYLIST_FOLDER, exist_ok=True)
    os.makedirs(f"{PLAYLIST_FOLDER}/covers", exist_ok=True)

    for name, files in playlist_map.items():
        if len(files) >= 3:
            tracks = [s for s in songs if s["file"] in files]
            shuffled = smart_shuffle(tracks.copy())

            # Genera cover dinamica
            cover_name = f"{user_id}_{name.replace(':', '_').replace(' ', '_')}.jpg"
            cover_path = f"{PLAYLIST_FOLDER}/covers/{cover_name}"
            cover = create_playlist_cover(shuffled, cover_path)

            playlist_output.append({
                "name": name,
                "description": f"Playlist generata automaticamente: {name}",
                "tracks": [s["file"] for s in shuffled],  # ✅ SOLO path, non oggetti completi
                "cover": f"/cover/{user_id}/{cover_name}" if os.path.exists(cover_path) else ""
            })

    # ✅ Salva su file
    user_playlist_path = os.path.join(PLAYLIST_FOLDER, f"{user_id}.json")
    with open(user_playlist_path, "w", encoding="utf-8") as f:
        json.dump(playlist_output, f, indent=2, ensure_ascii=False)

    print(f"✅ Playlist per '{user_id}' salvate in '{user_playlist_path}'")
    return playlist_output

# === DEFAULT ===
def main():
    return genera_playlist_per_utente("default")
