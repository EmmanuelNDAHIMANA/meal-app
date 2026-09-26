import pandas as pd
import streamlit as st

import auth
import config
import db
import schemas
import ui

st.set_page_config(page_title=config.APP_TITLE, page_icon="🌍", layout="wide")

user = auth.require_login()

ui.apply_iucn_styles()

brand, heading = st.columns([1, 5], vertical_alignment="center")
with brand:
    st.image("assets/iucn_logo.png", width=118)
with heading:
    st.title(config.APP_TITLE)

# Keep the database connectivity check, but show a failure only when the
# connection is unavailable; successful connection details aren't dashboard content.
ok, msg = db.test_connection()
if not ok:
    st.error(f"Database connection failed: {msg}")
    st.stop()

# ---- programme-wide headline metrics --------------------------------------
# These five tables record tree interventions. Area is deduplicated within
# each table because multiple species rows can describe the same site.
TREE_TABLE_KEYS = ("silvo", "bso", "roadsides", "tree_plantation", "af_demo")
tree_frames = {}
for key in TREE_TABLE_KEYS:
    cfg = schemas.TABLES[key]
    try:
        tree_frames[key] = db.run_query(f"SELECT * FROM `{cfg['table']}`")
    except Exception as exc:
        st.warning(f"Could not load {cfg['title']} summary: {exc}")
        tree_frames[key] = pd.DataFrame()

try:
    beneficiaries_df = db.run_query("SELECT gender FROM `beneficiaries`")
except Exception as exc:
    st.warning(f"Could not load beneficiary summary: {exc}")
    beneficiaries_df = pd.DataFrame(columns=["gender"])

def _sum_numeric(frames, column):
    return sum(
        pd.to_numeric(frame[column], errors="coerce").sum()
        for frame in frames if column in frame.columns
    )

tree_total = _sum_numeric(
    [tree_frames[k] for k in TREE_TABLE_KEYS if k != "roadsides"], "num_trees_planted"
)
tree_total += _sum_numeric([tree_frames["roadsides"]], "num_trees")

area_total = 0.0
area_by_intervention = []
for key, frame in tree_frames.items():
    if frame.empty:
        continue
    data = frame.copy()
    if key == "roadsides":
        data["length_km"] = pd.to_numeric(data.get("length_km"), errors="coerce")
        road_keys = [c for c in ("district", "road_name", "length_km") if c in data.columns]
        if road_keys:
            data = data.drop_duplicates(subset=road_keys, keep="first")
        data["_area"] = data["length_km"]
    else:
        data["area_ha"] = pd.to_numeric(data.get("area_ha"), errors="coerce")
        identity = "owner_name" if "owner_name" in data.columns else ("site_name" if "site_name" in data.columns else None)
        area_keys = [c for c in (identity, "area_ha", "district", "sector", "cell") if c and c in data.columns]
        if area_keys:
            data = data.drop_duplicates(subset=area_keys, keep="first")
        data["_area"] = data["area_ha"]
    area_total += data["_area"].sum()
    if "intervention" in data.columns:
        grouped = data.groupby("intervention", dropna=True)["_area"].sum()
        area_by_intervention.extend((name, value) for name, value in grouped.items())

gender_counts = beneficiaries_df.get("gender", pd.Series(dtype=object)).fillna("Unspecified").value_counts()
beneficiary_total = len(beneficiaries_df)
female_count = int(gender_counts.get("Female", 0))
male_count = int(gender_counts.get("Male", 0))

st.subheader("Programme overview")
overview = st.columns(4)
overview[0].metric("Total beneficiaries", f"{beneficiary_total:,}")
overview[1].metric("Total trees planted", f"{tree_total:,.0f}")
overview[2].metric("Area (Ha)", f"{area_total:,.2f}")
with overview[3]:
    st.markdown(
        f'<div class="iucn-summary-card"><div class="iucn-summary-title">Beneficiaries by gender</div>'
        f'<div class="iucn-gender-grid"><div class="iucn-gender-item">Female<br><strong>{female_count:,}</strong></div>'
        f'<div class="iucn-gender-item">Male<br><strong>{male_count:,}</strong></div></div></div>',
        unsafe_allow_html=True,
    )

if area_by_intervention:
    area_intervention_df = (pd.DataFrame(area_by_intervention, columns=["Intervention", "Area (Ha)"])
                            .groupby("Intervention", as_index=False)["Area (Ha)"].sum()
                            .sort_values("Area (Ha)", ascending=False))
    import plotly.express as px
    fig = px.bar(area_intervention_df, x="Intervention", y="Area (Ha)", title="Area (Ha) by Intervention",
                 text_auto=".2s", color_discrete_sequence=["#087fae"])
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title="", margin=dict(t=50, b=10), uniformtext_minsize=9,
                      uniformtext_mode="hide")
    ui.style_iucn_chart(fig)
    st.plotly_chart(fig, use_container_width=True)
if not beneficiaries_df.empty:
    gender_chart = gender_counts.rename_axis("Gender").reset_index(name="Beneficiaries")
    fig = px.bar(gender_chart, x="Gender", y="Beneficiaries", title="Beneficiaries by Gender",
                 text="Beneficiaries", color="Gender",
                 color_discrete_map={"Female": "#12b9d6", "Male": "#203b70", "Unspecified": "#8ba7c4"})
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title="", margin=dict(t=50, b=10), showlegend=False)
    ui.style_iucn_chart(fig)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---- record counts ---------------------------------------------------------
