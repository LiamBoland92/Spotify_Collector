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

### 1.3: Playlist recheck and final check

- Before each update, the collector checks whether the playlist has changed and re-reads it if so, instead of only reading it at startup.
  - Songs added from another computer or by hand are no longer added again.
  - Songs removed from the playlist are added back if you play them again.
  - Uses the playlist's version number (`snapshot_id`), so an unchanged playlist costs one small request per check instead of a full re-read.
  - Running on two computers at once is now mostly safe, though running one at a time is still best.
- Pressing Ctrl+C runs one last check before the wrap-up, so the playlist and stats are complete. Press Ctrl+C again to skip it.
- Checks are safe to interrupt: nothing is saved unless the playlist update succeeds.

TLDR: You can use multiple computers that will hand off to each other. As long as they don't add songs in the same second, there should be no repeats. The program checks the entire playlists for duplicate songs. In order to stay memory efficient, the computer will only check the folder if and only if it sees that it has been edited since it last took data.

## 2.0: Raspberry Pi deployment

- The collector now runs 24/7 on a Raspberry Pi as a background service, so it no longer needs a computer left on or a PowerShell window open.
  - It starts automatically when the Pi boots and restarts itself a minute after a crash.
  - The Pi doesn't need Spotify installed. It reads your account's listening history, so it picks up plays from your phone, laptop, or any other device.
- Tested on a Raspberry Pi 3 Model B+ (1 GB) running 64-bit Raspberry Pi OS. Any Pi with Wi-Fi works.
- New `spotify-collector.service` file in the repo: a template for the Linux service. Fill in your username, Client ID, and playlist name before installing it.
- Stopping the service (`sudo systemctl stop spotify-collector`) still runs the final check and wrap-up, the same as pressing Ctrl+C.

**TL;DR:** The Pi is a tiny always-on computer that runs the collector by itself, so nothing gets missed while your laptop is asleep.

### 2.1 Setup: Flashing the SD card

- Use Raspberry Pi Imager with Raspberry Pi OS (64-bit).
- In Customisation, set a hostname, username and password, and enable SSH and Raspberry Pi Connect.
- For Wi-Fi, enter your phone hotspot, not school Wi-Fi. Imager only supports networks with a single password, so eduroam is added later.
  - iPhone hotspot names use a curly apostrophe (’) that won't match a typed one, so rename the phone to something simple like `LiamiPhone`.
  - Turn on Allow Others to Join and Maximize Compatibility, and keep the Personal Hotspot screen open while the Pi boots.
- Don't unplug the Pi during its first boot (up to 5 minutes). Interrupting it can break the setup, and the fix is reflashing the card.

### 2.2 Setup: Connecting

- SSH in from a computer on the same hotspot: `ssh USERNAME@HOSTNAME.local`.
  - If the name isn't found, run `arp -a` and connect by IP instead (`172.20.10.X` on an iPhone hotspot).
  - "Connection refused" means the first boot is still finishing.
- Update the Pi: `sudo apt update && sudo apt full-upgrade -y`, then `sudo reboot`.
- Raspberry Pi Connect (connect.raspberrypi.com) gives a remote terminal from any browser, even on networks that block SSH between devices. Check it with `rpi-connect status` before leaving the hotspot.

### 2.3 Setup: Wi-Fi

- Add networks with `nmcli`. The Pi saves them all and joins whichever is in range, preferring higher `connection.autoconnect-priority`.
- Home Wi-Fi: `sudo nmcli connection add type wifi con-name Home ifname wlan0 ssid "NAME" wifi-sec.key-mgmt wpa-psk wifi-sec.psk 'PASSWORD' connection.autoconnect-priority 20`
- Northeastern: NURes-device is preferred (register the MAC from `cat /sys/class/net/wlan0/address`), but it isn't available in every building. eduroam works everywhere:
  - `sudo nmcli connection add type wifi con-name eduroam ifname wlan0 ssid eduroam wifi-sec.key-mgmt wpa-eap 802-1x.eap peap 802-1x.phase2-auth mschapv2 802-1x.identity "USERNAME@northeastern.edu" 802-1x.password 'PASSWORD' connection.autoconnect-priority 10`
  - eduroam stores your school password on the Pi. Update it after a password change with `sudo nmcli connection modify eduroam 802-1x.password 'NEW-PASSWORD'`.
- Put passwords in single quotes so `$` and `!` aren't misread, and start the command with a space so it isn't saved in your command history.
- If the Pi can't get online, turn on your phone hotspot. It falls back to it so you can get back in.

### 2.4 Setup: Installing the collector

- Clone into a lowercase folder (Linux folder names are case-sensitive): `git clone https://github.com/LiamBoland92/Spotify_Collector.git Spotify_collector`
- Install the library with `sudo apt install -y python3-requests` (Raspberry Pi OS blocks system-wide `pip install`).
- Copy `spotify_token.json` from a computer where the collector already works, since the Pi has no browser for the login.
  - On Windows: `Get-Content spotify_token.json | Set-Clipboard`
  - On the Pi, run `bind 'set enable-bracketed-paste off'`, then `cat > ~/Spotify_collector/spotify_token.json`, paste, press Enter, then Ctrl+D.
  - Check it with `python3 -m json.tool ~/Spotify_collector/spotify_token.json > /dev/null && echo OK`.
  - The `bind` line stops the terminal from saving invisible paste markers into the file (a stray `~` is the giveaway).
- Never share the token. If it leaks, remove the app's access at spotify.com/account (Manage apps) and log in again for a new one.
- After copying, stop the collector on your other computers so they don't share one token.

### 2.5 Setup: Running the service

- Copy the edited template to `/etc/systemd/system/spotify-collector.service`, then run each command on its own line:
  - `sudo systemctl daemon-reload`
  - `sudo systemctl enable --now spotify-collector`
- Check it: `systemctl status spotify-collector` should say **active (running)**.
- Recent output: `journalctl -u spotify-collector -n 20`. Live output: `journalctl -u spotify-collector -f`.
- Stats: `SPOTIFY_CLIENT_ID=YOUR_CLIENT_ID python3 spotify_collector.py stats --playlist "Fall 2026"` (the Client ID is only set inside the service, so pass it here).
- Switch playlists: `sudo sed -i 's/--playlist "Old"/--playlist "New"/' /etc/systemd/system/spotify-collector.service`, then `sudo systemctl daemon-reload` and `sudo systemctl restart spotify-collector`.
- Update the code: `cd ~/Spotify_collector && git pull && sudo systemctl restart spotify-collector`.
- Shut down before unplugging: `sudo shutdown now`.

## Acknowledgements
This was created while procrastinating studying for physics. Please bear with me on the shitty instructions; I am hoping to improve this sooner rather than later. Claude was used for most of this too, so again, forgive me for my sins.
