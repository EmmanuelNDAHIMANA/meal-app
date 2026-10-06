"""
Schema-driven UI engine reused by all nine data pages:
    render_form(table_key)      - submit one record at a time
    render_upload(table_key)    - download template + bulk upload Excel
    render_dashboard(table_key) - metrics/charts/table with slicers
"""
from __future__ import annotations
import datetime as dt
import hashlib
import html
import json
import re

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

import config
import db
import schemas
import templates
import reference_data as ref
import filestore
import mapwidget
import ui

CASCADE_FIRST = {"implementer", "district", "tree_origin"}


# ----------------------------------------------------------------- helpers

def _ver(table_key: str) -> int:
    return st.session_state.get(f"_ver_{table_key}", 0)


def _bump(table_key: str):
    st.session_state[f"_ver_{table_key}"] = _ver(table_key) + 1


def _fingerprint(value) -> str:
    """Stable identity for the current form values or uploaded workbook."""
    if hasattr(value, "getvalue"):
        payload = value.getvalue()
    else:
        payload = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _blank(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    if isinstance(v, str) and not v.strip():
        return True
    return False


def _clean(v):
    """Normalise a form/Excel value for MySQL."""
    if _blank(v):
        return None
    if isinstance(v, (dt.datetime, pd.Timestamp)):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, str):
        return v.strip()
    return v


# ------------------------------------------------------------ single record

def render_form(table_key: str):
    cfg = schemas.TABLES[table_key]
    pfx = f"f_{table_key}_{_ver(table_key)}"
    vals: dict[str, object] = {}

    st.caption("Fields marked * are required. Dropdowns are restricted to the validated reference data.")

    if not ref.trees_available() and any(fl["ftype"].startswith("tree_") for fl in cfg["fields"]):
        st.info(
            "No `reference/Trees.xlsx` found, so Tree Orgine / Tree Type / Tree species are "
            "free text. Add that file with those three columns to turn them into dropdowns."
        )

    cols = st.columns(2)
    i = 0
    for fl in cfg["fields"]:
        key = f"{pfx}_{fl['col']}"
        label = fl["label"] + (" *" if fl["req"] else "")
        ft = fl["ftype"]

        if ft == "gps":
            # Map picker needs full width, so it breaks out of the 2-column
            # grid rather than sharing a narrow column like the other fields.
            vals[fl["col"]] = mapwidget.render_gps_picker(label, key=key)
            st.divider()
            continue

        c = cols[i % 2]
        i += 1

        with c:
            if ft.startswith("indicator_"):
                options = ref.indicator_options(fl["col"], vals)
                indicator_widget_args = {}
                if fl["col"] == "reporting_date":
                    indicator_widget_args["format_func"] = lambda value: value[:4] if value else ""
                vals[fl["col"]] = st.selectbox(
                    label, [""] + options, key=key,
                    help="Choose the preceding indicator fields first."
                    if fl["col"] != "project" and not options else None,
                    **indicator_widget_args,
                )
            elif ft.startswith("activity_"):
                options = ref.activity_options(fl["col"], vals)
                vals[fl["col"]] = st.selectbox(
                    label, [""] + options, key=key,
                    help="Choose the preceding activity fields first."
                    if ft != "activity_implementer" and not options else None,
                )
            elif ft == "project":
                vals[fl["col"]] = st.selectbox(label, [""] + config.PROJECTS, key=key)
            elif ft == "implementer":
                vals[fl["col"]] = st.selectbox(label, [""] + ref.implementers(), key=key)
            elif ft == "intervention":
                opts = ref.interventions(vals.get("implementer", ""))
                vals[fl["col"]] = st.selectbox(
                    label, [""] + opts, key=key,
                    help="Select an Implementer first." if not opts else None,
                )
            elif ft == "district":
                vals[fl["col"]] = st.selectbox(label, [""] + ref.districts(), key=key)
            elif ft == "sector":
                vals[fl["col"]] = st.selectbox(
                    label, [""] + ref.sectors(vals.get("district", "")), key=key)
            elif ft == "cell":
                vals[fl["col"]] = st.selectbox(
                    label, [""] + ref.cells(vals.get("district", ""), vals.get("sector", "")), key=key)
            elif ft == "village":
                vals[fl["col"]] = st.selectbox(
                    label, [""] + ref.villages(vals.get("district", ""), vals.get("sector", ""),
                                               vals.get("cell", "")), key=key)
            elif ft == "tree_origin":
                if ref.trees_available():
                    vals[fl["col"]] = st.selectbox(label, [""] + ref.tree_origins(), key=key)
                else:
                    vals[fl["col"]] = st.text_input(label, key=key)
            elif ft == "tree_type":
                if ref.trees_available():
                    origin = vals.get("tree_origin") or vals.get("tree_category") or ""
                    vals[fl["col"]] = st.selectbox(label, [""] + ref.tree_types(origin), key=key)
                else:
                    vals[fl["col"]] = st.text_input(label, key=key)
            elif ft == "tree_species":
                if ref.trees_available():
                    origin = vals.get("tree_origin") or vals.get("tree_category") or ""
                    vals[fl["col"]] = st.selectbox(
                        label, [""] + ref.tree_species(origin, vals.get("tree_type", "")), key=key)
                else:
                    vals[fl["col"]] = st.text_input(label, key=key)
            elif ft == "gender":
                vals[fl["col"]] = st.selectbox(label, [""] + config.GENDER_OPTIONS, key=key)
            elif ft == "youth":
                vals[fl["col"]] = st.selectbox(label, [""] + config.YOUTH_OPTIONS, key=key)
            elif ft == "choice":
                vals[fl["col"]] = st.selectbox(label, [""] + fl.get("options", []), key=key)
            elif ft == "file":
                exts = fl.get("options") or None
                hint = f" (.{', .'.join(exts)})" if exts else ""
                vals[fl["col"]] = st.file_uploader(
                    fl["label"] + hint, type=exts, key=key,
                    help=f"Max {filestore.MAX_FILE_MB} MB. Renamed automatically with the upload date and your username.",
                )
            elif ft == "int":
                v = st.number_input(label, min_value=0, step=1, value=None,
                                    placeholder="leave empty if unknown", key=key)
                vals[fl["col"]] = v
            elif ft == "decimal":
                v = st.number_input(label, min_value=0.0, step=0.01, value=None,
                                    placeholder="leave empty if unknown", key=key)
                vals[fl["col"]] = v
            elif ft == "date":
                vals[fl["col"]] = st.date_input(label, value=None, format="YYYY-MM-DD", key=key)
            elif ft == "textarea":
                vals[fl["col"]] = st.text_area(label, key=key)
            elif ft == "phone":
                vals[fl["col"]] = st.text_input(label, placeholder="07xxxxxxxx", key=key)
            elif ft == "link":
                vals[fl["col"]] = st.text_input(label, placeholder="https://… or file path", key=key)
            else:
                vals[fl["col"]] = st.text_input(label, key=key)

    st.divider()
    operation_key = f"_single_insert_locked_{table_key}"
    has_new_input = any(not _blank(value) for value in vals.values())
    button_disabled = st.session_state.get(operation_key, False) and not has_new_input
    if st.button("✅ Submit record", type="primary", key=f"{pfx}_submit",
                 disabled=button_disabled):
        username = st.session_state["user"]["username"]

        # Save any uploaded files first, replacing the widget's UploadedFile
        # object with the generated filename (date + username baked in).
        file_save_failed = False
        for fl in cfg["fields"]:
            if fl["ftype"] != "file":
                continue
            uploaded = vals.get(fl["col"])
            if uploaded is None:
                vals[fl["col"]] = None
                continue
            try:
                vals[fl["col"]] = filestore.save_file(uploaded, username)
            except Exception as e:
                st.error(f"Could not save '{fl['label']}': {e}")
                file_save_failed = True
        if file_save_failed:
            return

        errs = _validate(cfg, {k: _clean(v) for k, v in vals.items()}, strict_ref=True)
        if errs:
            st.error("Fix these first:\n" + "\n".join(f"- {e}" for e in errs))
            return
        rec = {k: _clean(v) for k, v in vals.items()}
        rec["created_by"] = username
        rec["source"] = "manual"
        try:
            placeholders = ", ".join(f":{k}" for k in rec)
            collist = ", ".join(f"`{k}`" for k in rec)
            db.execute(f"INSERT INTO `{cfg['table']}` ({collist}) VALUES ({placeholders})", rec)
        except Exception as e:
            st.error(f"Save failed: {e}")
            return
        st.success("Record saved.")
        st.session_state[operation_key] = True
        _bump(table_key)
        st.rerun()


