"""
Loads the validated reference data from the bundled Excel files in
`reference/` and exposes cascading-dropdown + validation helpers.

Location.xlsx      -> ID, District, Sector, Cell, Village   (14,842 rows)
Interventions.xlsx -> UniqueID, Implementer, Intervention   (65 rows)
Trees.xlsx         -> Tree Origin, Tree Type, Tree species  (OPTIONAL)

Column names are matched case/space-insensitively so minor header changes in
the source files don't break the app.
"""
from __future__ import annotations
import re
import pandas as pd
import streamlit as st

import config


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _find_col(df: pd.DataFrame, *candidates: str):
    lookup = {_norm(c): c for c in df.columns}
    for cand in candidates:
        if _norm(cand) in lookup:
            return lookup[_norm(cand)]
    for cand in candidates:                       # loose / partial match
        key = _norm(cand)
        for nc, orig in lookup.items():
            if key and (key in nc or nc in key):
                return orig
    return None


def _standardise(df: pd.DataFrame, wanted: dict[str, tuple]) -> pd.DataFrame:
    """wanted = {"District": ("District","Distict"), ...}"""
    rename = {}
    for target, aliases in wanted.items():
        found = _find_col(df, *aliases)
        if found:
            rename[found] = target
    df = df.rename(columns=rename)
    for target in wanted:
        if target not in df.columns:
            df[target] = ""
        df[target] = df[target].astype(str).str.strip().replace({"nan": "", "None": ""})
    return df[list(wanted.keys())]


# ---------------------------------------------------------------- loaders

@st.cache_data(show_spinner=False)
def load_locations() -> pd.DataFrame:
    df = pd.read_excel(config.LOCATION_FILE, dtype=str).fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    return _standardise(df, {
        "District": ("District",),
        "Sector": ("Sector",),
        "Cell": ("Cell",),
        "Village": ("Village",),
    }).drop_duplicates()


@st.cache_data(show_spinner=False)
def load_interventions() -> pd.DataFrame:
    df = pd.read_excel(config.INTERVENTION_FILE, dtype=str).fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    return _standardise(df, {
        "Implementer": ("Implementer", "Implimenter"),
        "Intervention": ("Intervention", "Intervetion"),
    }).drop_duplicates()


@st.cache_data(show_spinner=False)
def load_trees() -> pd.DataFrame | None:
    """Optional. Returns None if reference/Trees.xlsx is not present."""
    if not config.TREE_FILE.exists():
        return None
    try:
        df = pd.read_excel(config.TREE_FILE, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        return _standardise(df, {
            "Tree Origin": ("Tree Origin", "Tree Orgine", "Tree Category"),
            "Tree Type": ("Tree Type",),
            "Tree species": ("Tree species", "Tree Species"),
        }).drop_duplicates()
    except Exception:
        return None


def trees_available() -> bool:
    return load_trees() is not None


# ------------------------------------------------- cascading option lists

def _uniq(series) -> list[str]:
    return sorted({v for v in series if v})


def _cf(s) -> str:
    """Case-fold + strip, for case-insensitive comparisons."""
    return str(s).strip().casefold()


def districts() -> list[str]:
    return _uniq(load_locations()["District"])


def sectors(district: str) -> list[str]:
    if not district:
        return []
    df = load_locations()
    return _uniq(df.loc[df["District"].str.casefold() == _cf(district), "Sector"])


def cells(district: str, sector: str) -> list[str]:
    if not (district and sector):
        return []
    df = load_locations()
    m = (df["District"].str.casefold() == _cf(district)) & (df["Sector"].str.casefold() == _cf(sector))
    return _uniq(df.loc[m, "Cell"])


def villages(district: str, sector: str, cell: str) -> list[str]:
    if not (district and sector and cell):
        return []
    df = load_locations()
    m = (df["District"].str.casefold() == _cf(district)) & \
        (df["Sector"].str.casefold() == _cf(sector)) & \
        (df["Cell"].str.casefold() == _cf(cell))
    return _uniq(df.loc[m, "Village"])


def implementers() -> list[str]:
    return _uniq(load_interventions()["Implementer"])


def interventions(implementer: str) -> list[str]:
    if not implementer:
        return []
    df = load_interventions()
    return _uniq(df.loc[df["Implementer"] == implementer, "Intervention"])


def tree_origins() -> list[str]:
    df = load_trees()
    return _uniq(df["Tree Origin"]) if df is not None else []


def tree_types(origin: str) -> list[str]:
    df = load_trees()
    if df is None or not origin:
        return []
    return _uniq(df.loc[df["Tree Origin"] == origin, "Tree Type"])


def tree_species(origin: str, ttype: str) -> list[str]:
    df = load_trees()
    if df is None or not (origin and ttype):
        return []
    m = (df["Tree Origin"] == origin) & (df["Tree Type"] == ttype)
    return _uniq(df.loc[m, "Tree species"])


# --------------------------------------------------------- validation

def canonical_location(district, sector, cell, village=""):
    """
    Case-insensitive lookup that returns the reference file's actual-cased
    (District, Sector, Cell, Village) tuple for a match, or None if the
    combination doesn't exist. Used to normalise casing on bulk upload so
    'KIGALI' and 'Kigali' don't end up as two different dashboard entries.
    Village in the returned tuple is "" when no village was given to match.
    """
    df = load_locations()
    m = (df["District"].str.casefold() == _cf(district)) & \
        (df["Sector"].str.casefold() == _cf(sector)) & \
        (df["Cell"].str.casefold() == _cf(cell))
    if village:
        m &= (df["Village"].str.casefold() == _cf(village))
    sub = df.loc[m]
    if sub.empty:
        return None
    row = sub.iloc[0]
    return (row["District"], row["Sector"], row["Cell"], row["Village"] if village else "")


def validate_location(district, sector, cell, village="") -> bool:
    return canonical_location(district, sector, cell, village) is not None


def validate_intervention(implementer, intervention) -> bool:
    df = load_interventions()
    m = (df["Implementer"] == str(implementer).strip()) & \
        (df["Intervention"] == str(intervention).strip())
    return bool(m.any())


def validate_implementer(implementer) -> bool:
    return str(implementer).strip() in implementers()


def validate_tree(origin, ttype, species) -> bool:
    df = load_trees()
    if df is None:
        return True          # no reference file -> nothing to validate against
    m = (df["Tree Origin"] == str(origin).strip()) & \
        (df["Tree Type"] == str(ttype).strip()) & \
        (df["Tree species"] == str(species).strip())
    return bool(m.any())
