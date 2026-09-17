"""
Central configuration.

Credentials are NEVER hardcoded. They are read from, in order:
  1. Streamlit secrets  (.streamlit/secrets.toml)
  2. Environment variables

Required keys: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

NOTE: the Aiven password was pasted in plaintext in chat. Rotate it in the
Aiven console before using this for real data.
"""
import os
from pathlib import Path

try:
    import streamlit as st
    _SECRETS = st.secrets
except Exception:
    _SECRETS = {}


def _get(key: str, default: str = "") -> str:
    try:
        if key in _SECRETS:
            return str(_SECRETS[key])
    except Exception:
        pass
    return os.environ.get(key, default)


BASE_DIR = Path(__file__).resolve().parent

DB_HOST = _get("DB_HOST", "mysql-2a6c776f-biclass.e.aivencloud.com")
DB_PORT = int(_get("DB_PORT", "15575") or 15575)
DB_USER = _get("DB_USER", "avnadmin")
DB_PASSWORD = _get("DB_PASSWORD", "")      # no hardcoded fallback for the secret
DB_NAME = _get("DB_NAME", "powerbi_db")

# ---- Bundled validated reference data -------------------------------------
REFERENCE_DIR = BASE_DIR / "reference"
LOCATION_FILE = REFERENCE_DIR / "Location.xlsx"          # District/Sector/Cell/Village
INTERVENTION_FILE = REFERENCE_DIR / "Interventions.xlsx"  # Implementer/Intervention
# Optional. If you drop a Trees.xlsx here with columns
# "Tree Origin", "Tree Type", "Tree species", those three fields become
# cascading dropdowns too. Without it they stay free-text.
TREE_FILE = REFERENCE_DIR / "Trees.xlsx"

PROJECTS = ["TREPA", "COMBIO", "AREECA", "DESIRA"]

GENDER_OPTIONS = ["Male", "Female"]
YOUTH_OPTIONS = ["Youth", "Not Youth"]

APP_TITLE = "Project M&E Data Platform"


def credentials_ok() -> bool:
    return bool(DB_PASSWORD and DB_HOST and DB_USER and DB_NAME)
