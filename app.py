"""Remote .bat runner + recent-files browser, exposed via ngrok."""
import os
import hashlib
import glob
import logging
import re
import secrets
import subprocess
import sys
from datetime import datetime, time
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, session, redirect
from pyngrok import conf, ngrok

import config

BASE_DIR = Path(__file__).resolve().parent
BAT_PATH = Path(config.BAT_PATH)
SCAN_ROOT = Path(config.SCAN_ROOT) if getattr(config, "SCAN_ROOT", None) else None
SECRET_FILE = BASE_DIR / "secret.txt"
TOKEN_FILE = BASE_DIR / "ngrok_token.txt"
URL_FILE = BASE_DIR / "current_url.txt"
CHATGPT_SCRIPT = BASE_DIR / "scripts" / "open_chatgpt.ps1"


def load_or_create_secret() -> str:
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text(encoding="utf-8").strip()
    value = secrets.token_urlsafe(24)
    SECRET_FILE.write_text(value, encoding="utf-8")
    return value


def load_ngrok_token() -> str:
    token = os.environ.get("NGROK_AUTHTOKEN")
    if token:
        return token.strip()
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    sys.exit(
        "Missing ngrok authtoken. Create ngrok_token.txt in this folder "
        "or set the NGROK_AUTHTOKEN environment variable. "
        "Get a free token at https://dashboard.ngrok.com/get-started/your-authtoken"
    )


SECRET = load_or_create_secret()
app = Flask(__name__, static_folder="static", template_folder="templates")

app.secret_key = SECRET
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict", SESSION_COOKIE_SECURE=True)
# Query credentials must never reach the development access log.
logging.getLogger("werkzeug").disabled = True

@app.before_request
def authenticate():
    if request.path.startswith("/static/") or request.path == "/manifest.webmanifest":
        return None
    key = request.args.get("k") or request.headers.get("X-Key")
    if key is not None:
        if not secrets.compare_digest(key, SECRET):
            abort(403)
        session["authorized"] = True
        if request.method == "GET" and "k" in request.args:
            return redirect(request.path)
    if not session.get("authorized"):
        abort(403)
    if request.method == "POST" and not key and request.headers.get("X-Requested-With") != "RemoteRunner":
        abort(403)

@app.after_request
def privacy_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# -- Routes ----------------------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        title=config.APP_TITLE,
        files_enabled=SCAN_ROOT is not None,
        chatgpt_enabled=CHATGPT_SCRIPT.exists(),
    )


@app.route("/run", methods=["POST"])
def run_bat():
    if not BAT_PATH.exists():
        return jsonify(ok=False, error=f"Missing file: {BAT_PATH}"), 500
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", str(BAT_PATH)],
            cwd=str(BAT_PATH.parent),
            shell=False,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        return jsonify(ok=True, message="Started")
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=str(e)), 500


@app.route("/files")
def files_page():
    if SCAN_ROOT is None:
        return "SCAN_ROOT is not configured in config.py", 500
    return render_template(
        "files.html",
        root=str(SCAN_ROOT),
        pdfs=_latest_pdfs(SCAN_ROOT, config.SCAN_FILE_LIMIT, config.SCAN_FILE_EXTS),
        folders=_latest_folders(SCAN_ROOT, config.SCAN_FOLDER_LIMIT),
        scanned_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        exts=", ".join(config.SCAN_FILE_EXTS),
        daily_pdf_count=_daily_pdf_count(),
        daily_window=_daily_pdf_window_label(),
    )


@app.route("/chatgpt")
def chatgpt_page():
    return render_template("chatgpt.html")


@app.route("/open-chatgpt", methods=["POST"])
def open_chatgpt():
    if not CHATGPT_SCRIPT.exists():
        return jsonify(ok=False, error=f"Missing file: {CHATGPT_SCRIPT}"), 500
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(CHATGPT_SCRIPT),
            ],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode != 0:
            error = (completed.stderr or completed.stdout or "PowerShell failed").strip()
            return jsonify(ok=False, error=error), 500
        message = (completed.stdout or "ChatGPT started on laptop").strip()
        return jsonify(ok=True, message=message)
    except subprocess.TimeoutExpired:
        return jsonify(ok=False, error="Timed out while starting ChatGPT"), 500
    except Exception as e:  # noqa: BLE001
        return jsonify(ok=False, error=str(e)), 500


