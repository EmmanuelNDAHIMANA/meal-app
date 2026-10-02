import streamlit as st

st.set_page_config(page_title="Project M&E Data Platform", page_icon="🌍", layout="wide")

programme_overview = st.Page("pages/0_Programme_Overview.py", title="Programme Overview", icon="📊")
tree_overview = st.Page("pages/1_Tree_Plantations.py", title="Tree Plantations", icon="🌳")
tree_plantation = st.Page("pages/1_Tree_Plantation.py", title="Tree Plantation", icon="🌱")
bso = st.Page("pages/3_BSO.py", title="BSO", icon="🌿")
silvo = st.Page("pages/4_Silvo.py", title="Silvo", icon="🌳")
af_demo = st.Page("pages/5_AF_Demo.py", title="AF Demo", icon="🌾")
roadsides = st.Page("pages/11_Roadsides.py", title="Roadsides", icon="🛣️")

beneficiaries = st.Page("pages/2_Beneficiaries.py", title="Beneficiaries", icon="👥")
activities = st.Page("pages/6_Activities_Tracker.py", title="Activities Tracker", icon="📋")
indicators = st.Page("pages/7_Indicators.py", title="Indicators", icon="📊")
trainings = st.Page("pages/8_Trainings.py", title="Trainings", icon="🎓")
jobs = st.Page("pages/9_Jobs_Created.py", title="Jobs Created", icon="💼")
cooperatives = st.Page("pages/12_Coperatives.py", title="Cooperatives", icon="🤝")
other_reports = st.Page("pages/99_Other_Reports.py", title="Other Reports", icon="📁")

tree_pages = [
    (tree_overview, "Tree Plantations", "🌳"),
    (tree_plantation, "Tree Plantation", "🌱"),
    (bso, "BSO", "🌿"),
    (silvo, "Silvo", "🌳"),
    (af_demo, "AF Demo", "🌾"),
    (roadsides, "Roadsides", "🛣️"),
]
programme_pages = [
    (beneficiaries, "Beneficiaries", "👥"),
    (activities, "Activities Tracker", "📋"),
    (indicators, "Indicators", "📊"),
    (trainings, "Trainings", "🎓"),
    (jobs, "Jobs Created", "💼"),
    (cooperatives, "Cooperatives", "🤝"),
]

navigation = st.navigation(
    [programme_overview] + [page for page, _, _ in tree_pages + programme_pages] + [other_reports],
    position="hidden",
)

st.sidebar.page_link(programme_overview, label="Programme Overview", icon="📊")
with st.sidebar.expander("Tree Plantations", expanded=True):
    for page, label, icon in tree_pages:
        st.page_link(page, label=label, icon=icon)
with st.sidebar.expander("Programme Data", expanded=True):
    for page, label, icon in programme_pages:
        st.page_link(page, label=label, icon=icon)
with st.sidebar.expander("Reports", expanded=True):
    st.page_link(other_reports, label="Other Reports", icon="📁")

navigation.run()
