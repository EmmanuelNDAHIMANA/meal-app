import pandas as pd
import streamlit as st

import auth
import config
import db
import schemas
import reference_data as ref

st.set_page_config(page_title=config.APP_TITLE, page_icon="🌍", layout="wide")

user = auth.require_login()

st.title("🌍 " + config.APP_TITLE)

ok, msg = db.test_connection()
if ok:
    st.success(f"Connected to `{config.DB_NAME}` at `{config.DB_HOST}`")
else:
    st.error(f"Database connection failed: {msg}")
    st.stop()

st.write(
    "Pick a table from the sidebar. Every table page has three tabs: "
    "**Submit one record**, **Bulk upload** (with a template download), and **Dashboard**."
)

# ---- reference data status -------------------------------------------------
loc, iv = ref.load_locations(), ref.load_interventions()
r1, r2, r3, r4 = st.columns(4)
r1.metric("Districts", loc["District"].nunique())
r2.metric("Sectors", loc["Sector"].nunique())
r3.metric("Cells", loc["Cell"].nunique())
r4.metric("Villages", loc["Village"].nunique())
st.caption(
    f"Reference data loaded: {len(loc):,} location rows · "
    f"{iv['Implementer'].nunique()} implementers · {len(iv)} interventions · "
    f"tree reference: {'yes' if ref.trees_available() else 'not provided (free text)'}"
)

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
        fig = px.bar(plot, x="Table", y="Records", title="Total records per table")
        fig.update_layout(xaxis_title="", margin=dict(t=50, b=0))
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
