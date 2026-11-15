#!/usr/bin/env python3
"""
spotify_collector.py - put every song you listen to over a time window into one playlist.

Two modes:
  watch   Polls your "recently played" feed every N minutes and adds new plays.
          Use this for a window that is now or in the future.
  import  Reads Spotify's Extended Streaming History export (JSON files you request
          from your account's privacy page). Use this for a window in the past.

Setup:
  pip install requests
  export SPOTIFY_CLIENT_ID=your_client_id     (Windows: set SPOTIFY_CLIENT_ID=...)

Examples:
  python spotify_collector.py watch  --playlist "Fall 2026" --until 2026-12-15
  python spotify_collector.py watch  --playlist "Fall 2026" --once        (for cron)
  python spotify_collector.py import --playlist "Summer 2026" \
         --start 2026-06-01 --end 2026-08-31 --files "Streaming_History_Audio_*.json"

Written against the Spotify Web API as of the February 2026 changes
(POST /me/playlists, /playlists/{id}/items). Needs Python 3.11+.
"""
import argparse
import base64
import glob
import hashlib
import http.server
import json
import os
import secrets
import sys
import time
import urllib.parse
import webbrowser
from datetime import datetime, timedelta, timezone

import requests

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
REDIRECT_URI = "http://127.0.0.1:8888/callback"   # must match your app's dashboard exactly
SCOPES = ("user-read-recently-played playlist-read-private "
          "playlist-modify-private playlist-modify-public")
API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"
TOKEN_FILE = "spotify_token.json"
STATE_FILE = "spotify_state.json"


# ---------------------------------------------------------------- auth (PKCE)

def _save_token(tok):
    tok["expires_at"] = time.time() + tok["expires_in"] - 60
    with open(TOKEN_FILE, "w") as f:
        json.dump(tok, f)


def _login():
    """One-time browser login. Uses PKCE, so no client secret is needed."""
    if not CLIENT_ID:
        sys.exit("Set the SPOTIFY_CLIENT_ID environment variable first.")
    verifier = secrets.token_urlsafe(64)[:128]
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "client_id": CLIENT_ID, "response_type": "code", "redirect_uri": REDIRECT_URI,
        "scope": SCOPES, "code_challenge_method": "S256",
        "code_challenge": challenge, "state": state,
    })

    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Logged in - you can close this tab.</h2>")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 8888), Handler)
    print("Opening your browser to log in to Spotify. If it doesn't open, visit:\n" + url)
    webbrowser.open(url)
    while "code" not in result and "error" not in result:
        server.handle_request()
    server.server_close()

    if "error" in result:
        sys.exit(f"Login failed: {result['error']}")
    if result.get("state") != state:
        sys.exit("Login failed: state mismatch.")

    r = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code", "code": result["code"],
        "redirect_uri": REDIRECT_URI, "client_id": CLIENT_ID, "code_verifier": verifier,
    }, timeout=30)
    r.raise_for_status()
    _save_token(r.json())


def get_token():
    if not os.path.exists(TOKEN_FILE):
        _login()
    with open(TOKEN_FILE) as f:
        tok = json.load(f)
    if time.time() >= tok["expires_at"]:
        r = requests.post(TOKEN_URL, data={
            "grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
            "client_id": CLIENT_ID,
        }, timeout=30)
        if r.status_code != 200:           # refresh token revoked/expired -> log in again
            os.remove(TOKEN_FILE)
            return get_token()
        new = r.json()
        new.setdefault("refresh_token", tok["refresh_token"])
        _save_token(new)
        tok = new
    return tok["access_token"]


# ---------------------------------------------------------------- API helpers

def api(method, path, **kwargs):
    url = path if path.startswith("http") else API + path
    for attempt in range(6):
        r = requests.request(method, url, timeout=30,
                             headers={"Authorization": f"Bearer {get_token()}"}, **kwargs)
        if r.status_code == 429:           # rate limited
            time.sleep(int(r.headers.get("Retry-After", 5)) + 1)
            continue
        if r.status_code >= 500:           # Spotify hiccup
            time.sleep(2 ** attempt)
            continue
        if not r.ok:
            raise RuntimeError(f"{method} {url} -> {r.status_code}: {r.text}")
        return r.json() if r.content else None
    raise RuntimeError(f"{method} {url} kept failing; giving up.")


def find_or_create_playlist(name):
    me = api("GET", "/me")["id"]
    url = "/me/playlists?limit=50"
    while url:
        page = api("GET", url)
        for p in page["items"]:
            if p and p["name"] == name and p["owner"]["id"] == me:
                return p["id"]
        url = page.get("next")
    created = api("POST", "/me/playlists", json={
        "name": name, "public": False,
        "description": "Auto-collected by spotify_collector.py",
    })
    print(f"Created playlist '{name}'.")
    return created["id"]


def playlist_uris(pid):
    uris, url = set(), f"/playlists/{pid}/items?limit=50"
    while url:
        page = api("GET", url)
        for entry in page["items"]:
            obj = entry.get("item") or entry.get("track")   # field was renamed in 2026
            if obj and obj.get("uri"):
                uris.add(obj["uri"])
        url = page.get("next")
    return uris


def add_to_playlist(pid, uris):
    for i in range(0, len(uris), 100):                     # API max is 100 per request
        api("POST", f"/playlists/{pid}/items", json={"uris": uris[i:i + 100]})


