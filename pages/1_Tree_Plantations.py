import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.express as px
import streamlit as st

import auth
import db
import schemas
import ui

auth.require_login()
ui.apply_iucn_styles()

st.title("🌳 Tree Plantations")
st.caption("Combined totals across Tree Plantation, BSO, Silvo, AF Demo, and Roadsides.")

tree_table_keys = ("silvo", "bso", "roadsides", "tree_plantation", "af_demo")
tree_frames = {}
for key in tree_table_keys:
    cfg = schemas.TABLES[key]
    try:
        tree_frames[key] = db.run_query(f"SELECT * FROM `{cfg['table']}`")
    except Exception as exc:
        st.warning(f"Could not load {cfg['title']} summary: {exc}")
        tree_frames[key] = pd.DataFrame()

def sum_numeric(frames, column):
    return sum(
        pd.to_numeric(frame[column], errors="coerce").sum()
        for frame in frames if column in frame.columns
    )

tree_total = sum_numeric(
    [tree_frames[key] for key in tree_table_keys if key != "roadsides"], "num_trees_planted"
)
tree_total += sum_numeric([tree_frames["roadsides"]], "num_trees")

area_total = 0.0
area_by_intervention = []
for key, frame in tree_frames.items():
    if frame.empty:
        continue
    data = frame.copy()
    if key == "roadsides":
        data["length_km"] = pd.to_numeric(data.get("length_km"), errors="coerce")
        dedup_keys = [column for column in ("district", "road_name", "length_km") if column in data.columns]
        if dedup_keys:
            data = data.drop_duplicates(subset=dedup_keys, keep="first")
        data["_area"] = data["length_km"]
    else:
        data["area_ha"] = pd.to_numeric(data.get("area_ha"), errors="coerce")
        identity = "owner_name" if "owner_name" in data.columns else (
            "site_name" if "site_name" in data.columns else None
        )
        dedup_keys = [column for column in (identity, "area_ha", "district", "sector", "cell")
                      if column and column in data.columns]
        if dedup_keys:
            data = data.drop_duplicates(subset=dedup_keys, keep="first")
        data["_area"] = data["area_ha"]
    area_total += data["_area"].sum()
    if "intervention" in data.columns:
        grouped = data.groupby("intervention", dropna=True)["_area"].sum()
        area_by_intervention.extend((name, value) for name, value in grouped.items())

metrics = st.columns(2)
metrics[0].metric("Total trees planted", f"{tree_total:,.0f}")
metrics[1].metric("Combined Area (Ha)", f"{area_total:,.2f}")

if area_by_intervention:
    area_df = (pd.DataFrame(area_by_intervention, columns=["Intervention", "Area (Ha)"])
               .groupby("Intervention", as_index=False)["Area (Ha)"].sum()
               .sort_values("Area (Ha)", ascending=False))
    fig = px.bar(area_df, x="Intervention", y="Area (Ha)", title="Combined Area (Ha) by Intervention",
                 text_auto=".2s", color_discrete_sequence=["#087fae"])
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title="", margin=dict(t=50, b=10), uniformtext_minsize=9,
                      uniformtext_mode="hide")
    ui.style_iucn_chart(fig)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No tree plantation records are available yet.")

