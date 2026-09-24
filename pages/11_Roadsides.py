import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

import auth
import forms
import schemas

TABLE_KEY = "roadsides"
CFG = schemas.TABLES[TABLE_KEY]

st.set_page_config(page_title=CFG["title"], page_icon=CFG["icon"], layout="wide")
auth.require_login()

st.title(f"{CFG['icon']} {CFG['title']}")

tab_one, tab_bulk, tab_dash = st.tabs(
    ["📝 Submit one record", "📥 Bulk upload", "📊 Dashboard"]
)

with tab_one:
    forms.render_form(TABLE_KEY)

with tab_bulk:
    forms.render_upload(TABLE_KEY)

with tab_dash:
    forms.render_dashboard(TABLE_KEY)