# ------------------------------------------------------------- validation

def _normalize_location_casing(rec: dict):
    """
    District/Sector/Cell/Village accept any case on bulk upload, but before
    saving we rewrite them to match the reference file's actual casing, so
    'KIGALI' and 'Kigali' don't end up as two different values in dashboard
    filters and charts. Only touches rows that already passed validation
    (i.e. a case-insensitive match is guaranteed to exist).
    """
    d, s, c = rec.get("district"), rec.get("sector"), rec.get("cell")
    if any(_blank(x) for x in (d, s, c)):
        return
    v = rec.get("village")
    canon = ref.canonical_location(d, s, c, v if not _blank(v) else "")
    if canon:
        rec["district"], rec["sector"], rec["cell"] = canon[0], canon[1], canon[2]
        if not _blank(v):
            rec["village"] = canon[3]


def _normalize_activity_values(rec: dict):
    canonical = ref.canonical_activity(rec)
    if canonical:
        rec.update(canonical)


def _validate(cfg, rec: dict, strict_ref: bool = True) -> list[str]:
    errs: list[str] = []
    by_type = {fl["ftype"]: fl["col"] for fl in cfg["fields"]}

    for fl in cfg["fields"]:
        if fl["req"] and _blank(rec.get(fl["col"])):
            errs.append(f"'{fl['label']}' is required")

    proj = rec.get("project")
    if cfg["table"] != "indicators" and not _blank(proj) and str(proj).strip() not in config.PROJECTS:
        errs.append(f"Project '{proj}' is not one of {', '.join(config.PROJECTS)}")

    impl = rec.get("implementer")
    interv = rec.get("intervention")
    if cfg["table"] not in ("activities", "indicators") and not _blank(impl) and not ref.validate_implementer(impl):
        errs.append(f"Implementer '{impl}' is not in the reference list")
    elif cfg["table"] not in ("activities", "indicators") and not _blank(impl) and not _blank(interv) and not ref.validate_intervention(impl, interv):
        errs.append(f"Intervention '{interv}' does not belong to Implementer '{impl}'")

    if cfg["table"] == "activities" and ref.canonical_activity(rec) is None:
        errs.append("The activity selections do not match the reporting reference list")
    if cfg["table"] == "indicators" and ref.canonical_indicator(rec) is None:
        errs.append("The indicator selections do not match the tracking reference list")

    d, s, c = rec.get("district"), rec.get("sector"), rec.get("cell")
    v = rec.get("village")
    if not any(_blank(x) for x in (d, s, c)):
        if not ref.validate_location(d, s, c, v if not _blank(v) else ""):
            where = f"{d} > {s} > {c}" + (f" > {v}" if not _blank(v) else "")
            errs.append(f"Location '{where}' is not a valid Rwanda administrative combination")

    if ref.trees_available():
        origin = rec.get("tree_origin") or rec.get("tree_category")
        tt, sp = rec.get("tree_type"), rec.get("tree_species")
        if not any(_blank(x) for x in (origin, tt, sp)):
            if not ref.validate_tree(origin, tt, sp):
                errs.append(f"Tree combination '{origin} / {tt} / {sp}' is not in the reference list")

    g = rec.get("gender")
    if not _blank(g) and str(g).strip() not in config.GENDER_OPTIONS:
        errs.append(f"Gender '{g}' must be Male or Female")

    y = rec.get("youth_status")
    if not _blank(y) and str(y).strip() not in config.YOUTH_OPTIONS:
        errs.append(f"'Youth or Not Youth' value '{y}' must be Youth or Not Youth")

    for fl in cfg["fields"]:
        if fl["ftype"] == "choice" and fl.get("options"):
            val = rec.get(fl["col"])
            if not _blank(val) and str(val).strip() not in fl["options"]:
                errs.append(f"'{fl['label']}' value '{val}' must be one of: {', '.join(fl['options'])}")

    return errs