@app.route("/manifest.webmanifest")
def manifest():
    return app.send_static_file("manifest.webmanifest")


# -- Helpers ---------------------------------------------------------------

def _human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{int(n)} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _fmt_date(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _latest_pdfs(root: Path, limit: int, exts):
    """Top-level files in root with one of the given extensions, newest first."""
    exts_lower = tuple(e.lower() for e in exts)
    items = []
    try:
        with os.scandir(root) as it:
            for entry in it:
                if not entry.is_file(follow_symlinks=False):
                    continue
                if not entry.name.lower().endswith(exts_lower):
                    continue
                try:
                    st = entry.stat()
                except OSError:
                    continue
                items.append((st.st_mtime, st.st_size, Path(entry.path)))
    except OSError:
        pass
    items.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "name": p.name,
            "path": str(p),
            "size": _human_size(int(size)),
            "date": _fmt_date(mtime),
        }
        for mtime, size, p in items[:limit]
    ]


def _daily_pdf_window():
    """Return today's local [start, end) timestamps for the download-count window."""
    start_hour = int(getattr(config, "DAILY_PDF_COUNT_START_HOUR", 5))
    end_hour = int(getattr(config, "DAILY_PDF_COUNT_END_HOUR", 8))
    now = datetime.now()
    start = datetime.combine(now.date(), time(hour=start_hour))
    end = datetime.combine(now.date(), time(hour=end_hour))
    return start.timestamp(), end.timestamp(), start_hour, end_hour


def _daily_pdf_window_label() -> str:
    _, _, start_hour, end_hour = _daily_pdf_window()
    return f"{start_hour:02d}:00–{end_hour:02d}:00"


def _auto_daily_scan_roots(root: Path):
    """
    Roots to inspect for PDFs that were downloaded earlier in the day.

    The root itself is scanned only at top level. Subfolders whose names look
    like temporary/merge areas are scanned recursively because the download
    workflow may move the original PDFs there after download.
    """
    roots = []
    if root is None:
        return roots

    # Always include only the top level of SCAN_ROOT, where files first arrive.
    if root.exists():
        roots.append((root, False))

    explicit = getattr(config, "DAILY_PDF_COUNT_ROOTS", None)
    if explicit:
        for item in explicit:
            p = Path(item)
            if p.exists() and p != root:
                roots.append((p, True))
        return roots

    hints = tuple(
        str(x).lower()
        for x in getattr(
            config,
            "DAILY_PDF_COUNT_FOLDER_HINTS",
            ("temp", "tempor", "merge"),
        )
    )
    try:
        with os.scandir(root) as it:
            for entry in it:
                if not entry.is_dir(follow_symlinks=False):
                    continue
                name = entry.name.lower()
                if any(h in name for h in hints):
                    roots.append((Path(entry.path), True))
    except OSError:
        pass
    return roots


def _iter_pdf_files(root: Path, recursive: bool, exts_lower):
    """Yield Path objects for matching files, tolerating transient move/delete errors."""
    if recursive:
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                # Skip Windows/system folders and our state folders if encountered.
                dirnames[:] = [
                    d for d in dirnames
                    if not d.startswith("$")
                    and d.lower() not in {"system volume information", "state_change_logs", "state_backups"}
                ]
                for name in filenames:
                    if name.lower().endswith(exts_lower):
                        yield Path(dirpath) / name
        except OSError:
            return
    else:
        try:
            with os.scandir(root) as it:
                for entry in it:
                    if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(exts_lower):
                        yield Path(entry.path)
        except OSError:
            return


