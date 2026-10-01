"""
Loads the validated reference data from the bundled Excel files in
`reference/` and exposes cascading-dropdown + validation helpers.

Location.xlsx      -> ID, District, Sector, Cell, Village   (14,842 rows)
Interventions.xlsx -> UniqueID, Implementer, Intervention   (65 rows)
Activities.xlsx     -> Implementer > Main Activity > Sub Activity > Deliverables > dates > Expected Results
Indicators.xlsx    -> Project > Implementer > Activity reference > Indicator > Sub Indicator > targets > Reporting Date > Indicator Type
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


ACTIVITY_COLUMNS = {
    "implementer": ("Implementer",),
    "main_activity": ("Main Activity",),
    "sub_activity": ("Sub Activity",),
    "deliverables": ("Deliverables",),
    "start_date": ("Start Date",),
    "end_date": ("End Date",),
    "expected_results": ("Expected Results",),
}


@st.cache_data(show_spinner=False)
def load_activities() -> pd.DataFrame:
    """Load the activity reporting hierarchy from the bundled reference workbook."""
    empty = pd.DataFrame(columns=list(ACTIVITY_COLUMNS))
    if not config.ACTIVITY_FILE.exists():
        return empty
    try:
        df = pd.read_excel(config.ACTIVITY_FILE, dtype=object).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        rename = {}
        for target, aliases in ACTIVITY_COLUMNS.items():
            found = _find_col(df, *aliases)
            if found:
                rename[found] = target
        df = df.rename(columns=rename)
        if not set(ACTIVITY_COLUMNS).issubset(df.columns):
            return empty
        df = df[list(ACTIVITY_COLUMNS)]
        for col in df.columns:
            if col in ("start_date", "end_date"):
                dates = pd.to_datetime(df[col], errors="coerce")
                df[col] = dates.dt.strftime("%Y-%m-%d").fillna("")
            else:
                df[col] = df[col].map(lambda v: str(v).strip() if not _blank_ref(v) else "")
        # The workbook has formatted empty rows after the actual reporting list.
        df = df[(df["implementer"] != "") & (df["main_activity"] != "")]
        return df.drop_duplicates().reset_index(drop=True)
    except Exception:
        return empty


def _blank_ref(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip()) or pd.isna(value)


def activity_options(field: str, selections: dict | None = None) -> list[str]:
    """Options for an activity reference field, narrowed by earlier selections."""
    df = load_activities()
    if field not in df.columns:
        return []
    selections = selections or {}
    hierarchy = list(ACTIVITY_COLUMNS)
    target_index = hierarchy.index(field)
    for parent in hierarchy[:target_index]:
        selected = selections.get(parent)
        if selected:
            df = df[df[parent] == str(selected).strip()]
        else:
            return []
    return sorted({str(v) for v in df[field] if str(v).strip()})


def canonical_activity(rec: dict) -> dict | None:
    """Return reference-cased activity values if the supplied combination exists."""
    df = load_activities()
    provided = {col: str(rec.get(col)).strip() for col in ACTIVITY_COLUMNS
                if not _blank_ref(rec.get(col))}
    if not provided:
        return {}
    mask = pd.Series(True, index=df.index)
    for col, value in provided.items():
        mask &= df[col].str.casefold() == value.casefold()
    match = df.loc[mask]
    if match.empty:
        return None
    row = match.iloc[0]
    return {col: row[col] for col in provided}


INDICATOR_COLUMNS = {
    "project": ("Project",),
    "implementer": ("Implementer",),
    "activity_reference": ("Activity reference",),
    "indicator": ("Indicator",),
    "sub_indicator": ("Sub Indicator",),
    "unit": ("Unit",),
    "mid_term_target": ("Mid-Term Target",),
    "lop_target": ("LoP Target",),
    "reporting_date": ("Reporting Date",),
    "target_year": ("Target/Year",),
    "indicator_type": ("Indicator Type",),
}


def _indicator_text(value) -> str:
    if _blank_ref(value):
        return ""
    if isinstance(value, (int, float)) and float(value).is_integer():
        return str(int(value))
    return str(value).strip()


@st.cache_data(show_spinner=False)
def load_indicators() -> pd.DataFrame:
    """Load indicator reporting choices from the bundled tracking workbook."""
    empty = pd.DataFrame(columns=list(INDICATOR_COLUMNS))
    if not config.INDICATOR_FILE.exists():
        return empty
    try:
        df = pd.read_excel(config.INDICATOR_FILE, dtype=object).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        rename = {}
        for target, aliases in INDICATOR_COLUMNS.items():
            found = _find_col(df, *aliases)
            if found:
                rename[found] = target
        df = df.rename(columns=rename)
        if not set(INDICATOR_COLUMNS).issubset(df.columns):
            return empty
        df = df[list(INDICATOR_COLUMNS)]
        for col in df.columns:
            if col == "reporting_date":
                def as_date(value):
                    if _blank_ref(value):
                        return ""
                    if isinstance(value, (int, float)) and 1900 <= float(value) <= 2100:
                        return f"{int(value):04d}-01-01"
                    date = pd.to_datetime(value, errors="coerce")
                    return date.strftime("%Y-%m-%d") if not pd.isna(date) else ""
                df[col] = df[col].map(as_date)
            else:
                df[col] = df[col].map(_indicator_text)
        df = df[(df["project"] != "") & (df["implementer"] != "") & (df["indicator"] != "")]
        return df.drop_duplicates().reset_index(drop=True)
    except Exception:
        return empty


def indicator_options(field: str, selections: dict | None = None) -> list[str]:
    """Return choices narrowed by any previously selected indicator fields."""
    df = load_indicators()
    if field not in df.columns:
        return []
    selections = selections or {}
    hierarchy = list(INDICATOR_COLUMNS)
    for parent in hierarchy[:hierarchy.index(field)]:
        selected = selections.get(parent)
        # Some reference rows have no target/sub-indicator. Leave those levels
        # optional, while retaining every other selected parent constraint.
        if not _blank_ref(selected):
            df = df[df[parent] == str(selected).strip()]
    values = {str(v) for v in df[field] if str(v).strip()}
    if field in ("mid_term_target", "lop_target", "target_year"):
        return sorted(values, key=lambda value: float(value))
    return sorted(values)


def canonical_indicator(rec: dict) -> dict | None:
    """Return source-cased indicator selections if their combination exists."""
    df = load_indicators()
    provided = {col: _indicator_text(rec.get(col)) for col in INDICATOR_COLUMNS
                if not _blank_ref(rec.get(col))}
    if not provided:
        return {}
    mask = pd.Series(True, index=df.index)
    for col, value in provided.items():
        mask &= df[col].str.casefold() == value.casefold()
    match = df.loc[mask]
    if match.empty:
        return None
    row = match.iloc[0]
    return {col: row[col] for col in provided}


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
