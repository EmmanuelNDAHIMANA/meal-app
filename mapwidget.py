"""
Interactive GPS coordinate picker for the "Location" / "Location (GPS)" /
"Location(GPS Coordinate)" fields.

Click anywhere on the map to drop a pin, then fine-tune the exact
latitude/longitude with the number inputs underneath (typing there moves
the pin too). Returns a "lat, lon" string in the same format these fields
have always used, so validation, storage, dashboards, and bulk-upload all
keep working unchanged.
"""
from __future__ import annotations
import streamlit as st
import folium
from streamlit_folium import st_folium

RWANDA_CENTER = (-1.9403, 29.8739)   # roughly the centre of Rwanda
DEFAULT_ZOOM = 8
PICKED_ZOOM = 14


def render_gps_picker(label: str, key: str, help_text: str = "") -> str:
    """
    Renders a click-to-pick map plus editable Latitude/Longitude fields.
    Must be called full-width (not inside a narrow column) for the map to
    be usable. Returns "lat, lon" (6-decimal string) or "" if unset.
    """
    state_key = f"{key}_latlon"

    st.markdown(f"**{label}**")
    st.caption(help_text or "Click the map to drop a pin, or type exact coordinates below.")

    current = st.session_state.get(state_key)
    center = current if current else RWANDA_CENTER
    zoom = PICKED_ZOOM if current else DEFAULT_ZOOM

    m = folium.Map(location=center, zoom_start=zoom, control_scale=True)
    if current:
        folium.Marker(
            current, tooltip="Selected location",
            icon=folium.Icon(color="green", icon="map-pin", prefix="fa"),
        ).add_to(m)
    m.add_child(folium.LatLngPopup())

    map_state = st_folium(
        m, height=320, use_container_width=True,
        key=f"{key}_map", returned_objects=["last_clicked"],
    )

    clicked = map_state.get("last_clicked") if map_state else None
    if clicked and (current is None or (clicked["lat"], clicked["lng"]) != current):
        st.session_state[state_key] = (round(clicked["lat"], 6), round(clicked["lng"], 6))
        current = st.session_state[state_key]
        st.rerun()

    c1, c2, c3 = st.columns([1, 1, 0.6])
    with c1:
        lat = st.number_input(
            "Latitude", value=current[0] if current else None, format="%.6f",
            min_value=-90.0, max_value=90.0, step=0.0001, key=f"{key}_lat",
            placeholder="click the map or type here",
        )
    with c2:
        lon = st.number_input(
            "Longitude", value=current[1] if current else None, format="%.6f",
            min_value=-180.0, max_value=180.0, step=0.0001, key=f"{key}_lon",
            placeholder="click the map or type here",
        )
    with c3:
        st.write("")
        st.write("")
        if st.button("Clear pin", key=f"{key}_clear", use_container_width=True):
            st.session_state.pop(state_key, None)
            st.rerun()

    if lat is not None and lon is not None:
        if (lat, lon) != current:
            st.session_state[state_key] = (lat, lon)
        return f"{lat:.6f}, {lon:.6f}"
    return ""
