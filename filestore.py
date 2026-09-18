"""
Stores uploaded files (shapefiles, training modules, attendance lists) in a
local folder, renaming each one to embed the upload date/time and the
username who uploaded it. The generated filename (not the file itself) is
what gets written into the data table's existing varchar column
(`shapefile`, `modules_link`, `attendance_link`) — so no database schema
change was needed for this feature.

    uploads/
        SiteA_shapefile__20260917_143512__jdoe.zip
        Q3_training_report__20260917_143622__jdoe.pdf

⚠️ IMPORTANT — read before relying on this in production:
If this app is deployed on Streamlit Community Cloud (or any host without a
persistent/attached disk), the `uploads/` folder lives on the container's
local filesystem. It survives normal page reloads and reboots-while-idle,
but it is WIPED whenever the app is redeployed (e.g. you push new code) or
the container is rebuilt from scratch. Files already recorded in MySQL will
still show a filename, but the underlying file will be gone.

If you need uploaded files to survive redeploys, the two common fixes are:
  1. Also store the file bytes in MySQL (a LONGBLOB column/table) — ask and
     I'll add this as a durable backup alongside the folder.
  2. Point this at a persistent volume or external storage (S3, Google
     Drive, etc.) instead of a local folder — a bigger change, but the most
     robust for a hosted deployment.
For now this saves to a local folder exactly as requested.
"""
from __future__ import annotations
import datetime as dt
import re
from pathlib import Path

import config

UPLOAD_DIR: Path = config.BASE_DIR / "uploads"
MAX_FILE_MB = 20


def _slug(s: str, max_len: int = 60) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", str(s)).strip("_")
    return (s[:max_len] or "file")


def ensure_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def generate_filename(original_name: str, username: str) -> str:
    stem = Path(original_name).stem
    ext = Path(original_name).suffix.lower()
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{_slug(stem)}__{ts}__{_slug(username)}{ext}"


def save_file(uploaded_file, username: str) -> str:
    """
    uploaded_file: a Streamlit UploadedFile (has .name and .getvalue()).
    Returns the generated filename that should be stored in the DB column.
    Raises ValueError if the file is too large.
    """
    ensure_dir()
    data = uploaded_file.getvalue()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise ValueError(f"File is {size_mb:.1f} MB, which is over the {MAX_FILE_MB} MB limit.")

    stored_name = generate_filename(uploaded_file.name, username)
    path = UPLOAD_DIR / stored_name
    # extremely unlikely, but guarantee no overwrite of an existing file
    i = 1
    while path.exists():
        stored_name = generate_filename(f"{Path(uploaded_file.name).stem}_{i}{Path(uploaded_file.name).suffix}", username)
        path = UPLOAD_DIR / stored_name
        i += 1
    path.write_bytes(data)
    return stored_name


def get_file_path(stored_name: str) -> Path | None:
    if not stored_name:
        return None
    p = UPLOAD_DIR / stored_name
    return p if p.exists() else None


def read_file(stored_name: str) -> bytes | None:
    p = get_file_path(stored_name)
    return p.read_bytes() if p else None
