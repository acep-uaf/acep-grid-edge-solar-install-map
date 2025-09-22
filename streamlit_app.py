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

PLANNED_KEYWORDS = {
    "planned",
    "proposed",
    "pending",
    "construction",
    "development",
    "future",
}

OPERATING_KEYWORDS = {
    "operating",
    "operational",
    "active",
    "online",
    "in operation",
}

INOPERATIVE_KEYWORDS = {
    "inoperative",
    "inoperable",
    "out of order",
    "out-of-order",
    "out of service",
    "out-of-service",
    "offline",
    "retired",
    "decommissioned",
    "not operating",
    "not-operating",
    "inactive",
    "under repair",
    "down",
}

STATUS_META = {
    "operating": {
        "icon": "✅",
        "label_text": "Operating",
        "system_background": "#eef8f0",
        "project_background": "#e6f3e9",
        "border": "#9acb9a",
        "project_border": "#82b77a",
        "label_background": "#dff1e0",
        "label_color": "#2f6d34",
    },
    "planned": {
        "icon": "⚠️",
        "label_text": "Planned",
        "system_background": "#fff8e1",
        "project_background": "#fff3cd",
        "border": "#e7c66a",
        "project_border": "#d5b34c",
        "label_background": "#fef3c7",
        "label_color": "#8a6d1a",
    },
    "inoperative": {
        "icon": "🚫",
        "label_text": "Inoperative",
        "system_background": "#fdecea",
        "project_background": "#f9e0dc",
        "border": "#f1998d",
        "project_border": "#dd8275",
        "label_background": "#f8d7da",
        "label_color": "#a13232",
    },
    "unknown": {
        "icon": "ℹ️",
        "label_text": "Status Unknown",
        "system_background": "#f5f6f8",
        "project_background": "#f0f2f5",
        "border": "#cfd6e0",
        "project_border": "#b9c2d0",
        "label_background": "#e6e9f0",
        "label_color": "#4a5568",
    },
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


def normalize_status(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return text


def classify_status(value: object) -> str:
    text = normalize_status(value)
    if not text or text in {"na", "n/a", "none", "unknown"}:
        return "unknown"
    if any(keyword in text for keyword in OPERATING_KEYWORDS):
        return "operating"
    if any(keyword in text for keyword in INOPERATIVE_KEYWORDS):
        return "inoperative"
    if any(keyword in text for keyword in PLANNED_KEYWORDS):
        return "planned"
    return "unknown"


def aggregate_status(statuses: Iterable[str]) -> str:
    status_list = list(statuses)
    if not status_list:
        return "unknown"
    if any(status == "operating" for status in status_list):
        return "operating"
    if any(status == "inoperative" for status in status_list):
        return "inoperative"
    if any(status == "planned" for status in status_list):
        return "planned"
    return "unknown"


def get_status_meta(status_class: str) -> Dict[str, str]:
    return STATUS_META.get(status_class, STATUS_META["unknown"])


def build_status_badge(status_class: str) -> str:
    meta = get_status_meta(status_class)
    return (
        "<span style='display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:999px;"
        f"background:{meta['label_background']};color:{meta['label_color']};font-size:11px;font-weight:600;'>"
        f"{meta['icon']} {meta['label_text']}</span>"
    )


def parse_install_year(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, pd.Timestamp):
        return int(value.year)
    if isinstance(value, (int, float)):
        if float(value).is_integer() and 1000 <= int(value) <= 3000:
            return int(value)
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        match = re.search(r"(19|20)\d{2}", text)
        if match:
            return int(match.group(0))
    return None


def get_system_install_year(row: pd.Series) -> Optional[int]:
    for column in ("BESS Install Date", "PV Install Date"):
        if column in row:
            year = parse_install_year(row.get(column))
            if year is not None:
                return year
    return None


def format_install_year_text(year: Optional[object], status_class: str) -> str:
    try:
        if year is not None and not pd.isna(year):
            return str(int(float(year)))
    except (TypeError, ValueError):
        pass
    if status_class == "planned":
        return "TBD"
    return "Unknown"


def build_system_section(row: pd.Series, status_class: str, install_year: Optional[int]) -> str:
    system_type = row.get("System Type")
    system_name = format_value(row.get("System Name"))
    system_type_label = format_value(system_type)
    heading = system_name or system_type_label or "System Details"

    meta = get_status_meta(status_class)
    badge_html = build_status_badge(status_class)
    install_year_text = format_install_year_text(install_year, status_class)

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
    return (
        "<div style='padding:10px;border-radius:10px;box-shadow:0 1px 3px rgba(15,23,42,0.08);"
        f"border:1px solid {meta['border']};background:{meta['system_background']};'>"
        + "<div style='display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:4px;'>"
        + f"<div style='font-weight:600;font-size:13px;color:#0b3954;'>{html.escape(heading)}</div>"
        + badge_html
        + "</div>"
        + f"<div style='font-size:11px;color:#43536d;margin-bottom:6px;'>Install year: {html.escape(install_year_text)}</div>"
        + f"<ul style='margin:0;padding-left:18px;font-size:12px;line-height:1.45;'>{details_html}</ul>"
        + "</div>"
    )


def build_project_section(project_df: pd.DataFrame) -> str:
    project_name = format_value(project_df["Project Name"].iloc[0])
    header = project_name or "Project"

    systems_df = project_df.copy()
    systems_df["_status_class"] = systems_df["System Status"].apply(classify_status)
    systems_df["_install_year"] = systems_df.apply(get_system_install_year, axis=1)

    sort_columns: List[str] = ["_install_year"]
    if "System Name" in systems_df.columns:
        sort_columns.append("System Name")
    if "System ID Number" in systems_df.columns:
        sort_columns.append("System ID Number")

    systems_df = systems_df.sort_values(sort_columns, na_position="last")

    project_status = aggregate_status(systems_df["_status_class"].tolist())
    project_meta = get_status_meta(project_status)

    year_series = systems_df["_install_year"].dropna()
    project_year = int(year_series.min()) if not year_series.empty else None
    project_year_text = format_install_year_text(project_year, project_status)

    system_sections: List[str] = []
    for _, row in systems_df.iterrows():
        install_year_value = row["_install_year"]
        if pd.isna(install_year_value):
            normalized_year: Optional[int] = None
        else:
            normalized_year = int(float(install_year_value))
        system_sections.append(
            build_system_section(row, row["_status_class"], normalized_year)
        )

    systems_html = (
        "<div style='display:flex;flex-direction:column;gap:8px;'>" + "".join(system_sections) + "</div>"
        if system_sections
        else "<div style='font-size:12px;color:#5f6c7b;'>No system details available for this project.</div>"
    )

    container_style = (
        f"flex:1 1 260px;min-width:240px;max-width:320px;border-radius:12px;"
        f"border:1px solid {project_meta['project_border']};"
        f"background:{project_meta['project_background']};"
        "box-shadow:0 2px 6px rgba(15,23,42,0.08);padding:12px;box-sizing:border-box;"
    )

    return (
        f"<div style=\"{container_style}\">"
        + "<div style='display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:6px;'>"
        + f"<div style='font-size:15px;font-weight:700;color:#0b3954;'>{html.escape(header)}</div>"
        + build_status_badge(project_status)
        + "</div>"
        + f"<div style='font-size:12px;color:#3f4a5a;margin-bottom:10px;'>First install year: {html.escape(project_year_text)}</div>"
        + systems_html
        + "</div>"
    )


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
            "<div style='display:flex;flex-wrap:wrap;gap:12px;align-items:stretch;'>"
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
