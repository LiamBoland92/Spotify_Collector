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

## Update 1.1
It now responds to the computer's time, not how long PowerShell has actually been running

## Acknowledgements
This was created while procrastinating studying for physics. Please bear with me on the shitty instructions; I am hoping to improve this sooner rather than later. Claude was used for most of this too, so again, forgive me for my sins.