# ---------------------------------------------------------------- utilities

def parse_iso(s):
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.astimezone() if dt.tzinfo is None else dt


def parse_when(s, end_of_day=False):
    """'2026-12-15' or '2026-12-15T18:00', interpreted in your local time zone."""
    dt = datetime.fromisoformat(s)
    if end_of_day and len(s) == 10:
        dt += timedelta(days=1)            # a bare end date includes that whole day
    return dt.astimezone()


def to_ms(dt):
    return int(dt.timestamp() * 1000)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def resolve_playlist(args):
    return args.playlist_id or find_or_create_playlist(args.playlist)


# ---------------------------------------------------------------- watch mode

def poll_once(pid, state, start_ms, end_ms, seen):
    cursors = state.setdefault("cursors", {})
    cursor = max(cursors.get(pid, 0), start_ms)
    data = api("GET", "/me/player/recently-played", params={"limit": 50, "after": cursor})
    items = (data or {}).get("items", [])
    if len(items) == 50:
        print("  Warning: 50 plays since last check (the API maximum) - some may be "
              "missed. Use a shorter --interval.")

    plays = []
    for it in items:
        track = it.get("track") or {}
        uri = track.get("uri", "")
        ms = to_ms(parse_iso(it["played_at"]))
        if uri.startswith("spotify:track:") and start_ms <= ms < end_ms:
            plays.append((ms, uri, track.get("name", "?")))
        cursor = max(cursor, ms)
    plays.sort()                           # oldest first, so the playlist is chronological

    to_add = []
    for _, uri, name in plays:
        if seen is not None:
            if uri in seen:
                continue
            seen.add(uri)
        to_add.append(uri)
        print(f"  + {name}")
    if to_add:
        add_to_playlist(pid, to_add)
    cursors[pid] = cursor
    return len(to_add)


def cmd_watch(args):
    state = load_state()
    pid = resolve_playlist(args)
    starts = state.setdefault("starts", {})
    if args.start:
        start = parse_when(args.start)
    elif pid in starts:                    # keep the first run's start time for this playlist
        start = datetime.fromisoformat(starts[pid])
    else:
        start = datetime.now().astimezone()
    starts[pid] = start.isoformat()
    save_state(state)
    end = parse_when(args.until, end_of_day=True) if args.until else datetime(9999, 12, 31, tzinfo=timezone.utc)
    seen = None if args.allow_dupes else playlist_uris(pid)

    print(f"Collecting plays from {start:%Y-%m-%d %H:%M} "
          f"until {'stopped' if not args.until else f'{end:%Y-%m-%d %H:%M}'}.")
    while True:
        try:
            n = poll_once(pid, state, to_ms(start), to_ms(end), seen)
            save_state(state)
            print(f"[{datetime.now():%H:%M}] added {n} track(s)")
        except (RuntimeError, requests.RequestException) as e:
            print(f"[{datetime.now():%H:%M}] error: {e}")
        if args.once or datetime.now().astimezone() >= end:
            break
        time.sleep(args.interval * 60)


# ---------------------------------------------------------------- import mode

def cmd_import(args):
    start = parse_when(args.start)
    end = parse_when(args.end, end_of_day=True)
    files = sorted({f for pattern in args.files for f in glob.glob(pattern)})
    if not files:
        sys.exit("No history files matched --files.")

    plays = []
    for fn in files:
        with open(fn, encoding="utf-8") as f:
            for e in json.load(f):
                uri = e.get("spotify_track_uri")
                if not uri or e.get("ms_played", 0) < args.min_seconds * 1000:
                    continue                # skips, podcasts, local files
                ts = parse_iso(e["ts"])
                if start <= ts < end:
                    plays.append((ts, uri))
    plays.sort()
    print(f"Found {len(plays)} qualifying plays in {len(files)} file(s).")

    pid = resolve_playlist(args)
    if args.allow_dupes:
        to_add = [uri for _, uri in plays]
    else:
        seen = playlist_uris(pid)
        to_add = []
        for _, uri in plays:
            if uri not in seen:
                seen.add(uri)
                to_add.append(uri)
    add_to_playlist(pid, to_add)
    print(f"Added {len(to_add)} track(s).")


# ---------------------------------------------------------------- CLI

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        g = sp.add_mutually_exclusive_group(required=True)
        g.add_argument("--playlist", help="playlist name (found or created)")
        g.add_argument("--playlist-id", help="ID of an existing playlist to use instead")
        sp.add_argument("--allow-dupes", action="store_true",
                        help="add a song every time it's played, not just once")

    w = sub.add_parser("watch", help="poll recently-played going forward")
    common(w)
    w.add_argument("--start", help="ignore plays before this (default: first run for this playlist)")
    w.add_argument("--until", help="stop after this date/time (default: run forever)")
    w.add_argument("--interval", type=float, default=20, help="minutes between checks")
    w.add_argument("--once", action="store_true", help="check once and exit (for cron)")
    w.set_defaults(func=cmd_watch)

    i = sub.add_parser("import", help="load a past window from your streaming history export")
    common(i)
    i.add_argument("--start", required=True)
    i.add_argument("--end", required=True)
    i.add_argument("--files", nargs="+", required=True, help="history JSON files or globs")
    i.add_argument("--min-seconds", type=int, default=30,
                   help="ignore plays shorter than this (default 30, Spotify's own cutoff)")
    i.set_defaults(func=cmd_import)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
