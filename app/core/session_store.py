import json
import os

STORE_FILE = "active_threads.json"

def save_active_thread(phone: str, thread_id: str):
    threads = get_all_threads()
    threads[phone] = thread_id
    with open(STORE_FILE, "w") as f:
        json.dump(threads, f, indent=4)

def get_active_thread(phone: str) -> str | None:
    threads = get_all_threads()
    return threads.get(phone)

def get_all_threads() -> dict:
    if not os.path.exists(STORE_FILE):
        return {}
    try:
        with open(STORE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}