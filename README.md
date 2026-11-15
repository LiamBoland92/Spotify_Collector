# Spotify Collector

Adds every song I listen to on Spotify over a time window into one playlist.

## One-time setup

1. Install Python 3.11+ and run `pip install -r requirements.txt`.
2. Create an app at https://developer.spotify.com/dashboard
   - Redirect URI: `http://127.0.0.1:8888/callback` (exactly)
   - API: Web API
   - The account that owns the app needs Spotify Premium.
3. Save the app's Client ID (PowerShell, then open a new window):
   ```
   setx SPOTIFY_CLIENT_ID "your_client_id"
   ```

The first run opens a browser to log in. The token is saved in
`spotify_token.json` (git-ignored) and renews itself.

## Collect songs going forward

```
python spotify_collector.py watch --playlist "Fall 2026" --interval 30
python spotify_collector.py watch --playlist "Fall 2026" --until 2026-12-15
python spotify_collector.py watch --playlist "Fall 2026" --once
```

- Runs until the PowerShell window is closed (or until `--until`).
- `--once` checks one time and exits (use with Task Scheduler).
- `--start 2026-11-14T13:30` includes plays from before the first run.
- Songs are added once each; `--allow-dupes` adds every play.
- Progress is saved per playlist in `spotify_state.json` (git-ignored),
  so the same command picks up where it left off.

**Limit:** Spotify only exposes the last 50 plays, so the script must check
at least every ~2 hours of listening or older plays are lost.

## Collect songs from the past

Request "Extended streaming history" from Spotify's account privacy page,
then:

```
python spotify_collector.py import --playlist "Summer 2026" --start 2026-06-01 --end 2026-08-31 --files "Streaming_History_Audio_*.json"
```

## Troubleshooting

- `client_id: Invalid` - the Client ID isn't set or is wrong.
- 403 creating a playlist - make it in Spotify and use `--playlist-id <id>`.
- "User not registered" - add yourself under User Management on the dashboard.

## 1.0: First version

- Watch mode checks your Spotify recently played list on a timer and adds new songs to a playlist.
- Import mode builds a playlist from a past time window using Spotify’s Extended Streaming History export, skipping plays under 30 seconds.
   - It finds your playlist by name, or creates it if you don’t have one, and --playlist-id lets you use a    specific playlist instead.
-No duplicate songs by default, including songs you added by hand; --allow-dupes turns that off.
-Songs are added in the order you played them.
-You log in to Spotify through your browser once, and the login renews automatically after that (no client secret needed).
-It uses Spotify’s API endpoints as they work since the February 2026 changes.
-It retries automatically when Spotify limits requests or has server errors.
      Options: --start, --until, --interval and --once.

### 1.1: Fixes

- Fixed a crash on Windows when no `--until` date was given.
- The start time is saved for each playlist, so repeated `--once` runs (like Task Scheduler) no longer skip plays from before each run.
- The wait between checks uses the real clock, so time asleep counts and a check happens within about 30 seconds of the laptop waking.

**TL;DR:** The script checks the computer's clock to decide when it's time for the next update, so sleep time counts.

### 1.2: Artists and wrap-up

- Each new song prints with its artists, for example `+ Disco 2000 - Pulp`.
- Each check line shows how many plays it saw and how many new songs it added.
- Pressing Ctrl+C, or reaching the `--until` date, shows a wrap-up instead of an error traceback. The wrap-up shows:
  - plays and new songs this session
  - total plays and how many different songs
  - total listening time
  - top 3 artists
  - most-repeated song
  - number of different artists
  - peak listening hour
- A new `stats` command shows the wrap-up anytime, even while the collector is running.
- Stats count every play, including repeats, are saved per playlist, and add up across restarts. They start counting from 1.2.
- Pressing Ctrl+C runs one last check before the wrap-up, so the playlist and stats are complete. Press Ctrl+C again to skip it.
- Checks are safe to interrupt: nothing is saved unless the playlist update succeeds.

TLDR: No longer ends in an error message. Wraps up with a full session breakdown with details.

## Acknowledgements
This was created while procrastinating studying for physics. Please bear with me on the shitty instructions; I am hoping to improve this sooner rather than later. Claude was used for most of this too, so again, forgive me for my sins.
