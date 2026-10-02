import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

import auth
import db
import filestore

user = auth.require_login()

st.title("📁 Other Reports")
st.caption(
    "Use this page for reports and documents that don't belong to any of the "
    "9 data tables — general updates, ad-hoc analyses, meeting notes, etc. "
    "Files are renamed the same way as everywhere else in the app: "
    "original name + upload date/time + your username."
)

# ------------------------------------------------------------------ upload
st.subheader("⬆️ Upload a report")
with st.form("upload_report", clear_on_submit=True):
    title = st.text_input("Title / description (optional)", placeholder="e.g. Q3 monitoring summary")
    up = st.file_uploader("File (any format)", type=None,
                          help=f"Max {filestore.MAX_FILE_MB} MB.")
    submitted = st.form_submit_button("Upload", type="primary")

if submitted:
    if up is None:
        st.error("Choose a file first.")
    else:
        try:
            stored_name = filestore.save_file(up, user["username"])
            db.execute(
                "INSERT INTO reports (title, stored_filename, original_filename, uploaded_by) "
                "VALUES (:t, :s, :o, :u)",
                {"t": title.strip() or None, "s": stored_name, "o": up.name, "u": user["username"]},
            )
            st.success(f"Uploaded as '{stored_name}'.")
            st.rerun()
        except Exception as e:
            st.error(f"Upload failed: {e}")

st.divider()

# ------------------------------------------------------------------ helpers
def _download_section(df: pd.DataFrame, key_prefix: str):
    if df.empty:
        st.caption("Nothing uploaded yet.")
        return
    show = df.copy()
    show["uploaded_at"] = pd.to_datetime(show["uploaded_at"]).dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(
        show[["title", "original_filename", "uploaded_by", "uploaded_at", "stored_filename"]],
        use_container_width=True, hide_index=True, height=min(400, 45 + 35 * len(show)),
    )
    pick = st.selectbox(
        "File to download", show["stored_filename"].tolist(),
        format_func=lambda s: show.loc[show["stored_filename"] == s, "original_filename"].iloc[0],
        key=f"pick_{key_prefix}",
    )
    if pick:
        data = filestore.read_file(pick)
        if data is None:
            st.warning(
                "This file isn't on disk right now. If the app was recently redeployed, "
                "uploaded files don't survive that on the current hosting setup."
            )
        else:
            orig = show.loc[show["stored_filename"] == pick, "original_filename"].iloc[0]
            st.download_button(f"⬇️ Download '{orig}'", data=data, file_name=orig, key=f"dl_{key_prefix}")


# ------------------------------------------------------------------ lists
try:
    all_reports = db.run_query("SELECT * FROM reports ORDER BY uploaded_at DESC")
except Exception as e:
    st.error(f"Could not load reports: {e}")
    st.stop()

if auth.is_admin():
    tab_all, tab_mine = st.tabs(["📋 All uploaded reports (admin)", "📄 My uploads"])

    with tab_all:
        st.subheader(f"All uploaded reports ({len(all_reports)})")
        _download_section(all_reports, "admin_all")

        if not all_reports.empty:
            st.markdown("**Delete a report**")
            del_pick = st.selectbox(
                "Report to delete", all_reports["stored_filename"].tolist(),
                format_func=lambda s: all_reports.loc[all_reports["stored_filename"] == s, "original_filename"].iloc[0],
                key="del_pick",
            )
            confirm = st.checkbox("I understand this permanently deletes the file and its record.", key="del_confirm")
            if st.button("🗑️ Delete report", type="primary", disabled=not confirm):
                try:
                    db.execute("DELETE FROM reports WHERE stored_filename = :s", {"s": del_pick})
                    path = filestore.get_file_path(del_pick)
                    if path:
                        path.unlink()
                    st.success("Deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Delete failed: {e}")

    with tab_mine:
        mine = all_reports[all_reports["uploaded_by"] == user["username"]]
        st.subheader(f"Your uploads ({len(mine)})")
        _download_section(mine, "mine_admin")
else:
    st.subheader("📄 Your uploads")
    mine = all_reports[all_reports["uploaded_by"] == user["username"]]
    _download_section(mine, "mine")
    st.caption("Only admins can see everyone else's uploaded reports.")
