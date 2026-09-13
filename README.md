# Remote .bat Runner

Trigger a Windows `.bat` file on your laptop from your phone with a single tap,
and peek at the most recently downloaded files — even when you're away from
home. No port forwarding, no VPN.

A tiny Flask web app on the laptop exposes:

- **`/`** — a big green **RUN** button that starts your `.bat`.
- **`/files`** — a list of the most recently modified files (e.g. PDFs) and
  folders at the top level of a chosen directory (e.g. `G:\` or your Downloads
  folder). Optional — disabled by default.

Both routes run in the same Python process and share the same
[ngrok](https://ngrok.com) tunnel. Add each URL to your phone's home screen
as a PWA and you'll have two 1-tap icons.

## How it works

```
 Phone (browser/PWA)  ──HTTPS──▶  ngrok  ──▶  Flask (localhost:5000)  ──▶  your .bat
```

- The URL contains a secret token; without it the page returns 404.
- All traffic is end-to-end over ngrok's HTTPS tunnel.
- The laptop only exposes the port to ngrok, not to the open internet.

## Requirements

- Windows 10/11 laptop that stays powered on (screen can be locked — sleep must be disabled).
- [Python 3.10+](https://www.python.org/downloads/)
- Free [ngrok account](https://dashboard.ngrok.com/signup) (for the authtoken and
  one free static "dev domain").

## Setup

```cmd
git clone https://github.com/YOUR_USERNAME/remote-bat-runner.git
cd remote-bat-runner
pip install -r requirements.txt
```

1. **Copy the config template and edit it:**

   ```cmd
   copy config.example.py config.py
   ```

   Edit `config.py`:
   - `BAT_PATH` — absolute path to the `.bat` file you want to run.
   - `NGROK_DOMAIN` — optional. Paste your free static domain from
     [dashboard.ngrok.com/domains](https://dashboard.ngrok.com/domains)
     (e.g. `"your-name.ngrok-free.dev"`) so the URL stays the same across restarts.
     Leave as `None` to get a random URL each launch.
   - `SCAN_ROOT` — optional. Set to a folder path (e.g. `r"G:\\"` or your
     Downloads folder) to enable the `/files` page. Leave as `None` to disable.
     Tweak `SCAN_FILE_EXTS`, `SCAN_FILE_LIMIT`, `SCAN_FOLDER_LIMIT` to taste.

2. **Add your ngrok authtoken.** Grab it from
   [dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
   and save it to `ngrok_token.txt` (one line, no quotes). Alternatively set
   the `NGROK_AUTHTOKEN` environment variable.

3. **Generate the PWA icons** (one-time):

   ```cmd
   python make_icons.py
   ```

4. **Run it:**

   ```cmd
   start.bat
   ```

   The console prints both URLs:

   ```
   PUBLIC URLs (open on phone, then Add to Home Screen):
     RUN button page : https://your-name.ngrok-free.dev/?k=<secret>
     Recent files    : https://your-name.ngrok-free.dev/files?k=<secret>
   ```

5. **On your phone:** open each URL in Chrome/Safari → accept the ngrok warning
   on first visit → browser menu → **Add to Home Screen**. You now have one
   icon for the RUN button and (optionally) a second icon for the recent-files
   list.

## Keeping the laptop awake

Screen locked is fine — the server keeps running. Sleep/hibernate is not. Run
once, as admin if needed:

```cmd
powercfg /change standby-timeout-ac 0
powercfg /change standby-timeout-dc 0
powercfg /change hibernate-timeout-ac 0
powercfg /change hibernate-timeout-dc 0
```

To also ignore the lid-close action on a laptop:

```cmd
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setdcvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
powercfg /setactive SCHEME_CURRENT
```

## Security notes

- The URL-embedded `?k=<secret>` is the only thing protecting your endpoint.
  Don't share the full URL publicly — treat it like a password.
- `secret.txt` is auto-generated on first run. Delete it to rotate the secret.
- `config.py`, `ngrok_token.txt`, `secret.txt`, and `current_url.txt` are in
  `.gitignore` — never commit them.
- The `/run` endpoint only starts the `.bat` configured in `config.py`. It does
  not accept arbitrary commands from the client.

## Extending

- **Multiple scripts.** Turn `BAT_PATH` into a dict like
  `{"pdf": r"D:\...\a.bat", "backup": r"D:\...\b.bat"}`, map routes
  `/run/<name>`, and add more buttons to `templates/index.html`.
- **Recursive scan.** `_latest_pdfs` / `_latest_folders` in `app.py` use
  `os.scandir` (top-level only) for speed. Swap to `os.walk` if you want to
  recurse — but cap the depth and add a time budget; scanning a full drive
  can be very slow.

## License

MIT

## Added: morning PDF count (05:00-08:00)

The `/files` page now shows a highlighted total for PDFs downloaded today in the
configured morning window. The default window is **05:00 <= time < 08:00**.

The counter always checks PDFs still present at the top level of `SCAN_ROOT`.
It also recursively checks top-level workflow folders whose names contain
`temp`, `tempor`, or `merge`, so files that were moved after download continue
to be counted. Duplicate copies are de-duplicated by filename and SHA-256 content digest.
Modification time is the download-completion proxy: the actual downloader uses
`shutil.copy2` for backups and moves source files without changing that timestamp.
Creation time changes on copying and is not used.

For maximum accuracy, configure the exact workflow folders in your local
`config.py` (this file remains untracked):

```python
DAILY_PDF_COUNT_START_HOUR = 5
DAILY_PDF_COUNT_END_HOUR = 8
DAILY_PDF_COUNT_ROOTS = (
    r"G:\\Temp",
    r"G:\\Temporare",
    r"G:\\PDF_Merge",
)
```

Only put folders that contain the **source downloaded PDFs** in that tuple. If a
folder contains newly generated merged PDFs too, excluding that folder prevents
those generated outputs from inflating the download count.

## Added: open ChatGPT from the phone

A new protected page is available at:

```text
/chatgpt?k=<same-secret>
```

Tap **OPEN CHATGPT** to start or activate the ChatGPT Windows app in the current
logged-in Windows desktop session. The implementation is in
`scripts/open_chatgpt.ps1`; it dynamically resolves the installed ChatGPT app
instead of hard-coding a package ID.

The public ChatGPT URL is also written as the third line in `current_url.txt`.

## Surviving Windows Update restarts

There are two separate pieces:

1. **Automatic Windows logon** — run `scripts/setup_autologon.ps1` once while
   physically at the laptop. It downloads Microsoft's official Sysinternals
   Autologon tool and opens its local GUI. Enter the Windows password there and
   click **Enable**. The password is not put in this repository, `config.py`,
   GitHub, or the mobile web page.
2. **Start Arcanum after logon** — run `scripts/setup_runner_at_logon.ps1` once.
   It registers a Scheduled Task named `RemoteBatRunner-AtLogon`, which starts
   Python directly (no `pause`) 30 seconds after that Windows user logs in.
   It restarts on failure and prevents duplicate task instances. This starts the
   control server and ngrok; the existing download schedule remains responsible
   for starting the downloader.

After those are configured, the recovery chain is:

```text
Windows Update restart
  -> Windows Autologon
  -> RemoteBatRunner-AtLogon task
  -> python app.py
  -> Flask + ngrok
  -> phone pages become reachable again
  -> /chatgpt button can start ChatGPT
```

### Why there is no remote "type my Windows password" web page

The Windows sign-in screen runs on the Windows secure desktop. A normal Flask,
Python, PowerShell, or browser process cannot reliably inject Enter/password/
Enter into that secure screen. More importantly, sending the Windows password
through an ngrok/GitHub page would create an unnecessary credential exposure.
The one-time local Autologon configuration is the reliable approach for an
unattended laptop.

## Verified Windows workflow and privacy

Local inspection found the source backups in `G:/Temporare`, created with
`shutil.copy2`, and source segments named `__pagesN-M.pdf`. Use
`DAILY_PDF_NAME_PATTERN = r"__pages\d+-\d+\.pdf$"` to exclude merged outputs.
The actual backup directory was empty after cleanup on 2026-09-12. Optional
`DAILY_PDF_LOG_GLOBS` recovers unique names from positive-size `Confirmat pe disk`
records in existing batch logs, using the batch's local `Data:` timestamps
(month/day/year). Only completed sessions wholly within the window are accepted;
a session spanning 05:00 or 08:00 cannot supply exact per-download times.
Disk copies already represented by those log names are not counted again.
Deleted files without a usable log cannot be reconstructed. For 2026-09-12 the
available completed session gives 25 unique confirmed source downloads.

The private `?k=` entry link now establishes an HttpOnly, Secure, SameSite cookie
and redirects to a clean URL. Use HTTPS through ngrok. Templates contain no
server key, POSTs require a custom request header, responses are no-store and
no-referrer, and local access logging/ngrok request inspection are disabled.
Private links remain only in the ignored local `current_url.txt`; never publish
that file. Anyone possessing the entry link can operate the runner.

`setup_autologon.ps1` checks the Microsoft digital signature before opening the
local credential dialog. Administrators can recover an Autologon LSA secret;
configure automatic sign-in only on the intended private laptop.

Validation: `python -m unittest discover -s tests -v`. Test launches are mocked;
Windows foreground activation and a full reboot require local verification.

## See and control the local ChatGPT window from a phone

Open `/remote?k=<same-private-key>` or use **Controlează ChatGPT** on the home
page. Select the ChatGPT window, activate it, and click the message field in
the image. **Introdu textul** types Unicode text into the focused field;
**Trimite / Enter** submits separately. Newlines are flattened to spaces so
typing alone never submits a message. Enable the three-second refresh to see
responses, or enlarge the image and pan on a small screen.

This is a user-operated experimental window remote control, not a separate AI
conversation or an automatic idle detector. It only accepts visible windows
owned by `ChatGPT.exe`, which is the installed app on this laptop. Windows must
be logged in and unlocked. Input is rejected if the target window moved, lost
foreground, is covered at the click point, or if the snapshot expired. Snapshots
are in memory, expire after 20 seconds and are scoped to the browser session;
each action consumes its snapshot token. There is no arbitrary shell or hotkey
endpoint. Anyone with the private runner link can operate this window.

TeamViewer remains the second option for full desktop control. Install
**TeamViewer Remote Control** on the phone and use the laptop's ID and current
password shown in TeamViewer, or the already configured account. No TeamViewer
password is stored in this project or its web page. Account sign-in and the
first phone connection must be completed by the user. The remote page includes
links to the Android and iPhone apps.

Validation covers authentication, session-isolated/expiring/single-use snapshot
tokens, Unicode insertion without Enter, invalid input rejection, and a real
Windows screenshot. Typing/submitting in the user's live conversation is left
for the user's phone test to avoid sending an unintended message.
