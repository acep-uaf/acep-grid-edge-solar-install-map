"""Streamlit application for visualizing Alaska community energy projects."""
from __future__ import annotations

import html
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
    system_type = row.get("System Type")
    system_name = format_value(row.get("System Name"))
    system_type_label = format_value(system_type)
    heading = system_name or system_type_label or "System Details"

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
        + f"<ul style='margin:0;padding-left:18px;font-size:12px;line-height:1.4;'>{details_html}</ul>"
        + "</div>"
    )


def build_project_section(project_df: pd.DataFrame) -> str:
    project_name = format_value(project_df["Project Name"].iloc[0])
    header = project_name or "Project"

    body_parts = [
        "<div style=\"flex:1 1 240px;min-width:220px;max-width:280px;border:1px solid #d5d7dc;\""
        "border-radius:8px;padding:8px;background-color:rgba(255,255,255,0.92);box-sizing:border-box;\">",
        f"<div style='font-size:14px;font-weight:600;color:#12355b;margin-bottom:6px;'>{html.escape(header)}</div>",
    ]

    sort_columns: List[str] = []
    if "System Name" in project_df.columns:
        sort_columns.append("System Name")
    if "System ID Number" in project_df.columns:
        sort_columns.append("System ID Number")

    systems = project_df.sort_values(sort_columns) if sort_columns else project_df
    total_systems = len(systems)
    system_sections: List[str] = []
    for idx, (_, row) in enumerate(systems.iterrows()):
        system_sections.append(build_system_section(row, idx < total_systems - 1))

    if system_sections:
        body_parts.extend(system_sections)
    else:
        body_parts.append(
            "<div style='font-size:12px;color:#5f6c7b;'>No system details available for this project.</div>"
        )

    body_parts.append("</div>")
    return "".join(body_parts)


def build_tooltip_html(community: str, community_df: pd.DataFrame) -> str:
    project_groups = list(community_df.groupby("Project ID Number", dropna=False))

    def sort_key(item) -> tuple[int, str]:
        project_id, project_df = item
        name = format_value(project_df["Project Name"].iloc[0])
        if name:
            return (0, name.casefold())
        fallback = format_value(project_id) or ""
        return (1, fallback.casefold())

    project_groups.sort(key=sort_key)

    project_sections = [build_project_section(project_df) for _, project_df in project_groups]

    if project_sections:
        projects_html = (
            "<div style='display:flex;flex-wrap:wrap;gap:8px;align-items:stretch;'>"
            + "".join(project_sections)
            + "</div>"
        )
    else:
        projects_html = "<div style='font-size:12px;color:#5f6c7b;'>No project details available.</div>"

    parts = [
        "<div style=\"min-width:300px;max-width:680px;font-family:Roboto,Arial,sans-serif;\">",
        f"<div style='font-size:16px;font-weight:700;margin-bottom:8px;color:#0b3954;'>{html.escape(community)}</div>",
        projects_html,
    ]
    parts.append("</div>")
    return "".join(parts)


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
        icon_suffix = f" {' '.join(icon_list)}" if icon_list else ""
        label = f"{community}{icon_suffix}"
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

    st.caption(
        "Data source: ACEP Grid Edge Solar Installation dataset. Hover over communities to see projects, "
        "systems, and associated parameters."
    )


if __name__ == "__main__":
    main()
