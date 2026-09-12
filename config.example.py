"""Copy this file to config.py and edit the values."""

# Absolute path to the .bat file you want to trigger from your phone.
BAT_PATH = r"C:\path\to\your\script.bat"

# ngrok static domain (optional). Leave as None for a random URL each run.
# Free ngrok accounts get one free static "dev domain" at
# https://dashboard.ngrok.com/domains — paste it here, e.g.:
# NGROK_DOMAIN = "your-dev-domain.ngrok-free.dev"
NGROK_DOMAIN = None

# Local Flask port (any free port is fine).
PORT = 5000

# Title shown on the phone page.
APP_TITLE = "Remote Runner"

# --------------------------------------------------------------------------
# Recent-files browser (the /files page).
# Shows the most recently modified files (matching SCAN_FILE_EXTS) and the
# most recently modified subfolders, at the top level of SCAN_ROOT.
# Set SCAN_ROOT to None to disable the page.
# --------------------------------------------------------------------------

SCAN_ROOT = None  # e.g. r"G:\\" or r"C:\Users\me\Downloads"
SCAN_FILE_EXTS = (".pdf",)  # extensions to list (lowercase, with dot)
SCAN_FILE_LIMIT = 2         # how many recent files to show
SCAN_FOLDER_LIMIT = 2       # how many recent folders to show

# --------------------------------------------------------------------------
# Morning PDF download counter shown on /files.
# Counts files whose modification time is today in [05:00, 08:00).
#
# Recommended: set DAILY_PDF_COUNT_ROOTS explicitly to the folders where the
# downloaded source PDFs live after they leave G:\ root. Each listed root is
# scanned recursively. If left as None, the app scans the top level of
# SCAN_ROOT plus any top-level folders whose names contain temp/tempor/merge.
# --------------------------------------------------------------------------
DAILY_PDF_COUNT_START_HOUR = 5
DAILY_PDF_COUNT_END_HOUR = 8
DAILY_PDF_COUNT_ROOTS = None
# Example:
# DAILY_PDF_COUNT_ROOTS = (
#     r"G:\\Temp",
#     r"G:\\Temporare",
#     r"G:\\PDF_Merge",
# )
DAILY_PDF_COUNT_FOLDER_HINTS = ("temp", "tempor", "merge")

# Optional source filename filter; excludes merged outputs for Arcanum.
DAILY_PDF_NAME_PATTERN = None  # e.g. r"__pages\d+-\d+\.pdf$"

# Optional existing Arcanum batch logs; recover deleted/moved source PDFs.
# Only completed sessions entirely within the window are used.
DAILY_PDF_LOG_GLOBS = ()
