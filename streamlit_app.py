"""Streamlit application for visualizing Alaska community energy projects."""
from __future__ import annotations

import html
import re
from typing import Dict, Iterable, List, Optional

import pandas as pd
import pydeck as pdk
import streamlit as st

DATA_PATH = "data/installation_data_csv.csv"

PV_FIELDS = [
    ("PV DC Capacity (kWdc)", "PV DC Capacity (kWdc)"),
    ("PV AC Capacity (kWac)", "PV AC Capacity (kWac)"),
    ("Number of PV Modules", "Number of PV Modules"),
    ("PV Module Manufacturer", "PV Module Manufacturer"),
    ("PV Module Model", "PV Module Model"),
    ("PV Inverter Manufacturer", "PV Inverter Manufacturer"),
    ("PV Inverter Model", "PV Inverter Model"),
    ("PV Installation Manager", "PV Installation Manager"),
    ("PV Install Date", "PV Install Date"),
    ("PV Owner", "PV Owner"),
    ("PV Ownership Structure", "PV Ownership Structure"),
]

BESS_FIELDS = [
    ("BESS Capacity (kWh)", "BESS Capacity (kWh)"),
    ("BESS Throughput (kW)", "BESS Throughput (kW)"),
    ("BESS Manufacturer", "BESS Manufacturer"),
    ("BESS Model", "BESS Model"),
    ("BESS Inverter Manufacturer", "BESS Inverter Manufacturer"),
    ("BESS Inverter Model", "BESS Inverter Model"),
    ("BESS Installation Manager", "BESS Installation Manager"),
    ("BESS Install Date", "BESS Install Date"),
    ("BESS Owner", "BESS Owner"),
    ("BESS Ownership Structure", "BESS Ownership Structure"),
]

COLOR_SCALE = {
    "diesels_off_operating": [34, 139, 34, 220],  # green
    "diesels_off_planned": [255, 165, 0, 220],  # orange
    "non_diesels_off_operating": [65, 105, 225, 220],  # royal blue
    "non_diesels_off_planned": [120, 120, 120, 220],  # grey
}

COLOR_LABELS = {
    "diesels_off_operating": "Operating system with diesels-off capability",
    "diesels_off_planned": "Planned system with diesels-off capability",
    "non_diesels_off_operating": "Operating system without diesels-off capability",
    "non_diesels_off_planned": "Planned or proposed system without diesels-off capability",
}


_SYSTEM_ID_PATTERN = re.compile(r"\s*\(([A-Z0-9-]+)\)\s*$")