st.subheader("Records by table")
rows = []
for key in schemas.TABLE_ORDER:
    cfg = schemas.TABLES[key]
    try:
        n = int(db.run_query(f"SELECT COUNT(*) AS n FROM `{cfg['table']}`").iloc[0]["n"])
    except Exception:
        n = None
    rows.append({"Table": f"{cfg['icon']} {cfg['title']}", "Records": n})
counts = pd.DataFrame(rows)

c1, c2 = st.columns([1, 1.6])
with c1:
    st.dataframe(counts, use_container_width=True, hide_index=True)
with c2:
    plot = counts.dropna()
    if not plot.empty and plot["Records"].sum() > 0:
        import plotly.express as px
        fig = px.bar(plot, x="Table", y="Records", title="Total records per table",
                     text="Records", color_discrete_sequence=["#203b70"])
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(xaxis_title="", margin=dict(t=50, b=10))
        ui.style_iucn_chart(fig)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No records yet — start with a table page in the sidebar.")

# ---- admin panel -----------------------------------------------------------
if auth.is_admin():
    st.divider()
    st.subheader("👤 User management")

    tab_add, tab_update, tab_delete, tab_list = st.tabs(
        ["➕ Add user", "✏️ Update user", "🗑️ Delete user", "📋 All users"]
    )

    # ---------------------------------------------------------- Add
    with tab_add:
        with st.form("add_user", clear_on_submit=True):
            a, b = st.columns(2)
            nu = a.text_input("Username")
            nf = b.text_input("Full name")
            npw = a.text_input("Password", type="password")
            nrole = b.selectbox("Role", ["user", "admin"])
            if st.form_submit_button("Create user", type="primary"):
                if not nu or len(npw) < 6:
                    st.error("Username required; password must be at least 6 characters.")
                elif auth.get_user(nu):
                    st.error("That username already exists.")
                else:
                    auth.create_user(nu, npw, nf, nrole)
                    st.success(f"User '{nu}' created.")
                    st.rerun()

    # ---------------------------------------------------------- Update
    with tab_update:
        users_df = auth.list_users()
        if users_df.empty:
            st.info("No users yet.")
        else:
            target = st.selectbox("User to update", users_df["username"].tolist(), key="upd_target")
            row = users_df[users_df["username"] == target].iloc[0]

            st.markdown("**Profile**")
            with st.form("update_profile"):
                a, b = st.columns(2)
                new_username = a.text_input("Username", value=row["username"])
                new_full_name = b.text_input("Full name", value=row["full_name"])
                new_role = a.selectbox("Role", ["user", "admin"],
                                       index=["user", "admin"].index(row["role"]))
                if st.form_submit_button("Save changes", type="primary"):
                    if row["role"] == "admin" and new_role == "user" and auth.admin_count() <= 1:
                        st.error("Can't demote the last remaining admin.")
                    elif target == user["username"] and new_role == "user":
                        st.error("You cannot demote your own account.")
                    else:
                        try:
                            auth.update_user(target, full_name=new_full_name,
                                            role=new_role, new_username=new_username)
                            st.success(f"'{target}' updated.")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

            st.markdown("**Reset password**")
            with st.form("update_password"):
                newpw = st.text_input("New password", type="password")
                if st.form_submit_button("Reset password"):
                    if len(newpw) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        auth.set_password(target, newpw)
                        st.success(f"Password reset for '{target}'.")

            st.markdown("**Account status**")
            act = st.radio("Status", ["Active", "Disabled"], horizontal=True,
                          index=0 if row["is_active"] else 1, key="upd_status")
            if st.button("Apply status"):
                if target == user["username"] and act == "Disabled":
                    st.error("You cannot disable your own account.")
                else:
                    auth.set_active(target, act == "Active")
                    st.success(f"'{target}' set to {act}.")
                    st.rerun()

    # ---------------------------------------------------------- Delete
    with tab_delete:
        users_df = auth.list_users()
        if users_df.empty:
            st.info("No users yet.")
        else:
            del_target = st.selectbox("User to delete", users_df["username"].tolist(), key="del_target")
            del_row = users_df[users_df["username"] == del_target].iloc[0]
            st.warning(f"This permanently deletes **{del_target}** ({del_row['full_name']}, "
                       f"{del_row['role']}). Records they created (`created_by`) are kept — "
                       f"only the login is removed. This cannot be undone.")
            confirm = st.checkbox(f"I understand, delete '{del_target}' permanently", key="del_confirm")
            if st.button("🗑️ Delete user", type="primary", disabled=not confirm):
                if del_target == user["username"]:
                    st.error("You cannot delete your own account.")
                elif del_row["role"] == "admin" and auth.admin_count() <= 1:
                    st.error("Can't delete the last remaining admin.")
                else:
                    auth.delete_user(del_target)
                    st.success(f"'{del_target}' deleted.")
                    st.rerun()

    # ---------------------------------------------------------- List
    with tab_list:
        st.dataframe(auth.list_users(), use_container_width=True, hide_index=True)
