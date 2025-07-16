import os
from genera_playlist_auto import genera_playlist_per_utente

ASCOLTI_FOLDER = "ascolti"

def get_all_user_ids():
    if not os.path.exists(ASCOLTI_FOLDER):
        return []

    files = os.listdir(ASCOLTI_FOLDER)
    user_ids = [f.replace(".json", "") for f in files if f.endswith(".json")]
    return user_ids

def main():
    user_ids = get_all_user_ids()
    if not user_ids:
        print("⚠️ Nessun utente trovato in 'ascolti/'")
        return

    print(f"🎯 Genero playlist per: {user_ids}")
    for user_id in user_ids:
        genera_playlist_per_utente(user_id)

    print("✅ Playlist settimanali generate per tutti gli utenti.")

if __name__ == "__main__":
    main()

