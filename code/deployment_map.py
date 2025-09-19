import pandas as pd
import streamlit as st
import pydeck
from pydeck import map_styles
import base64


st.title("Alaska PV and BESS Technical Information Map")
installations = pd.read_excel("data/installation_data_excel.xlsx")

installations

view_state = pydeck.ViewState(
    latitude=65, longitude=-160, controller=True, zoom=2.4, pitch=10
)