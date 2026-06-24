import requests
import json
import time
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY   = None # for uploading to github never write your api key 
GAME_NAME = "Spring"
TAG_LINE  = "cha"
PLATFORM  = "na1"
REGION    = "americas"

HEADERS = {"X-Riot-Token": API_KEY}

# ── helpers ────────────────────────────────────────────────────────────────────

def _get(url, params=None, retries=5):
    for _ in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        except requests.exceptions.ReadTimeout:
            print(f"  [timeout] retrying in 10s...")
            time.sleep(10)
            continue
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 15)) + 2
            print(f"  [rate limit] sleeping {wait}s...")
            time.sleep(wait)
            continue
        if r.status_code == 503:
            print(f"  [503] retrying in 10s...")
            time.sleep(10)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Failed after {retries} retries: {url}")

def _sleep():
    time.sleep(1.3)   # ~46 req/min, well under 100/2min personal key limit

# ── API calls ──────────────────────────────────────────────────────────────────

def get_my_puuid():
    url = f"https://{REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{GAME_NAME}/{TAG_LINE}"
    return _get(url)["puuid"]

def get_puuid_by_riot_id(game_name, tag_line):
    url = f"https://{REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    return _get(url)["puuid"]

def get_match_ids(puuid, count=100):
    url = f"https://{REGION}.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids"
    return _get(url, params={"count": count, "queue": 1100})  # 1100 = ranked TFT

def get_match(match_id):
    url = f"https://{REGION}.api.riotgames.com/tft/match/v1/matches/{match_id}"
    return _get(url)

CHALLENGER_RIOT_IDS = [
    ("ACAD wasian",      "NA2"),
    ("ACAD Dishsoap",    "NA3"),
    ("junglebook1",      "NA1"),
    ("Msian Emilywang",  "emo"),
    ("grea",             "melt"),
    ("FNC Filup",        "TFT"),
    ("CTG Marcel P",     "NA2"),
    ("VIT setsuko",      "NA2"),
    ("CTG dankmemes01",  "001"),
    ("VIT k3soju",       "000"),
]

def get_challenger_puuids():
    """Returns list of (puuid, name) tuples."""
    results = []
    for i, (name, tag) in enumerate(CHALLENGER_RIOT_IDS):
        _sleep()
        puuid = get_puuid_by_riot_id(name, tag)
        results.append((puuid, name))
        print(f"  [{i+1}/{len(CHALLENGER_RIOT_IDS)}] {name}#{tag}")
    return results

# ── fetch helpers ──────────────────────────────────────────────────────────────

def fetch_matches_for_player(puuid, count, is_me, seen_ids, label="", player_name=""):
    _sleep()
    match_ids = get_match_ids(puuid, count)
    new_ids = [mid for mid in match_ids if mid not in seen_ids]
    print(f"  {label}: {len(new_ids)} new matches ({len(match_ids)-len(new_ids)} already cached)")

    matches = []
    for i, mid in enumerate(new_ids):
        _sleep()
        print(f"    [{i+1}/{len(new_ids)}] {mid}")
        match = get_match(mid)
        match["_my_puuid"]    = puuid
        match["_is_me"]       = is_me
        match["_player_name"] = player_name
        matches.append(match)
        seen_ids.add(mid)
    return matches

def load_checkpoint(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []

def save_checkpoint(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

# ── main ───────────────────────────────────────────────────────────────────────

def main():
    os.makedirs("data", exist_ok=True)

    my_checkpoint    = "data/matches.json"
    chall_checkpoint = "data/challenger_matches.json"

    # ── my games ──
    my_matches = load_checkpoint(my_checkpoint)
    my_seen    = {m["metadata"]["match_id"] for m in my_matches}

    if len(my_matches) < 100:
        print("─── Fetching my games ───")
        my_puuid = get_my_puuid()
        print(f"My PUUID: {my_puuid[:20]}...")
        new = fetch_matches_for_player(my_puuid, count=100, is_me=True,
                                       seen_ids=my_seen, label="me",
                                       player_name=GAME_NAME)
        my_matches.extend(new)
        save_checkpoint(my_checkpoint, my_matches)
        print(f"Saved {len(my_matches)} personal matches → {my_checkpoint}")
    else:
        print(f"My games already complete ({len(my_matches)} matches), skipping.")

    # ── challenger games ──
    chall_matches = load_checkpoint(chall_checkpoint)
    chall_seen    = {m["metadata"]["match_id"] for m in chall_matches}

    # also skip match IDs we already have from my own games
    all_seen = my_seen | chall_seen

    print("\n─── Fetching challenger games ───")
    challengers = get_challenger_puuids()

    player_map = {puuid: name for puuid, name in challengers}
    player_map[get_my_puuid()] = f"{GAME_NAME}#{TAG_LINE}"
    with open("data/player_map.json", "w") as f:
        json.dump(player_map, f, indent=2)
    print("Saved data/player_map.json")

    for i, (puuid, player_name) in enumerate(challengers):
        print(f"\nChallenger {i+1}/{len(challengers)}  {player_name}")
        new = fetch_matches_for_player(puuid, count=100, is_me=False,
                                       seen_ids=all_seen,
                                       label=player_name,
                                       player_name=player_name)
        chall_matches.extend(new)
        # checkpoint after every player in case of interruption
        save_checkpoint(chall_checkpoint, chall_matches)
        print(f"  Running total: {len(chall_matches)} challenger matches saved.")

    print(f"\nDone.")
    print(f"  My matches:          {len(my_matches)}")
    print(f"  Challenger matches:  {len(chall_matches)}")

if __name__ == "__main__":
    main()