def format_value(value: object) -> Optional[str]:
    """Return a formatted string for display in tooltips."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        # Some iterables (e.g., lists) raise a TypeError in pd.isna; ignore in that case.
        pass
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value)


def infer_system_type(system_id: Optional[str]) -> str:
    if not system_id or not isinstance(system_id, str):
        return "Unknown"
    suffix = system_id.strip().split("-")[-1].upper()
    if suffix == "P":
        return "Solar PV"
    if suffix == "B":
        return "Battery Energy Storage"
    return "Unknown"



def clean_system_name(name: Optional[str]) -> Optional[str]:
    """Remove trailing system IDs from the provided system name."""
    if not name or not isinstance(name, str):
        return None
    cleaned = name.strip()
    match = _SYSTEM_ID_PATTERN.search(cleaned)
    if match:
        token = match.group(1)
        if any(char.isdigit() for char in token) and "-" in token:
            cleaned = _SYSTEM_ID_PATTERN.sub("", cleaned).rstrip()
    return cleaned or None

def build_list_items(pairs: Iterable[tuple[str, object]]) -> str:
    items: List[str] = []
    for label, raw_value in pairs:
        value = format_value(raw_value)
        if value:
            items.append(
                f"<li><span style='font-weight:500;color:#1f2a44;'>{html.escape(label)}:</span> "
                f"{html.escape(value)}</li>"
            )
    if not items:
        return "<li>No additional parameters available</li>"
    return "".join(items)


def build_system_section(row: pd.Series, show_divider: bool) -> str:
    system_type = row["System Type"]

    system_name = clean_system_name(row.get("System Name"))
    if system_name:
        heading = system_name
    elif format_value(system_type):
        heading = f"{system_type} System"
    else:
        heading = "System"

    base_fields = [
        ("System Type", system_type),
        ("Status", row.get("System Status")),
        ("Enables Diesels-Off", row.get("Enables Diesels-Off (yes/no)")),
        ("Supports Diesels-Off", row.get("Supports Diesels-Off (yes/no)")),
        ("Location", row.get("Location")),
        ("Funding Announcement", row.get("Funding Anncouncement Number")),
        ("Award Number", row.get("Award Number")),
    ]

    if system_type == "Battery Energy Storage":
        parameter_pairs = [(label, row.get(column)) for label, column in BESS_FIELDS]
    elif system_type == "Solar PV":
        parameter_pairs = [(label, row.get(column)) for label, column in PV_FIELDS]
    else:
        parameter_pairs = []

    details_html = build_list_items(base_fields + parameter_pairs)
    divider_style = "border-bottom:1px dashed #b5b5b5;" if show_divider else ""
    return (
        "<div style=\"margin-bottom:6px;padding-bottom:6px;" + divider_style + "\">"
        + f"<div style='font-weight:600;font-size:13px;margin-bottom:4px;color:#0b3954;'>{html.escape(heading)}</div>"

        + f"<ul style='margin:0;padding-left:18px;font-size:12px;line-height:1.45;'>{details_html}</ul>"


        + "</div>"
    )



def build_project_section(project_df: pd.DataFrame, fallback_label: str) -> str:
    project_name = format_value(project_df["Project Name"].iloc[0]) or fallback_label
    systems = project_df.sort_values("System Name", na_position="last")
    card_parts = [
        "<div style=\"flex:1 1 240px;min-width:220px;max-width:280px;",
        "background-color:rgba(255,255,255,0.95);border:1px solid #d5d7dc;",
        "border-radius:10px;padding:10px 12px;box-shadow:0 6px 18px rgba(15,23,42,0.14);\">",
        f"<div style='font-size:15px;font-weight:650;color:#0b3954;margin-bottom:8px;'>{html.escape(project_name)}</div>",
    ]

    for idx, (_, row) in enumerate(systems.iterrows()):
        card_parts.append(build_system_section(row, idx < len(systems) - 1))

    card_parts.append("</div>")
    return "".join(card_parts)


def build_tooltip_html(community: str, community_df: pd.DataFrame) -> str:
    project_sections: List[str] = []
    for index, (_, project_df) in enumerate(
        community_df.groupby("Project ID Number", dropna=False),
        start=1,
    ):
        project_sections.append(
            build_project_section(project_df, fallback_label=f"Project {index}")
        )

    projects_html = "".join(project_sections) or "<div>No project details available</div>"
    community_heading = format_value(community) or "Community"
    return (
        "<div style=\"min-width:320px;max-width:640px;font-family:Roboto,Arial,sans-serif;\">"
        + f"<div style='font-size:17px;font-weight:700;margin-bottom:10px;color:#05274d;'>{html.escape(community_heading)}</div>"
        + "<div style='display:flex;flex-wrap:wrap;gap:10px;'>"
        + projects_html
        + "</div></div>"
    )

def determine_color_category(group: pd.DataFrame) -> str:
    enables = group["Enables Diesels-Off (yes/no)"].astype(str).str.strip().str.lower()
    statuses = group["System Status"].astype(str).str.strip().str.lower()

    condition_df = pd.DataFrame({"enables": enables, "status": statuses})

    if not condition_df.empty:
        mask_operating = condition_df["status"] == "operating"
        mask_enables = condition_df["enables"] == "yes"
        if (mask_operating & mask_enables).any():
            return "diesels_off_operating"
        if mask_enables.any():
            return "diesels_off_planned"
        if mask_operating.any():
            return "non_diesels_off_operating"
    return "non_diesels_off_planned"


def create_community_records(df: pd.DataFrame) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    for community, group in df.groupby("Community Name", dropna=True):
        coords = group[["Longitude", "Latitude"]].dropna()
        if coords.empty:
            continue
        lon = coords["Longitude"].astype(float).mean()
        lat = coords["Latitude"].astype(float).mean()

        has_pv = (group["System Type"] == "Solar PV").any()
        has_bess = (group["System Type"] == "Battery Energy Storage").any()
        icon_list = []
        if has_pv:
            icon_list.append("☀️")
        if has_bess:
            icon_list.append("🔋")

        icon_line = " ".join(icon_list)
        label_parts = [community]
        if icon_line:
            label_parts.append(icon_line)
        label = "\n".join(label_parts)


        tooltip_html = build_tooltip_html(community, group)
        category = determine_color_category(group)
        color = COLOR_SCALE.get(category, COLOR_SCALE["non_diesels_off_planned"])

        records.append(
            {
                "community": community,
                "longitude": lon,
                "latitude": lat,
                "color": color,
                "tooltip_html": tooltip_html,
                "label": label,
                "category": category,
            }
        )
    return records


@st.cache_data(show_spinner=False)
def load_data(path: str = DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, na_values=["NA", ""], keep_default_na=True)
    df["System Type"] = df["System ID Number"].apply(infer_system_type)
    return df



def build_deck(records: List[Dict[str, object]]) -> pdk.Deck:
    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        data=records,
        id="community-scatter",

def main() -> None:
    st.set_page_config(page_title="Alaska Clean Energy Projects", page_icon="☀️", layout="wide")

    st.title("Alaska Community Clean Energy Installations")
    st.markdown(
        """
        Explore solar photovoltaic (PV) and battery energy storage system (BESS) projects across Alaska's communities. Each
        map pin represents a community and reveals its projects and systems when hovered. Pin colors reflect whether any
        associated system supports diesels-off operations and its operational status. Labels show whether a community has
        PV (☀️) and/or BESS (🔋) systems.
        """
    )

    data = load_data()
    community_records = create_community_records(data)

    if not community_records:
        st.warning("No community records with valid coordinates were found in the dataset.")
        return

    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        data=community_records,

        get_position="[longitude, latitude]",
        get_fill_color="color",
        get_line_color="[255, 255, 255, 255]",
        line_width_min_pixels=1,
        get_radius=8000,
        radius_min_pixels=6,
        pickable=True,
        auto_highlight=True,
    )

    text_layer = pdk.Layer(
        "TextLayer",

        data=records,
        id="community-labels",
        get_position="[longitude, latitude]",
        get_text="label",
        get_color="[35, 35, 35, 255]",
        get_size=15,
        get_alignment_baseline="top",
        get_text_anchor="middle",
        get_pixel_offset=[0, 26],
        line_height=1.2,
    )

    view_state = pdk.ViewState(
        latitude=64.2008,
        longitude=-152.4044,
        zoom=3.6,
        min_zoom=2.5,
        max_zoom=10,
        pitch=30,
    )

    tooltip_style = {
        "backgroundColor": "rgba(245, 248, 252, 0.95)",
        "color": "#1f2933",
        "fontFamily": "Roboto, Arial, sans-serif",
        "fontSize": "12px",
        "border": "1px solid #d5d7dc",
        "borderRadius": "10px",
        "padding": "10px",
        "boxShadow": "0 10px 26px rgba(15, 23, 42, 0.18)",
        "maxWidth": "640px",
    }

    return pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=view_state,
        layers=[scatter_layer, text_layer],
        tooltip={"html": "{tooltip_html}", "style": tooltip_style},
    )


def render_legend() -> None:

        data=community_records,
        get_position="[longitude, latitude]",
        get_text="label",
        get_color="[35, 35, 35, 255]",
        get_size=16,
        get_alignment_baseline="top",
        get_text_anchor="middle",
        get_pixel_offset=[0, 18],
    )

    view_state = pdk.ViewState(latitude=64.2008, longitude=-152.4044, zoom=3.6, min_zoom=2.5, max_zoom=10, pitch=30)

    tooltip_style = {
        "html": "{tooltip_html}",
        "style": {
            "backgroundColor": "rgba(245, 248, 252, 0.95)",
            "color": "#1f2933",
            "fontFamily": "Roboto, Arial, sans-serif",
            "fontSize": "12px",
            "border": "1px solid #d5d7dc",
            "borderRadius": "8px",
            "padding": "8px",
        },
    }

    deck = pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=view_state,
        layers=[scatter_layer, text_layer],
        tooltip=tooltip_style,
    )

    st.pydeck_chart(deck, use_container_width=True)


    st.subheader("Map Legend")
    legend_columns = st.columns(2)
    for (category, description), column in zip(COLOR_LABELS.items(), legend_columns * 2):
        rgba = COLOR_SCALE[category]
        rgb_css = f"rgb({rgba[0]}, {rgba[1]}, {rgba[2]})"
        column.markdown(
            f"<div style='display:flex;align-items:center;margin-bottom:8px;'>"
            f"<span style='display:inline-block;width:16px;height:16px;background:{rgb_css};"
            f"border:1px solid #4a4a4a;border-radius:50%;margin-right:8px;'></span>"
            f"<span style='font-size:13px;'>{description}</span></div>",
            unsafe_allow_html=True,
        )



if __name__ == "__main__":
    main()
