import pandas as pd
import streamlit as st
import pydeck
from pydeck import map_styles
import base64

st.title("Alaska PV and BESS Technical Information Map")
installations = pd.read_csv("data/update_example_short.csv")
#installations
view_state = pydeck.ViewState(
    latitude=65, longitude=-160, controller=True, zoom=2.4, pitch=10
)

icon_blue = ".\\data\\markers\\marker_blue.png"
icon_green = ".\\data\\markers\\marker_green.png"
icon_red = ".\\data\\markers\\marker_red.png"

with open(icon_blue, "rb") as f:
    marker_data_blue = base64.b64encode(f.read()).decode('utf-8')
with open(icon_green, "rb") as f:
    marker_data_green = base64.b64encode(f.read()).decode('utf-8')
with open(icon_red, "rb") as f:
    marker_data_red = base64.b64encode(f.read()).decode('utf-8')

#marker_data_blue
icon_data_blue = {"url":f"data:image/png;base64,{marker_data_blue}",
             "width":242,
             "height":242,
             "anchorY": 242,}

icon_data_red = {"url":f"data:image/png;base64,{marker_data_red}",
             "width":242,
             "height":242,
             "anchorY": 242,}

icon_data_green = {"url":f"data:image/png;base64,{marker_data_green}",
             "width":242,
             "height":242,
             "anchorY": 242,}

installations_blue = installations.loc[installations["Planned"] == "y"]
installations_blue["icon_data"] = None
for i in installations_blue.index:
    installations_blue.at[i, "icon_data"] = icon_data_blue

installations_green = installations.loc[(installations["Planned"] == "n")&(installations["d_off"] == "y")]
installations_green["icon_data"] = None
for i in installations_green.index:
    installations_green.at[i, "icon_data"] = icon_data_green

installations_red = installations.loc[(installations["Planned"] == "n")&(installations["d_off"] == "n")]
installations_red["icon_data"] = None
for i in installations_red.index:
    installations_red.at[i, "icon_data"] = icon_data_red
    

layers = []

## Planned
point_layer_blue = pydeck.Layer(
    type="IconLayer",
    data=installations_blue,
    id="pv_installations",
    get_position=["Longitude", "Latitude"],
    pickable=True,
    get_icon="icon_data",
    get_size=15,
    size_scale=2,)

layers.append(point_layer_blue)

point_layer_green = pydeck.Layer(
    type="IconLayer",
    data=installations_green,
    id="pv_installations_green",
    get_position=["Longitude", "Latitude"],
    pickable=True,
    get_icon="icon_data",
    get_size=15,
    size_scale=2,)

layers.append(point_layer_green)

point_layer_red = pydeck.Layer(
    type="IconLayer",
    data=installations_red,
    id="pv_installations_red",
    get_position=["Longitude", "Latitude"],
    pickable=True,
    get_icon="icon_data",
    get_size=15,
    size_scale=2,)

layers.append(point_layer_red)

## Operational
label_layer = pydeck.Layer(
    type="TextLayer",
    data=installations,
    get_position=["Longitude", "Latitude"],
    get_text="Community",
    get_size=12,
    visible = view_state.zoom < 3


)
layers.append(label_layer)




chart = pydeck.Deck(
    layers=layers,
    initial_view_state=view_state,
    tooltip={"html": "<img width='100' src='https://www.gvea.com/wp-content/uploads/GVEA-Solar-Farm-10-2018-web.gif'/><br> <b>{Community}</b> ({Location}) <br>"
    "<ul>"
        "<li><b>Year of Installation:</b> {Year of Installation}</li>"
        "<li><b>PV Capacity (kWdc):</b> {Installed Size - KW DC}</li>"
        "<li><b>BESS SIZE (kW/KWh):</b> {BESS Size - KW/KWH}</li></ul>"},
    #map_style="mapbox://styles/mapbox/standard-satellite",
    map_style="road",
    #map_provider="mapbox",
    api_keys={"mapbox":"pk.eyJ1IjoidWFmLWFjZXAtc29sYXIiLCJhIjoiY21mNGJyMzQxMDN0eDJyb3MwNDdzNTJyaCJ9.fBZHzsknwbKUbDR_C9_QvQ"},
    width=1000,
    height=200,
)

event = st.pydeck_chart(chart, on_select="rerun", selection_mode="multi-object", width=800, height=400, use_container_width=False)

#view_state.zoom
#chart.show()
#event.selection