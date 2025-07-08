import pandas as pd
import streamlit as st
import pydeck
from pydeck import map_styles

installations = pd.read_csv("data/ex_data.csv")

ICON_URL = "https://upload.wikimedia.org/wikipedia/commons/c/c4/Projet_bi%C3%A8re_logo_v2.png"

icon_data = {"url":ICON_URL,
             "width":242,
             "height":242,
             "anchorY": 242,}

installations["icon_data"] = None
for i in installations.index:
    installations.at[i, "icon_data"] = icon_data

installations

point_layer = pydeck.Layer(
    type="IconLayer",
    data=installations,
    id="pv_installations",
    get_position=["Longitude", "Latitude"],
    pickable=True,
    get_icon="icon_data",
    get_size=15,
    size_scale=2,)

view_state = pydeck.ViewState(
    latitude=65, longitude=-160, controller=True, zoom=2.4, pitch=10
)

chart = pydeck.Deck(
    point_layer,
    initial_view_state=view_state,
    tooltip={"text": "{Location}\nYear of Installation: {Year of Installation}"},
    map_style="light",

)

event = st.pydeck_chart(chart, on_select="rerun", selection_mode="multi-object")

event.selection