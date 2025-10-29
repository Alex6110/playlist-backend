from supabase import create_client, Client

SUPABASE_URL = "https://uoqhmrlcswcefgvgigwt.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVvcWhtcmxjc3djZWZndmdpZ3d0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI3NjUyOTAsImV4cCI6MjA2ODM0MTI5MH0.lbB6UOQmG9aASXou8tTuk3sC9gJ7X15Nnoaq2kBsdUI"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def migrate_users():
    print("🔍 Recupero utenti da Supabase...")
    res = supabase.table("users").select("*").execute()

    updated = 0
    for user in res.data:
        user_id = user.get("id")
        name = user.get("name")

        if not name or name.strip() == "":
            # aggiungi un nome di default
            default_name = f"User_{user_id[:4]}"
            print(f"⚡ Aggiorno utente {user_id} con name='{default_name}'")

            supabase.table("users").update({"name": default_name}).eq("id", user_id).execute()
            updated += 1

    print(f"✅ Migrazione completata. Utenti aggiornati: {updated}")

if __name__ == "__main__":
    migrate_users()

