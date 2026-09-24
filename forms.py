"""
Schema-driven UI engine reused by all nine data pages:
    render_form(table_key)      - submit one record at a time
    render_upload(table_key)    - download template + bulk upload Excel
    render_dashboard(table_key) - metrics/charts/table with slicers
"""
from __future__ import annotations
import datetime as dt
import re

import pandas as pd
import plotly.express as px
import streamlit as st

import config
import db
import schemas
import templates
import reference_data as ref
import filestore
import mapwidget

CASCADE_FIRST = {"implementer", "district", "tree_origin"}


# ----------------------------------------------------------------- helpers

def _ver(table_key: str) -> int:
    return st.session_state.get(f"_ver_{table_key}", 0)


def _bump(table_key: str):
    st.session_state[f"_ver_{table_key}"] = _ver(table_key) + 1


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
            if ft == "project":
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
    if st.button("✅ Submit record", type="primary", key=f"{pfx}_submit"):
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


def _validate(cfg, rec: dict, strict_ref: bool = True) -> list[str]:
    errs: list[str] = []
    by_type = {fl["ftype"]: fl["col"] for fl in cfg["fields"]}

    for fl in cfg["fields"]:
        if fl["req"] and _blank(rec.get(fl["col"])):
            errs.append(f"'{fl['label']}' is required")

    proj = rec.get("project")
    if not _blank(proj) and str(proj).strip() not in config.PROJECTS:
        errs.append(f"Project '{proj}' is not one of {', '.join(config.PROJECTS)}")

    impl = rec.get("implementer")
    interv = rec.get("intervention")
    if not _blank(impl) and not ref.validate_implementer(impl):
        errs.append(f"Implementer '{impl}' is not in the reference list")
    elif not _blank(impl) and not _blank(interv) and not ref.validate_intervention(impl, interv):
        errs.append(f"Intervention '{interv}' does not belong to Implementer '{impl}'")

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

    if st.button(f"⬆️ Insert {len(good)} record(s)", type="primary", key=f"ins_{table_key}"):
        try:
            out = pd.DataFrame(good)
            out["created_by"] = st.session_state["user"]["username"]
            out["source"] = "bulk"
            db.insert_dataframe(out, cfg["table"])
            st.success(f"Inserted {len(good)} record(s) into {cfg['title']}.")
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


def render_dashboard(table_key: str):
    cfg = schemas.TABLES[table_key]
    try:
        df = db.run_query(f"SELECT * FROM `{cfg['table']}`")
    except Exception as e:
        st.error(f"Could not load data: {e}")
        return

    if df.empty:
        st.info("No records in this table yet.")
        return

    f1, f2, f3 = st.columns(3)
    with f1:
        proj = st.multiselect("Project", sorted(df["project"].dropna().unique())
                              if "project" in df else [], key=f"d_p_{table_key}")
    with f2:
        impl = st.multiselect("Implementer", sorted(df["implementer"].dropna().unique())
                              if "implementer" in df else [], key=f"d_i_{table_key}")
    with f3:
        if "intervention" in df.columns:
            pool = df[df["implementer"].isin(impl)] if impl else df
            interv = st.multiselect("Intervention", sorted(pool["intervention"].dropna().unique()),
                                    key=f"d_v_{table_key}")
        else:
            interv = []
            st.caption("This table has no Intervention column.")

    fdf = df.copy()
    if proj:
        fdf = fdf[fdf["project"].isin(proj)]
    if impl:
        fdf = fdf[fdf["implementer"].isin(impl)]
    if interv:
        fdf = fdf[fdf["intervention"].isin(interv)]

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
    metrics = [("Records", f"{len(fdf):,}")]
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
        metrics.append(("Districts", fdf["district"].nunique()))

    mcols = st.columns(min(len(metrics), 5))
    for (label, value), mc in zip(metrics[:5], mcols):
        mc.metric(label, value)

    if fdf.empty:
        st.warning("No records match the current filters.")
        return

    st.divider()

    # pick a sensible measure for the charts
    measure = next((c for c, _ in numeric_headline
                    if c in fdf.columns and pd.to_numeric(fdf[c], errors="coerce").notna().any()), None)

    g1, g2 = st.columns(2)
    with g1:
        if "implementer" in fdf.columns:
            if measure:
                source_df = (area_dedup_df if measure == "area_ha" else
                             roadside_length_df if measure == "length_km" else fdf)
                agg = (source_df.assign(_m=pd.to_numeric(source_df[measure], errors="coerce"))
                          .groupby("implementer", as_index=False)["_m"].sum()
                          .rename(columns={"_m": measure}).sort_values(measure, ascending=False))
                fig = px.bar(agg, x="implementer", y=measure, title=f"{measure} by Implementer")
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
                fig = px.bar(agg, x="implementer", y="records", title="Records by Implementer")
            fig.update_layout(xaxis_title="", margin=dict(t=50, b=0))
            st.plotly_chart(fig, use_container_width=True)
    with g2:
        if "project" in fdf.columns:
            agg = fdf.groupby("project", as_index=False).size().rename(columns={"size": "records"})
            fig = px.pie(agg, names="project", values="records", hole=0.45, title="Records by Project")
            fig.update_layout(margin=dict(t=50, b=0))
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
                             title="Total Length (Km) by Intervention")
            else:
                agg = (fdf.groupby("intervention", as_index=False).size()
                          .rename(columns={"size": "records"})
                          .sort_values("records", ascending=True).tail(12))
                fig = px.bar(agg, x="records", y="intervention", orientation="h",
                             title="Records by Intervention (top 12)")
            fig.update_layout(yaxis_title="", margin=dict(t=50, b=0))
            st.plotly_chart(fig, use_container_width=True)
    with g4:
        if "district" in fdf.columns and fdf["district"].notna().any():
            agg = (fdf.groupby("district", as_index=False).size()
                      .rename(columns={"size": "records"})
                      .sort_values("records", ascending=False).head(12))
            fig = px.bar(agg, x="district", y="records", title="Records by District (top 12)")
            fig.update_layout(xaxis_title="", margin=dict(t=50, b=0))
            st.plotly_chart(fig, use_container_width=True)

    if "gender" in fdf.columns and fdf["gender"].notna().any():
        agg = fdf.groupby("gender", as_index=False).size().rename(columns={"size": "records"})
        fig = px.bar(agg, x="gender", y="records", title="Records by Gender", height=300)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.markdown(f"#### Records ({len(fdf):,})")
    st.dataframe(fdf, use_container_width=True, height=380)
    st.download_button(
        "⬇️ Download filtered records (CSV)",
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
