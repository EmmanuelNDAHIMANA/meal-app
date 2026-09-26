"""Shared IUCN branded styling for Streamlit pages and dashboard charts."""
import streamlit as st


IUCN_CYAN = "#12b9d6"
IUCN_BLUE = "#087fae"
IUCN_NAVY = "#203b70"
IUCN_PALETTE = [IUCN_BLUE, IUCN_CYAN, IUCN_NAVY, "#65c9d8", "#7890b5"]


def apply_iucn_styles():
    st.markdown("""
    <style>
    :root { --iucn-cyan:#12b9d6; --iucn-blue:#087fae; --iucn-navy:#203b70; }
    [data-testid="stMetric"], .iucn-summary-card {
        background: linear-gradient(135deg,#fff 0%,#f0fbfd 100%);
        border:1px solid #59c7dc; border-left:5px solid var(--iucn-blue);
        border-radius:12px; padding:12px 15px;
        box-shadow:0 3px 12px rgba(32,59,112,.08);
    }
    [data-testid="stMetricLabel"] p { color:var(--iucn-navy); font-weight:650; font-size:.92rem; }
    [data-testid="stMetricValue"] { color:var(--iucn-navy); }
    .iucn-summary-title { color:var(--iucn-navy); font-size:.92rem; font-weight:650; margin-bottom:8px; }
    .iucn-gender-grid { display:flex; gap:18px; align-items:center; }
    .iucn-gender-item { color:#203b70; font-size:1rem; white-space:nowrap; }
    .iucn-gender-item strong { font-size:1.18rem; }
    [data-testid="stPlotlyChart"] {
        border:1px solid #b7e8f0; border-radius:12px; padding:8px;
        box-shadow:0 3px 12px rgba(32,59,112,.06);
    }
    </style>
    """, unsafe_allow_html=True)


def style_iucn_chart(fig):
    fig.update_layout(
        template="plotly_white",
        font=dict(color=IUCN_NAVY),
        colorway=IUCN_PALETTE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