def _norm_hdr(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _coerce(val, ftype):
    """Convert an Excel cell into the right python type, or raise ValueError."""
    if _blank(val):
        return None
    if ftype == "int":
        return int(float(str(val).replace(",", "").strip()))
    if ftype == "decimal":
        return float(str(val).replace(",", "").strip())
    if ftype == "date":
        ts = pd.to_datetime(val, errors="raise", dayfirst=False)
        return ts.date().isoformat()
    if ftype in ("activity_start_date", "activity_end_date"):
        ts = pd.to_datetime(val, errors="raise", dayfirst=False)
        return ts.date().isoformat()
    if ftype in ("indicator_mid_term_target", "indicator_lop_target", "indicator_target_year"):
        return float(str(val).replace(",", "").strip())
    if ftype == "indicator_reporting_date":
        if isinstance(val, (int, float)) and 1900 <= float(val) <= 2100:
            return f"{int(val):04d}-01-01"
        ts = pd.to_datetime(val, errors="raise", dayfirst=False)
        return ts.date().isoformat()
    return str(val).strip()


# ----------------------------------------------------------- bulk upload

def render_upload(table_key: str):
    cfg = schemas.TABLES[table_key]

    c1, c2 = st.columns([1, 2])
    with c1:
        try:
            data = templates.build_template(table_key)
            st.download_button(
                "⬇️ Download Excel template",
                data=data,
                file_name=f"{cfg['table']}_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
                key=f"tpl_{table_key}",
            )
        except Exception as e:
            st.error(f"Template generation failed: {e}")
    with c2:
        st.caption(
            "The template has the exact headers for this table, in-cell dropdowns for "
            "Project / Implementer / District / Gender, a cascading Intervention list, "
            "and full Location & Intervention lookup sheets."
        )

    st.divider()
    up = st.file_uploader("Upload the filled template (.xlsx)", type=["xlsx"], key=f"up_{table_key}")
    if up is None:
        return
    upload_fingerprint = _fingerprint(up)

    try:
        xls = pd.ExcelFile(up)
        sheet = "Data" if "Data" in xls.sheet_names else xls.sheet_names[0]
        raw = pd.read_excel(xls, sheet_name=sheet)
    except Exception as e:
        st.error(f"Could not read that file: {e}")
        return

    raw = raw.dropna(how="all")
    if raw.empty:
        st.warning("That sheet has no data rows.")
        return

    # map uploaded headers -> db columns
    hdr_to_col = {_norm_hdr(fl["label"]): fl["col"] for fl in cfg["fields"]}
    ftype_by_col = {fl["col"]: fl["ftype"] for fl in cfg["fields"]}
    mapping, unknown = {}, []
    for uc in raw.columns:
        target = hdr_to_col.get(_norm_hdr(uc))
        if target:
            mapping[uc] = target
        else:
            unknown.append(str(uc))

    missing = [fl["label"] for fl in cfg["fields"]
               if fl["col"] not in mapping.values() and fl["req"]]
    if missing:
        st.error("Required columns are missing from your file: " + ", ".join(missing))
        return
    if unknown:
        st.info("Ignored unrecognised columns: " + ", ".join(unknown))

    df = raw.rename(columns=mapping)
    good, bad = [], []
    for pos, (_, row) in enumerate(df.iterrows()):
        excel_row = pos + 2
        rec, errs = {}, []
        for fl in cfg["fields"]:
            col = fl["col"]
            if col not in df.columns:
                rec[col] = None
                continue
            try:
                rec[col] = _coerce(row.get(col), ftype_by_col[col])
            except Exception:
                rec[col] = None
                errs.append(f"'{fl['label']}' has an invalid {fl['ftype']} value ({row.get(col)!r})")
        errs += _validate(cfg, rec, strict_ref=True)
        if errs:
            bad.append({"Excel row": excel_row, "Problems": "; ".join(errs),
                        **{k: v for k, v in rec.items()}})
        else:
            _normalize_location_casing(rec)
            if cfg["table"] == "activities":
                _normalize_activity_values(rec)
            if cfg["table"] == "indicators":
                canonical = ref.canonical_indicator(rec)
                if canonical:
                    rec.update(canonical)
            good.append(rec)

    m1, m2, m3 = st.columns(3)
    m1.metric("Rows read", len(df))
    m2.metric("Ready to insert", len(good))
    m3.metric("Rejected", len(bad))

    if bad:
        st.warning("These rows will not be inserted until they're corrected:")
        bad_df = pd.DataFrame(bad)
        st.dataframe(bad_df, use_container_width=True, height=260)
        st.download_button(
            "⬇️ Download rejected rows (CSV)",
            bad_df.to_csv(index=False).encode(),
            file_name=f"{cfg['table']}_rejected_rows.csv",
            key=f"bad_{table_key}",
        )

    if not good:
        st.error("Nothing to upload.")
        return

    with st.expander(f"Preview the {len(good)} valid row(s)"):
        st.dataframe(pd.DataFrame(good), use_container_width=True)

    inserted_key = f"_last_bulk_insert_{table_key}"
    if st.button(f"⬆️ Insert {len(good)} record(s)", type="primary", key=f"ins_{table_key}",
                 disabled=st.session_state.get(inserted_key) == upload_fingerprint):
        try:
            out = pd.DataFrame(good)
            out["created_by"] = st.session_state["user"]["username"]
            out["source"] = "bulk"
            db.insert_dataframe(out, cfg["table"])
            st.success(f"Inserted {len(good)} record(s) into {cfg['title']}.")
            st.session_state[inserted_key] = upload_fingerprint
            st.balloons()
        except Exception as e:
            st.error(f"Insert failed: {e}")


# -------------------------------------------------------------- dashboard

def _dedup_area_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse rows that represent the same physical site down to one row, so
    Area (ha) isn't summed once per tree species/type recorded there (these
    tables have one row per species planted at a site, all sharing the same
    area). Two rows count as the same site when Owner's Name (or Site Name,
    for tables that don't have an Owner's Name column) + Area (ha) +
    District + Sector + Cell all match. Used only for the Area (ha) totals;
    every other metric still counts every row.
    """
    if "area_ha" not in df.columns:
        return df
    identity_col = "owner_name" if "owner_name" in df.columns else (
        "site_name" if "site_name" in df.columns else None)
    key_cols = [c for c in (identity_col, "area_ha", "district", "sector", "cell") if c and c in df.columns]
    if not key_cols:
        return df
    out = df.copy()
    out["area_ha"] = pd.to_numeric(out["area_ha"], errors="coerce")
    return out.drop_duplicates(subset=key_cols, keep="first")


def _dedup_roadside_length_df(df: pd.DataFrame) -> pd.DataFrame:
    """Count each district + road name + length combination once."""
    if "length_km" not in df.columns:
        return df
    key_cols = [c for c in ("district", "road_name", "length_km") if c in df.columns]
    if not key_cols:
        return df
    out = df.copy()
    out["length_km"] = pd.to_numeric(out["length_km"], errors="coerce")
    return out.drop_duplicates(subset=key_cols, keep="first")


def _indicator_main_activity_options(df: pd.DataFrame) -> dict[str, set[str]]:
    """Map indicator activity-reference codes to their Main Activity labels."""
    activities = ref.load_activities()
    options: dict[str, set[str]] = {}
    if df.empty or "activity_reference" not in df.columns:
        return options

    refs = df[[column for column in ("implementer", "activity_reference") if column in df.columns]]
    refs = refs.dropna().drop_duplicates()
    for _, row in refs.iterrows():
        activity_ref = str(row.get("activity_reference", "")).strip()
        if not activity_ref:
            continue
        implementer = str(row.get("implementer", "")).strip()
        candidates = activities
        if implementer and "implementer" in candidates:
            candidates = candidates[candidates["implementer"].astype(str).str.casefold() == implementer.casefold()]
        matches = candidates[
            candidates["main_activity"].astype(str).str.match(
                rf"^\s*{re.escape(activity_ref)}(?!\d)", case=False, na=False
            )
        ] if not candidates.empty else candidates
        labels = matches["main_activity"].astype(str).str.strip().unique().tolist() if not matches.empty else []
        for label in labels or [activity_ref]:
            options.setdefault(label, set()).add(activity_ref)
    return dict(sorted(options.items(), key=lambda item: item[0].casefold()))


def _render_indicator_summary_table(
    selected_df: pd.DataFrame, period_source_df: pd.DataFrame, date_filtered: bool = False
):
    """Render the Power BI indicator summary as a searchable HTML table."""
    if selected_df.empty:
        st.info("No indicator records match the current filters.")
        return

    def numeric(series):
        return pd.to_numeric(series, errors="coerce")

    def mean_or_zero(series):
        values = numeric(series).dropna()
        return float(values.mean()) if not values.empty else 0.0

    def sum_or_zero(series):
        return float(numeric(series).sum()) if series is not None else 0.0

    special_terms = (
        "density", "cvc", "districts with integrated climate resilient ",
        "staff from national government and district authorities",
    )
    all_rows = period_source_df.copy()
    chosen_rows = selected_df.copy()
    for frame in (all_rows, chosen_rows):
        if "indicator_sub_indicator" not in frame.columns:
            frame["indicator_sub_indicator"] = (
                frame["indicator"].fillna("").astype(str).str.strip()
                + ":"
                + frame["sub_indicator"].fillna("").astype(str).str.strip()
            )
        frame["_display_indicator"] = frame["indicator_sub_indicator"].fillna("").astype(str).str.strip()
        frame["_report_date"] = pd.to_datetime(frame["reporting_date"], errors="coerce").dt.normalize()
        frame["_actual_num"] = numeric(frame["actual_value"])
        frame["_target_num"] = numeric(frame["lop_target"])
        frame["_year_target_num"] = numeric(frame["target_year"])

    rows_html = []
    group_cols = ["_display_indicator", "indicator_type", "unit"]
    groups = chosen_rows[group_cols].fillna("").drop_duplicates()
    for _, group in groups.iterrows():
        indicator = str(group["_display_indicator"])
        data_mask = pd.Series(True, index=all_rows.index)
        selected_mask = pd.Series(True, index=chosen_rows.index)
        for col in group_cols:
            data_mask &= all_rows[col].fillna("").astype(str).eq(str(group[col]))
            selected_mask &= chosen_rows[col].fillna("").astype(str).eq(str(group[col]))
        data = all_rows[data_mask]
        selected = chosen_rows[selected_mask]
        if data.empty:
            continue
        special = any(term in indicator.casefold() for term in special_terms)
        implementers = sorted(data["implementer"].dropna().astype(str).unique(), key=str.casefold)

        # LoP values ignore the Reporting Date selection, matching the DAX measure.
        total_target = mean_or_zero(data["_target_num"])
        total_actual = (mean_or_zero(data["_actual_num"]) if special
                        else sum_or_zero(data["_actual_num"]))

        # Without a date selection, show the latest reporting date with a target/actual.
        target_date_source = selected if date_filtered else data
        max_target_date = target_date_source.loc[
            target_date_source["_year_target_num"] > 0, "_report_date"
        ].max()
        if special and date_filtered:
            yearly_target_rows = selected
        elif pd.isna(max_target_date):
            yearly_target_rows = data.iloc[0:0]
        else:
            yearly_target_rows = target_date_source[
                target_date_source["_report_date"] == max_target_date
            ]
        target_year = (mean_or_zero(yearly_target_rows["_year_target_num"]) if special
                       else sum_or_zero(yearly_target_rows["_year_target_num"]))

        actual_date_source = selected if date_filtered else data
        max_actual_date = actual_date_source.loc[
            actual_date_source["_actual_num"] > 0, "_report_date"
        ].max()
        if special and date_filtered:
            yearly_actual_rows = selected
        else:
            yearly_actual_rows = (actual_date_source[actual_date_source["_report_date"] == max_actual_date]
                                  if not pd.isna(max_actual_date) else data.iloc[0:0])
        yearly_actual = (mean_or_zero(yearly_actual_rows["_actual_num"]) if special
                         else sum_or_zero(yearly_actual_rows["_actual_num"]))

        lop_progress = total_actual / total_target if total_target else 0.0
        yearly_progress = yearly_actual / target_year if target_year else 0.0
        pct_text = f"{lop_progress:.0%}"
        yearly_pct_text = f"{yearly_progress:.0%}"
        lop_width = min(max(lop_progress, 0.0), 1.0) * 100
        yearly_degrees = min(max(yearly_progress, 0.0), 1.0) * 360
        color = "#27ae60" if lop_progress > 0.6 else "#f1c40f" if lop_progress > 0.3 else "#e74c3c"
        yearly_color = "#27ae60" if yearly_progress > 0.6 else "#f1c40f" if yearly_progress > 0.3 else "#e74c3c"
        chips = []
        chip_colors = {
            "ICRAF": ("#d6e4ff", "#1f4e79"), "RFA": ("#e8f8f5", "#117a65"),
            "CORDAID": ("#fdebd0", "#9c640c"), "IUCN": ("#eafaf1", "#1e8449"),
            "Enabel/IUCN": ("#f5eef8", "#6c3483"),
        }
        for implementer in implementers:
            bg, fg = chip_colors.get(implementer, ("#eef1f5", "#444"))
            chips.append(
                f'<span class="chip" style="background:{bg};color:{fg}">{html.escape(implementer)}</span>'
            )
        unit = html.escape(str(group["unit"]))
        indicator_type = html.escape(str(group["indicator_type"]))
        rows_html.append(
            "<tr class='data-row'>"
            f'<td class="indicator">● {html.escape(indicator)}</td>'
            f"<td>{unit}</td><td>{total_target:,.0f}</td><td class='actual'>{total_actual:,.0f}</td>"
            f"<td>{''.join(chips)}</td><td><span class='chip' style='background:#eef4ff;color:#2b579a'>{indicator_type}</span></td>"
            f'<td><div class="progress"><div class="bar" style="width:{lop_width:.1f}%;background:{color}"></div></div>'
            f'<span style="color:{color};font-weight:600">{pct_text}</span></td>'
            f'<td><div class="pie" style="background:conic-gradient({yearly_color} 0deg {yearly_degrees:.1f}deg,#eee {yearly_degrees:.1f}deg 360deg)"></div>'
            f'<span style="color:{yearly_color};font-weight:600">{yearly_pct_text}</span></td></tr>'
        )

    table_html = """
    <style>
      body{font-family:Segoe UI,Arial,sans-serif;margin:0;color:#263442}
      #searchBox{width:250px;padding:7px 9px;margin:0 0 10px;border:1px solid #cbd5df;border-radius:6px;font-size:13px}
      .table-wrap{overflow:auto;max-height:650px;border:1px solid #e0e0e0;border-radius:7px}
      table{width:100%;border-collapse:separate;border-spacing:0;background:#fff;font-size:13px}
      th,td{border-bottom:1px solid #e6e9ed;padding:10px;text-align:left;vertical-align:middle}
      th{position:sticky;top:0;z-index:2;background:#f8fafc;color:#6b7785;font-size:11px;letter-spacing:.03em;white-space:nowrap}
      tr:hover td{background:#f9fbff}.indicator{font-weight:600;min-width:260px}
      .chip{display:inline-block;padding:4px 8px;border-radius:10px;font-size:11px;margin:2px;white-space:nowrap}
      .actual{font-weight:600;color:#2b579a}.progress{display:inline-block;width:120px;background:#eee;border-radius:10px;height:8px;margin-right:8px;overflow:hidden;vertical-align:middle}
      .bar{height:100%}.pie{display:inline-block;width:30px;height:30px;border-radius:50%;margin-right:8px;vertical-align:middle;position:relative}
      .pie:after{content:"";position:absolute;inset:5px;border-radius:50%;background:#fff}
    </style>
    <input id="searchBox" type="text" placeholder="Search indicator..." oninput="filterTable()">
    <div class="table-wrap"><table><thead><tr>
      <th>INDICATOR NAME</th><th>UNIT</th><th>LoP TARGET</th><th>ACTUAL</th><th>RESPONSIBLE</th><th>INDICATOR TYPE</th><th>LoP PROGRESS</th><th>YEARLY PROGRESS</th>
    </tr></thead><tbody id="indicatorRows">__ROWS__</tbody></table></div>
    <script>
      function filterTable(){const q=document.getElementById('searchBox').value.toLowerCase();
        document.querySelectorAll('.data-row').forEach(r=>r.style.display=r.innerText.toLowerCase().includes(q)?'':'none');}
    </script>
    """.replace("__ROWS__", "".join(rows_html))
    height = min(740, max(220, 100 + len(rows_html) * 48))
    components.html(table_html, height=height, scrolling=True)


def _render_activity_progress_charts(activity_df: pd.DataFrame):
    """Show activity execution counts and completion rates by reporting quarter."""
    chart_df = activity_df.copy()
    chart_df["_progress"] = (
        chart_df["execution_progress"].fillna("Unknown").astype(str).str.strip()
        .replace("", "Unknown")
    )
    chart_df["_completed"] = chart_df["_progress"].str.casefold().eq("completed")
    chart_df["_quarter"] = pd.to_datetime(
        chart_df["reporting_date"], errors="coerce"
    ).dt.to_period("Q").map(
        lambda period: f"{period.year}-Q{period.quarter}" if not pd.isna(period) else None
    )

    main_df = chart_df[chart_df["main_activity"].fillna("").astype(str).str.strip().ne("")]
    sub_df = chart_df[chart_df["sub_activity"].fillna("").astype(str).str.strip().ne("")]

    sub_counts = (sub_df.groupby("main_activity", as_index=False)
                  .agg(completed_sub_activities=("_completed", "sum"),
                       total_sub_activities=("sub_activity", "size")))
    main_dates = (main_df.assign(_end_date=pd.to_datetime(main_df["end_date"], errors="coerce"))
                  .groupby("main_activity")["_end_date"].max())
    main_summary = (main_df[["main_activity"]].drop_duplicates()
                    .merge(sub_counts, on="main_activity", how="left"))
    main_summary["completed_sub_activities"] = main_summary["completed_sub_activities"].fillna(0)
    main_summary["total_sub_activities"] = main_summary["total_sub_activities"].fillna(0)
    main_summary["progress"] = main_summary["completed_sub_activities"].div(
        main_summary["total_sub_activities"].where(main_summary["total_sub_activities"].ne(0))
    ).fillna(0)
    main_summary["end_date"] = main_summary["main_activity"].map(main_dates)

    today = pd.Timestamp(dt.date.today())

    def activity_status(row):
        progress = row["progress"]
        end_date = row["end_date"]
        if progress == 1:
            return "Completed"
        if pd.isna(end_date):
            return "End Date Missing"
        if progress == 0:
            return "Not Started and Delayed" if end_date >= today else "Not Started"
        return "Started Progress On Track" if end_date >= today else "Started Progress Delayed"

    main_summary["status"] = main_summary.apply(activity_status, axis=1)

    st.markdown("#### Activity execution progress")
    pie_cols = st.columns(2)
    with pie_cols[0]:
        if main_summary.empty:
            st.info("No Main Activities in the current filter.")
        else:
            counts = (main_summary.groupby("status", as_index=False).size()
                      .rename(columns={"size": "main_activities"}))
            fig = px.pie(
                counts, names="status", values="main_activities", hole=0.42,
                title="Main Activities by Execution Progress", color_discrete_sequence=ui.IUCN_PALETTE,
            )
            fig.update_traces(textinfo="label+value+percent", textposition="inside")
            fig.update_layout(margin=dict(t=55, b=0), legend_title_text="Main Activity Status")
            ui.style_iucn_chart(fig)
            st.plotly_chart(fig, use_container_width=True)
    with pie_cols[1]:
        if sub_df.empty:
            st.info("No Sub Activities in the current filter.")
        else:
            counts = (sub_df.groupby("_progress", as_index=False).size()
                      .rename(columns={"size": "sub_activities"}))
            fig = px.pie(
                counts, names="_progress", values="sub_activities", hole=0.42,
                title="Sub Activities by Execution Progress", color_discrete_sequence=ui.IUCN_PALETTE,
            )
            fig.update_traces(textinfo="label+value+percent", textposition="inside")
            fig.update_layout(margin=dict(t=55, b=0), legend_title_text="Execution Progress")
            ui.style_iucn_chart(fig)
            st.plotly_chart(fig, use_container_width=True)

    if not main_summary.empty:
        st.caption("Main Activity progress = completed subactivities ÷ all corresponding subactivities.")
        display_summary = main_summary[[
            "main_activity", "completed_sub_activities", "total_sub_activities", "progress", "status"
        ]].rename(columns={
            "main_activity": "Main Activity",
            "completed_sub_activities": "Completed Sub Activities",
            "total_sub_activities": "Total Sub Activities",
            "progress": "Progress %",
            "status": "Status",
        })
        display_summary["Progress %"] = display_summary["Progress %"].map(lambda value: f"{value:.0%}")
        st.dataframe(display_summary, use_container_width=True, hide_index=True)

    st.markdown("#### Completed activities by reporting quarter")
    quarter_cols = st.columns(2)
    main_quarterly = (sub_df.dropna(subset=["_quarter"])
                      .groupby(["_quarter", "main_activity"], as_index=False)
                      .agg(completed=("_completed", "sum"), total=("_completed", "size")))
    if not main_quarterly.empty:
        main_quarterly["_activity_pct"] = main_quarterly["completed"] / main_quarterly["total"] * 100
        main_quarterly = (main_quarterly.groupby("_quarter", as_index=False)
                          .agg(completed_pct=("_activity_pct", "mean"),
                               activities=("main_activity", "nunique")))
    sub_quarterly = (sub_df.dropna(subset=["_quarter"]).groupby("_quarter", as_index=False).agg(
        completed=("_completed", "sum"), total=("_completed", "size")
    ))
    if not sub_quarterly.empty:
        sub_quarterly["completed_pct"] = sub_quarterly["completed"] / sub_quarterly["total"] * 100

    for column, quarterly, title, hover_data in (
        (quarter_cols[0], main_quarterly, "Average Main Activity Completion Rate", {"activities": True}),
        (quarter_cols[1], sub_quarterly, "Sub Activity Completion Rate", {"completed": True, "total": True}),
    ):
        with column:
            if quarterly.empty:
                st.info(f"No reporting quarter available for {title.lower()}.")
                continue
            fig = px.bar(
                quarterly, x="_quarter", y="completed_pct", title=title,
                text=quarterly["completed_pct"].map(lambda value: f"{value:.0f}%"),
                color_discrete_sequence=ui.IUCN_PALETTE,
                hover_data={**hover_data, "completed_pct": ":.1f"},
            )
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_yaxes(title="Completed", ticksuffix="%", range=[0, 100])
            fig.update_xaxes(title="Year-Quarter", categoryorder="array", categoryarray=sorted(quarterly["_quarter"]))
            fig.update_layout(margin=dict(t=55, b=0), showlegend=False)
            ui.style_iucn_chart(fig)
            st.plotly_chart(fig, use_container_width=True)


def render_dashboard(table_key: str):
    ui.apply_iucn_styles()
    if table_key == "beneficiaries":
        # Keep long household counts compact enough to fit their summary card.
        st.markdown("""<style>
        [data-testid="stMetricValue"] { font-size: 1.45rem; }
        </style>""", unsafe_allow_html=True)
    cfg = schemas.TABLES[table_key]
    count_label = "Beneficiaries" if table_key == "beneficiaries" else "Records"
    try:
        df = db.run_query(f"SELECT * FROM `{cfg['table']}`")
    except Exception as e:
        st.error(f"Could not load data: {e}")
        return

    if df.empty:
        st.info(f"No {count_label.lower()} in this table yet.")
        return

    indicator_type_filter = []
    indicator_filter = []
    proj = []
    main_activity = []
    interv = []
    beneficiary_category = []
    indicator_dates = []
    activity_quarters = []
    activity_codes = []
    if table_key == "indicators":
        # Mirror the Power BI calculated column used by the summary table and
        # Indicator slicer: Indicator & ":" & Sub Indicator.
        df["indicator_sub_indicator"] = (
            df["indicator"].fillna("").astype(str).str.strip()
            + ":"
            + df["sub_indicator"].fillna("").astype(str).str.strip()
        )
        filter_columns = st.columns(4)
        reporting_periods = pd.to_datetime(df["reporting_date"], errors="coerce").dt.to_period("Q")
        date_values = sorted(
            {f"{period.year}-Q{period.quarter}" for period in reporting_periods.dropna()},
            key=lambda value: (int(value[:4]), int(value[-1])),
        )
        with filter_columns[0]:
            indicator_dates = st.multiselect("Reporting Date", date_values, key=f"d_date_{table_key}")
        with filter_columns[1]:
            impl = st.multiselect("Implementer", sorted(df["implementer"].dropna().astype(str).unique(), key=str.casefold), key=f"d_i_{table_key}")
        with filter_columns[2]:
            indicator_type_filter = st.multiselect("Indicator Type", sorted(df["indicator_type"].dropna().astype(str).unique(), key=str.casefold), key=f"d_type_{table_key}")
        with filter_columns[3]:
            indicator_filter = st.multiselect("Indicator", sorted(df["indicator_sub_indicator"].dropna().astype(str).unique(), key=str.casefold), key=f"d_indicator_{table_key}")
    elif table_key == "activities":
        df["activity_code"] = df["main_activity"].fillna("").astype(str).str.strip().str.slice(0, 5)
        filter_columns = st.columns(3)
        reporting_periods = pd.to_datetime(df["reporting_date"], errors="coerce").dt.to_period("Q")
        quarter_values = sorted(
            {f"{period.year}-Q{period.quarter}" for period in reporting_periods.dropna()},
            key=lambda value: (int(value[:4]), int(value[-1])),
        )
        with filter_columns[0]:
            activity_quarters = st.multiselect(
                "Reporting Date (Year-Quarter)", quarter_values, key=f"d_date_{table_key}"
            )
        with filter_columns[1]:
            impl = st.multiselect(
                "Implementer",
                sorted(df["implementer"].dropna().astype(str).unique(), key=str.casefold),
                key=f"d_i_{table_key}",
            )
        with filter_columns[2]:
            activity_codes = st.multiselect(
                "Activity Code",
                sorted(
                    [code for code in df["activity_code"].dropna().astype(str).unique() if code.strip()],
                    key=str.casefold,
                ),
                key=f"d_activity_code_{table_key}",
            )
    else:
        filter_columns = st.columns(4 if table_key == "beneficiaries" else 3)
        f1, f2, f3 = filter_columns[:3]
        with f1:
            proj = st.multiselect("Project", sorted(df["project"].dropna().unique()) if "project" in df else [], key=f"d_p_{table_key}")
        with f2:
            impl = st.multiselect("Implementer", sorted(df["implementer"].dropna().unique()) if "implementer" in df else [], key=f"d_i_{table_key}")
        with f3:
            if "intervention" in df.columns:
                pool = df[df["implementer"].isin(impl)] if impl else df
                interv = st.multiselect("Intervention", sorted(pool["intervention"].dropna().unique()), key=f"d_v_{table_key}")
            else:
                st.caption("This table has no Intervention column.")
    if table_key == "beneficiaries":
        with filter_columns[3]:
            beneficiary_category = st.multiselect(
                "Beneficiary Category",
                sorted(df["beneficiary_category"].dropna().unique())
                if "beneficiary_category" in df.columns else [],
                key=f"d_bc_{table_key}",
            )

    fdf = df.copy()
    if table_key == "beneficiaries" and "district" in fdf.columns:
        # Normalize casing before counts and grouping so case variants become one district.
        fdf["district"] = fdf["district"].astype("string").str.strip().str.title()
    if proj:
        fdf = fdf[fdf["project"].isin(proj)]
    if impl:
        fdf = fdf[fdf["implementer"].isin(impl)]
    if table_key == "activities" and activity_quarters:
        date_periods = pd.to_datetime(fdf["reporting_date"], errors="coerce").dt.to_period("Q")
        period_text = date_periods.map(
            lambda period: f"{period.year}-Q{period.quarter}" if not pd.isna(period) else None
        )
        fdf = fdf[period_text.isin(activity_quarters)]
    if table_key == "activities" and activity_codes:
        fdf = fdf[fdf["activity_code"].astype(str).isin(activity_codes)]
    if interv:
        fdf = fdf[fdf["intervention"].isin(interv)]
    if table_key == "indicators" and indicator_type_filter:
        fdf = fdf[fdf["indicator_type"].isin(indicator_type_filter)]
    if table_key == "indicators" and indicator_filter:
        fdf = fdf[fdf["indicator_sub_indicator"].isin(indicator_filter)]
    if beneficiary_category:
        fdf = fdf[fdf["beneficiary_category"].isin(beneficiary_category)]
    indicator_period_df = fdf.copy() if table_key == "indicators" else None
    if table_key == "indicators" and indicator_dates:
        date_periods = pd.to_datetime(fdf["reporting_date"], errors="coerce").dt.to_period("Q")
        period_text = date_periods.map(
            lambda period: f"{period.year}-Q{period.quarter}" if not pd.isna(period) else None
        )
        fdf = fdf[period_text.isin(indicator_dates)]
    district_counts = None
    if table_key == "beneficiaries" and "district" in fdf.columns:
        district_counts = (fdf.dropna(subset=["district"])
                           .groupby("district").size()
                           .rename("records").reset_index())
        district_counts = district_counts[district_counts["records"] > 100]

    # headline metrics
    numeric_headline = [
        ("num_trees_planted", "Trees planted"),
        ("num_survived_trees", "Trees survived"),
        ("area_ha", "Area (ha)"),
        ("num_participants", "Participants"),
        ("persons_in_hh", "Persons in HH"),
        ("actual_value", "Actual value"),
    ]
    if table_key == "roadsides":
        numeric_headline.insert(0, ("length_km", "Length (Km)"))
    area_dedup_df = _dedup_area_df(fdf)
    roadside_length_df = _dedup_roadside_length_df(fdf) if table_key == "roadsides" else fdf
    if table_key == "coperatives":
        metrics = [("Cooperative/Group", fdf["cooperative_group"].nunique(dropna=True)
                    if "cooperative_group" in fdf.columns else 0)]
        for col, label in (("total_workers", "Total workers"),
                           ("total_female", "Total number of Female"),
                           ("total_male", "Total number of Male")):
            total = pd.to_numeric(fdf[col], errors="coerce").sum() if col in fdf.columns else 0
            metrics.append((label, f"{total:,.0f}"))
    else:
        metrics = [(count_label, f"{len(fdf):,}")]
        for col, label in numeric_headline:
            if col not in fdf.columns or not pd.to_numeric(fdf[col], errors="coerce").notna().any():
                continue
            if col == "area_ha":
                total = pd.to_numeric(area_dedup_df["area_ha"], errors="coerce").sum()
            elif col == "length_km":
                total = pd.to_numeric(roadside_length_df["length_km"], errors="coerce").sum()
            else:
                total = pd.to_numeric(fdf[col], errors="coerce").sum()
            metrics.append((label, f"{total:,.0f}"))
        if "implementer" in fdf.columns:
            metrics.append(("Implementers", fdf["implementer"].nunique()))
        if "district" in fdf.columns:
            district_total = (len(district_counts) if district_counts is not None
                              else fdf["district"].nunique())
            metrics.append(("Districts", district_total))

    if table_key not in ("indicators", "activities"):
        mcols = st.columns(min(len(metrics), 5))
        for (label, value), mc in zip(metrics[:5], mcols):
            mc.metric(label, value)

    if fdf.empty:
        st.warning(f"No {count_label.lower()} match the current filters.")
        return

    st.divider()

    if table_key == "indicators":
        st.markdown("#### Indicator progress summary")
        _render_indicator_summary_table(fdf, indicator_period_df, date_filtered=bool(indicator_dates))
    elif table_key == "activities":
        _render_activity_progress_charts(fdf)

    # pick a sensible measure for the charts
    measure = ("total_workers" if table_key == "coperatives" and "total_workers" in fdf.columns else
               next((c for c, _ in numeric_headline
                    if c in fdf.columns and pd.to_numeric(fdf[c], errors="coerce").notna().any()), None)
               )

    g1, g2 = st.columns(2)
    with g1:
        if "implementer" in fdf.columns and table_key not in ("indicators", "activities"):
            if table_key == "coperatives":
                agg = (fdf.assign(_workers=pd.to_numeric(fdf["total_workers"], errors="coerce"))
                       .groupby("implementer", as_index=False)["_workers"].sum()
                       .rename(columns={"_workers": "total_workers"}))
                fig = px.bar(agg, x="implementer", y="total_workers", title="Total workers by Implementer",
                             text_auto=".2s", color_discrete_sequence=ui.IUCN_PALETTE)
            elif measure:
                source_df = (area_dedup_df if measure == "area_ha" else
                             roadside_length_df if measure == "length_km" else fdf)
                agg = (source_df.assign(_m=pd.to_numeric(source_df[measure], errors="coerce"))
                          .groupby("implementer", as_index=False)["_m"].sum()
                          .rename(columns={"_m": measure}).sort_values(measure, ascending=False))
                fig = px.bar(agg, x="implementer", y=measure, title=f"{measure} by Implementer",
                             text_auto=".2s", color_discrete_sequence=ui.IUCN_PALETTE)
                if measure == "area_ha":
                    fig.update_layout(annotations=[dict(
                        text="Deduplicated by owner/site + area + location",
                        xref="paper", yref="paper", x=0, y=1.08, showarrow=False,
                        font=dict(size=10, color="gray"))])
                elif measure == "length_km":
                    fig.update_layout(annotations=[dict(
                        text="Deduplicated by district + road name + length",
                        xref="paper", yref="paper", x=0, y=1.08, showarrow=False,
                        font=dict(size=10, color="gray"))])
            else:
                agg = fdf.groupby("implementer", as_index=False).size().rename(columns={"size": "records"})
                fig = px.bar(agg, x="implementer", y="records", title=f"{count_label} by Implementer",
                             text_auto=".2s", color_discrete_sequence=ui.IUCN_PALETTE)
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(xaxis_title="", margin=dict(t=50, b=0))
            ui.style_iucn_chart(fig)
            st.plotly_chart(fig, use_container_width=True)
    with g2:
        if "project" in fdf.columns and table_key not in ("indicators", "activities"):
            if table_key == "coperatives":
                agg = (fdf.assign(_workers=pd.to_numeric(fdf["total_workers"], errors="coerce"))
                       .groupby("project", as_index=False)["_workers"].sum()
                       .rename(columns={"_workers": "total_workers"}))
                fig = px.pie(agg, names="project", values="total_workers", hole=0.45,
                             title="Total workers by Project", color_discrete_sequence=ui.IUCN_PALETTE)
            else:
                agg = fdf.groupby("project", as_index=False).size().rename(columns={"size": "records"})
                fig = px.pie(agg, names="project", values="records", hole=0.45, title=f"{count_label} by Project",
                             color_discrete_sequence=ui.IUCN_PALETTE)
            fig.update_traces(textinfo="label+value", textposition="inside")
            fig.update_layout(margin=dict(t=50, b=0))
            ui.style_iucn_chart(fig)
            st.plotly_chart(fig, use_container_width=True)

    g3, g4 = st.columns(2)
    with g3:
        if "intervention" in fdf.columns and fdf["intervention"].notna().any():
            if table_key == "roadsides":
                agg = (roadside_length_df.assign(
                           _length=pd.to_numeric(roadside_length_df["length_km"], errors="coerce"))
                       .groupby("intervention", as_index=False)["_length"].sum()
                       .rename(columns={"_length": "length_km"})
                       .sort_values("length_km", ascending=True).tail(12))
                fig = px.bar(agg, x="length_km", y="intervention", orientation="h",
                             title="Total Length (Km) by Intervention", text_auto=".2s",
                             color_discrete_sequence=ui.IUCN_PALETTE)
            elif table_key == "coperatives":
                agg = (fdf.assign(_workers=pd.to_numeric(fdf["total_workers"], errors="coerce"))
                       .groupby("intervention", as_index=False)["_workers"].sum()
                       .rename(columns={"_workers": "total_workers"})
                       .sort_values("total_workers", ascending=True).tail(12))
                fig = px.bar(agg, x="total_workers", y="intervention", orientation="h",
                             title="Total workers by Intervention (top 12)", text_auto=".2s",
                             color_discrete_sequence=ui.IUCN_PALETTE)
            else:
                agg = (fdf.groupby("intervention", as_index=False).size()
                          .rename(columns={"size": "records"})
                          .sort_values("records", ascending=True).tail(12))
                fig = px.bar(agg, x="records", y="intervention", orientation="h",
                             title=f"{count_label} by Intervention (top 12)", text_auto=".2s",
                             color_discrete_sequence=ui.IUCN_PALETTE)
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(yaxis_title="", margin=dict(t=50, b=0))
            ui.style_iucn_chart(fig)
            st.plotly_chart(fig, use_container_width=True)
    with g4:
        if "district" in fdf.columns and fdf["district"].notna().any():
            if table_key == "coperatives":
                agg = (fdf.assign(_workers=pd.to_numeric(fdf["total_workers"], errors="coerce"))
                       .groupby("district", as_index=False)["_workers"].sum()
                       .rename(columns={"_workers": "total_workers"})
                       .sort_values("total_workers", ascending=False).head(12))
                fig = px.bar(agg, x="district", y="total_workers", title="Total workers by District (top 12)",
                             text_auto=".2s", color_discrete_sequence=ui.IUCN_PALETTE)
            else:
                agg = district_counts if district_counts is not None else (
                fdf.groupby("district", as_index=False).size()
                   .rename(columns={"size": "records"})
                )
                agg = agg.sort_values("records", ascending=False).head(12)
            if table_key == "coperatives" or not agg.empty:
                if table_key != "coperatives":
                    fig = px.bar(agg, x="district", y="records", title=f"{count_label} by District (over 100)",
                                 text_auto=".2s", color_discrete_sequence=ui.IUCN_PALETTE)

                fig.update_traces(textposition="outside", cliponaxis=False)
                fig.update_layout(xaxis_title="", margin=dict(t=50, b=0))
                ui.style_iucn_chart(fig)
                st.plotly_chart(fig, use_container_width=True)

    if "gender" in fdf.columns and fdf["gender"].notna().any():
        if table_key == "coperatives":
            agg = (fdf.assign(_workers=pd.to_numeric(fdf["total_workers"], errors="coerce"))
                   .groupby("gender", as_index=False)["_workers"].sum()
                   .rename(columns={"_workers": "total_workers"}))
            fig = px.bar(agg, x="gender", y="total_workers", title="Total workers by Gender", height=300,
                         text_auto=".2s", color_discrete_sequence=ui.IUCN_PALETTE)
        else:
            agg = fdf.groupby("gender", as_index=False).size().rename(columns={"size": "records"})
            fig = px.bar(agg, x="gender", y="records", title=f"{count_label} by Gender", height=300,
                         text_auto=".2s", color_discrete_sequence=ui.IUCN_PALETTE)
        fig.update_traces(textposition="outside", cliponaxis=False)
        ui.style_iucn_chart(fig)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown(f"#### Records ({len(fdf):,})")
    st.dataframe(fdf, use_container_width=True, height=380)
    st.download_button(
        f"⬇️ Download filtered {count_label.lower()} (CSV)",
        fdf.to_csv(index=False).encode(),
        file_name=f"{cfg['table']}_filtered.csv",
        key=f"dl_{table_key}",
    )

    # ---------------------------------------------------- attachments
    file_fields = [fl for fl in cfg["fields"] if fl["ftype"] == "file"]
    if file_fields:
        st.divider()
        with st.expander("📎 Download an attached file"):
            fc1, fc2 = st.columns(2)
            with fc1:
                chosen_label = st.selectbox(
                    "Field", [fl["label"] for fl in file_fields], key=f"att_field_{table_key}")
            chosen_col = next(fl["col"] for fl in file_fields if fl["label"] == chosen_label)
            options = sorted(fdf[chosen_col].dropna().unique()) if chosen_col in fdf.columns else []
            with fc2:
                chosen_file = st.selectbox("File", options, key=f"att_file_{table_key}") if options else None
            if not options:
                st.caption("No files uploaded for this field yet (in the current filter).")
            elif chosen_file:
                data = filestore.read_file(chosen_file)
                if data is None:
                    st.warning(
                        "This file isn't on disk right now. If the app was recently "
                        "redeployed, uploaded files don't survive that on the current "
                        "hosting setup — see the note in filestore.py."
                    )
                else:
                    st.download_button(
                        f"⬇️ Download {chosen_file}", data=data, file_name=chosen_file,
                        key=f"att_dl_{table_key}",
                    )