def _confirmed_download_names(start_ts, end_ts):
    """Recover source names from completed batch sessions wholly inside the window.

    The existing downloader writes 'Confirmat pe disk' only after completion.
    Batch headers/footers carry local timestamps; sessions crossing a boundary
    cannot be assigned exact download times and are deliberately ignored.
    """
    names = set()
    stamp_re = re.compile(r"Data:\s+\w+\s+(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2}:\d{2})")
    confirmed_re = re.compile(r"Confirmat pe disk:\s*(.+\.pdf)\s+\([1-9]\d* bytes\)", re.I)
    for pattern in getattr(config, "DAILY_PDF_LOG_GLOBS", ()):
        for filename in glob.glob(pattern):
            try:
                if Path(filename).stat().st_mtime < start_ts:
                    continue
                pending, session_start = set(), None
                with open(filename, encoding="utf-8", errors="replace") as stream:
                    for line in stream:
                        stamp = stamp_re.search(line)
                        if stamp:
                            ts = datetime.strptime(" ".join(stamp.groups()), "%m/%d/%Y %H:%M:%S").timestamp()
                            if session_start is not None and start_ts <= session_start <= ts < end_ts:
                                names.update(pending)
                            pending, session_start = set(), ts
                        match = confirmed_re.search(line)
                        if match:
                            pending.add(match.group(1).strip().lower())
            except (OSError, ValueError):
                continue
    return names


def _daily_pdf_count() -> int:
    """Count unique PDFs modified today during the configured morning window."""
    if SCAN_ROOT is None:
        return 0
    start_ts, end_ts, _, _ = _daily_pdf_window()
    exts_lower = tuple(e.lower() for e in getattr(config, "SCAN_FILE_EXTS", (".pdf",)))
    seen = set()
    disk_names = set()
    pattern = getattr(config, "DAILY_PDF_NAME_PATTERN", None)

    for root, recursive in _auto_daily_scan_roots(SCAN_ROOT):
        for p in _iter_pdf_files(root, recursive, exts_lower):
            if pattern and not re.search(pattern, p.name, re.IGNORECASE):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            if not (start_ts <= st.st_mtime < end_ts):
                continue
            # A file can temporarily exist in more than one workflow folder.
            # Match source name and content, even when copied timestamps differ.
            try:
                digest = hashlib.sha256()
                with p.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                seen.add((p.name.lower(), digest.digest()))
                disk_names.add(p.name.lower())
            except OSError:
                continue
    recovered = _confirmed_download_names(start_ts, end_ts)
    return len(seen) + len(recovered - disk_names)


def _latest_folders(root: Path, limit: int):
    """Top-level folders in root, newest first."""
    items = []
    try:
        with os.scandir(root) as it:
            for entry in it:
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if entry.name.startswith("$") or entry.name.lower() == "system volume information":
                    continue
                try:
                    st = entry.stat()
                except OSError:
                    continue
                items.append((st.st_mtime, Path(entry.path)))
    except OSError:
        pass
    items.sort(key=lambda x: x[0], reverse=True)
    return [
        {"name": p.name, "path": str(p), "date": _fmt_date(mtime)}
        for mtime, p in items[:limit]
    ]


# -- Tunnel ----------------------------------------------------------------

def start_tunnel() -> str:
    conf.get_default().auth_token = load_ngrok_token()
    kwargs = {"proto": "http", "inspect": False}
    if config.NGROK_DOMAIN:
        kwargs["domain"] = config.NGROK_DOMAIN
    tunnel = ngrok.connect(config.PORT, **kwargs)
    url = tunnel.public_url.replace("http://", "https://")
    home = f"{url}/?k={SECRET}"
    files = f"{url}/files?k={SECRET}"
    chatgpt = f"{url}/chatgpt?k={SECRET}"
    URL_FILE.write_text(home + "\n" + files + "\n" + chatgpt + "\n", encoding="utf-8")
    print("Private mobile links saved in current_url.txt", flush=True)
    return home


if __name__ == "__main__":
    start_tunnel()
    app.run(host="127.0.0.1", port=config.PORT, debug=False, use_reloader=False)
