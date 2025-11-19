"""Streamlit application for visualizing Alaska Solar PV and battery energy storage projects."""
from __future__ import annotations

import html
import re
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote_plus

import pandas as pd
import pydeck as pdk
import streamlit as st
import streamlit.components.v1 as components
import pathlib

DATA_PATH = "data/installation_data_csv.csv"

BASE_FIELDS = [
    ("Enables Diesels-Off", "Enables Diesels-Off (yes/no)"),
    ("Supports Diesels-Off", "Supports Diesels-Off (yes/no)"),
    ("Funding Announcement", "Funding Anncouncement Number"),
    ("Award Number", "Award Number"),
]

PV_CAPACITY_FIELDS = [
    ("PV DC Capacity (kWdc)", "PV DC Capacity (kWdc)"),
    ("PV AC Capacity (kWac)", "PV AC Capacity (kWac)"),
]

PV_ADDITIONAL_FIELDS = [
    ("Number of PV Modules", "Number of PV Modules"),
    ("PV Module Manufacturer", "PV Module Manufacturer"),
    ("PV Module Model", "PV Module Model"),
    ("PV Inverter Manufacturer", "PV Inverter Manufacturer"),
    ("PV Inverter Model", "PV Inverter Model"),
    ("PV Installation Manager", "PV Installation Manager"),
    ("PV Owner", "PV Owner"),
    ("PV Ownership Structure", "PV Ownership Structure"),
]

BESS_CAPACITY_FIELDS = [
    ("Capacity (kWh)", "BESS Capacity (kWh)"),
    ("Throughput (kW)", "BESS Throughput (kW)"),
]

BESS_EQUIPMENT_FIELDS = [
    ("Manufacturer", "BESS Manufacturer"),
    ("Model", "BESS Model"),
    ("Inverter Manufacturer", "BESS Inverter Manufacturer"),
    ("Inverter Model", "BESS Inverter Model"),
]

BESS_OWNERSHIP_FIELDS = [
    ("Owner", "BESS Owner"),
    ("Installation Manager", "BESS Installation Manager"),
]

BESS_OTHER_FIELDS = [
    ("Ownership Structure", "BESS Ownership Structure"),
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


def format_value_or_unknown(value: object) -> str:
    formatted = format_value(value)
    return formatted if formatted is not None else "Unknown"


def infer_system_type(system_id: Optional[str]) -> str:
    if not system_id or not isinstance(system_id, str):
        return "Unknown"
    suffix = system_id.strip().split("-")[-1].upper()
    if suffix == "P":
        return "Solar PV"
    if suffix == "B":
        return "Battery Energy Storage"
    return "Unknown"


def build_list_items(
    pairs: Iterable[tuple[str, object]], *, empty_message: str = "<li>No additional parameters available</li>"
) -> str:
    items: List[str] = []
    for label, raw_value in pairs:
        value = format_value(raw_value)
        if value:
            items.append(
                f"<li><span style='font-weight:500;color:#1f2a44;'>{html.escape(label)}:</span> "
                f"{html.escape(value)}</li>"
            )
    if not items:
        return empty_message
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


def build_year_badge(text: str) -> str:
    return (
        "<div style='display:inline-block;padding:2px 6px;border-radius:6px;background:#eef1f6;"
        "color:#2f3b52;font-size:11px;font-weight:600;letter-spacing:0.02em;'>"
        f"{html.escape(text)}</div>"
    )


def build_info_group(title: str, items: List[tuple[str, str]]) -> str:
    cells = []
    for label, value in items:
        cells.append(
            "<div style='padding:6px 8px;border-radius:8px;background:rgba(255,255,255,0.75);"
            "border:1px solid rgba(15,23,42,0.08);'>"
            f"<div style='font-size:10px;font-weight:600;text-transform:uppercase;color:#4a5b75;letter-spacing:0.04em;'>{html.escape(label)}</div>"
            f"<div style='font-size:12px;color:#102a43;margin-top:4px;'>{html.escape(value)}</div>"
            "</div>"
        )
    return (
        "<div style='margin-bottom:8px;padding:8px;border-radius:10px;background:rgba(15,23,42,0.04);'>"
        f"<div style='font-size:11px;font-weight:600;color:#0b3954;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.04em;'>{html.escape(title)}</div>"
        "<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:6px;'>"
        + "".join(cells)
        + "</div>"
        + "</div>"
    )


def build_bess_detail_html(row: pd.Series, base_pairs: List[tuple[str, object]]) -> str:
    capacity_items = [
        (label, format_value_or_unknown(row.get(column)))
        for label, column in BESS_CAPACITY_FIELDS
    ]
    capacity_html = build_info_group("Capacity & Throughput", capacity_items)

    equipment_items = [
        (label, format_value_or_unknown(row.get(column)))
        for label, column in BESS_EQUIPMENT_FIELDS
    ]
    equipment_html = build_info_group("Equipment", equipment_items)

    ownership_items = [
        (label, format_value_or_unknown(row.get(column)))
        for label, column in BESS_OWNERSHIP_FIELDS
    ]
    ownership_html = build_info_group("Ownership", ownership_items)

    other_pairs = base_pairs + [
        (label, row.get(column)) for label, column in BESS_OTHER_FIELDS
    ]
    other_list_items = build_list_items(other_pairs, empty_message="")
    other_html = ""
    if other_list_items:
        other_html = (
            "<ul style='margin:8px 0 0;padding-left:16px;font-size:12px;line-height:1.45;'>"
            f"{other_list_items}</ul>"
        )

    return capacity_html + equipment_html + ownership_html + other_html


def build_pv_detail_html(row: pd.Series, base_pairs: List[tuple[str, object]]) -> str:
    capacity_items = [
        (label, format_value_or_unknown(row.get(column)))
        for label, column in PV_CAPACITY_FIELDS
    ]
    capacity_html = build_info_group("Capacity (DC & AC)", capacity_items)

    parameter_pairs = [(label, row.get(column)) for label, column in PV_ADDITIONAL_FIELDS]
    list_items = build_list_items(base_pairs + parameter_pairs)
    details_html = (
        f"<ul style='margin:8px 0 0;padding-left:16px;font-size:12px;line-height:1.45;'>{list_items}</ul>"
    )

    return capacity_html + details_html


def build_system_section(row: pd.Series, status_class: str, install_year: Optional[int]) -> str:
    system_type = row.get("System Type")
    system_name = format_value(row.get("System Name"))
    system_type_label = format_value(system_type)
    heading = system_name or system_type_label or "System Details"

    emoji_prefix = ""
    if system_type == "Battery Energy Storage":
        emoji_prefix = "🔋 "
    elif system_type == "Solar PV":
        emoji_prefix = "☀️ "
    if emoji_prefix:
        heading = f"{emoji_prefix}{heading}"

    meta = get_status_meta(status_class)
    badge_html = build_status_badge(status_class)
    install_year_text = format_install_year_text(install_year, status_class)
    install_year_badge = build_year_badge(install_year_text)

    base_pairs = [(label, row.get(column)) for label, column in BASE_FIELDS]

    if system_type == "Battery Energy Storage":
        detail_content = build_bess_detail_html(row, base_pairs)
    elif system_type == "Solar PV":
        detail_content = build_pv_detail_html(row, base_pairs)
    else:
        list_items = build_list_items(base_pairs)
        detail_content = (
            f"<ul style='margin:4px 0 0;padding-left:16px;font-size:12px;line-height:1.45;'>{list_items}</ul>"
        )

    return (
        "<div style='padding:8px;border-radius:10px;box-shadow:0 1px 2px rgba(15,23,42,0.08);'"
        f"border:1px solid {meta['border']};background:{meta['system_background']};'>"
        + "<div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;gap:6px;'>"
        + f"<div style='font-weight:600;font-size:13px;color:#0b3954;'>{html.escape(heading)}</div>"
        + badge_html
        + "</div>"
        + f"<div style='margin-bottom:6px;'>{install_year_badge}</div>"
        + detail_content
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
    project_year_badge = build_year_badge(project_year_text)

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
        "<div style='display:flex;flex-direction:column;gap:6px;'>" + "".join(system_sections) + "</div>"
        if system_sections
        else "<div style='font-size:12px;color:#5f6c7b;'>No system details available for this project.</div>"
    )

    container_style = (
        f"flex:1 1 250px;min-width:230px;max-width:300px;border-radius:10px;"
        f"border:1px solid {project_meta['project_border']};"
        f"background:{project_meta['project_background']};"
        "box-shadow:0 1px 3px rgba(15,23,42,0.08);padding:10px;box-sizing:border-box;"
    )

    return (
        f"<div style=\"{container_style}\">"
        + "<div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;gap:6px;'>"
        + f"<div style='font-size:15px;font-weight:700;color:#0b3954;'>{html.escape(header)}</div>"
        + build_status_badge(project_status)
        + "</div>"
        + f"<div style='margin-bottom:6px;'>{project_year_badge}</div>"
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
            "<div style='display:flex;flex-wrap:wrap;gap:10px;align-items:stretch;'>"
            + "".join(project_sections)
            + "</div>"
        )
    else:
        projects_html = "<div style='font-size:12px;color:#5f6c7b;'>No project details available.</div>"

    parts = [
        "<div style=\"min-width:300px;max-width:680px;font-family:Roboto,Arial,sans-serif;\">",
        f"<div style='font-size:16px;font-weight:700;margin-bottom:6px;color:#0b3954;'>{html.escape(community)}</div>",
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
                "detail_url": f"?community={quote_plus(community)}",
            }
        )
    return records



def render_community_detail(community: str, data: pd.DataFrame) -> bool:
    community_df = data[data["Community Name"] == community]
    if community_df.empty:
        st.warning(f"No project details were found for {community}.")
        return False


    st.title(f"{community} - Detailed Information")
    detail_html = build_tooltip_html(community, community_df)
    st.markdown(detail_html, unsafe_allow_html=True)

    return True


def inject_click_handler(html_string: str) -> str:
    injection = """
    (function attachCommunityClickHandler(deckInstance) {
      if (!deckInstance) {
        return;
      }

      const deckObject = deckInstance.deck || deckInstance.__deck || deckInstance;
      if (!deckObject || typeof deckObject.setProps !== 'function') {
        return;
      }

      const container = document.getElementById('deck-container');
      if (!container) {
        return;
      }

      const existingOnClick =
        deckObject.props && typeof deckObject.props.onClick === 'function'
          ? deckObject.props.onClick
          : null;
      const existingGetCursor =
        deckObject.props && typeof deckObject.props.getCursor === 'function'
          ? deckObject.props.getCursor
          : null;

      const state = {
        panelElements: null,
        copyTimeout: null,
      };

      const ensurePanel = () => {
        if (state.panelElements) {
          return state.panelElements;
        }

        if (getComputedStyle(container).position === 'static') {
          container.style.position = 'relative';
        }

        const panel = document.createElement('div');
        panel.className = 'pinned-community-panel';
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-live', 'polite');
        panel.style.position = 'absolute';
        panel.style.top = '16px';
        panel.style.right = '16px';
        panel.style.maxWidth = '360px';
        panel.style.width = 'min(360px, calc(100% - 32px))';
        panel.style.maxHeight = 'calc(100% - 32px)';
        panel.style.display = 'none';
        panel.style.flexDirection = 'column';
        panel.style.background = 'rgba(255, 255, 255, 0.98)';
        panel.style.borderRadius = '12px';
        panel.style.boxShadow = '0 18px 32px rgba(15, 23, 42, 0.28)';
        panel.style.border = '1px solid rgba(15, 23, 42, 0.08)';
        panel.style.backdropFilter = 'blur(4px)';
        panel.style.padding = '16px';
        panel.style.boxSizing = 'border-box';
        panel.style.zIndex = '10';

        const header = document.createElement('div');
        header.style.display = 'flex';
        header.style.alignItems = 'center';
        header.style.justifyContent = 'space-between';
        header.style.gap = '8px';
        header.style.marginBottom = '12px';

        const title = document.createElement('div');
        title.style.fontSize = '16px';
        title.style.fontWeight = '700';
        title.style.color = '#0b3954';
        title.textContent = 'Community details';
        header.appendChild(title);

        const closeButton = document.createElement('button');
        closeButton.type = 'button';
        closeButton.setAttribute('aria-label', 'Close pinned community details');
        closeButton.textContent = '\u00d7';
        closeButton.style.border = 'none';
        closeButton.style.background = 'transparent';
        closeButton.style.fontSize = '20px';
        closeButton.style.lineHeight = '20px';
        closeButton.style.cursor = 'pointer';
        closeButton.style.color = '#1f2a44';
        closeButton.addEventListener('click', () => {
          panel.style.display = 'none';
        });
        header.appendChild(closeButton);

        panel.appendChild(header);

        const actions = document.createElement('div');
        actions.style.display = 'flex';
        actions.style.flexWrap = 'wrap';
        actions.style.gap = '8px';
        actions.style.marginBottom = '8px';

        const openLink = document.createElement('a');
        openLink.textContent = 'Detailed Community Page \u2197';
        openLink.href = '#';
        openLink.target = '_blank';
        openLink.rel = 'noopener noreferrer';
        openLink.style.display = 'none';
        openLink.style.fontSize = '13px';
        openLink.style.fontWeight = '600';
        openLink.style.color = '#0b7285';
        openLink.style.textDecoration = 'none';
        openLink.style.padding = '6px 10px';
        openLink.style.borderRadius = '999px';
        openLink.style.fontFamily = 'Roboto, Arial, sans-serif'
        openLink.style.background = 'rgba(11, 114, 133, 0.12)';
        openLink.addEventListener('mouseenter', () => {
          openLink.style.background = 'rgba(11, 114, 133, 0.18)';
        });
        openLink.addEventListener('mouseleave', () => {
          openLink.style.background = 'rgba(11, 114, 133, 0.12)';
        });
        actions.appendChild(openLink);

        const copyButton = document.createElement('button');
        copyButton.type = 'button';
        copyButton.textContent = 'Copy shareable link';
        copyButton.style.fontSize = '13px';
        copyButton.style.fontWeight = '600';
        copyButton.style.color = '#1f2a44';
        copyButton.style.background = '#e9eef5';
        copyButton.style.border = '1px solid rgba(15, 23, 42, 0.08)';
        copyButton.style.borderRadius = '999px';
        copyButton.style.padding = '6px 12px';
        copyButton.style.cursor = 'pointer';
        copyButton.style.display = 'none';

        panel.appendChild(actions);

        const linkWrapper = document.createElement('div');
        linkWrapper.style.display = 'none';
        linkWrapper.style.marginBottom = '10px';
        linkWrapper.style.width = '100%';

        const linkInput = document.createElement('input');
        linkInput.type = 'text';
        linkInput.readOnly = true;
        linkInput.style.width = '100%';
        linkInput.style.fontSize = '12px';
        linkInput.style.padding = '6px 8px';
        linkInput.style.borderRadius = '6px';
        linkInput.style.border = '1px solid rgba(15, 23, 42, 0.16)';
        linkInput.style.background = '#f8fafc';
        linkInput.style.color = '#1f2a44';
        linkInput.style.boxSizing = 'border-box';
        linkWrapper.appendChild(linkInput);

    

        const status = document.createElement('div');
        status.style.fontSize = '12px';
        status.style.color = '#2f6d34';
        status.style.minHeight = '18px';
        status.style.marginBottom = '6px';
        status.textContent = '';
        panel.appendChild(status);

        const body = document.createElement('div');
        body.style.overflowY = 'auto';
        body.style.paddingRight = '4px';
        body.style.marginRight = '-4px';
        body.style.flex = '1 1 auto';
        body.style.fontFamily = 'Roboto, Arial, sans-serif';
        body.style.color = '#102a43';
        panel.appendChild(body);

        container.appendChild(panel);

        copyButton.addEventListener('click', () => {
          if (!linkInput.value) {
            return;
          }
          const text = linkInput.value;
          const finalize = success => {
            if (state.copyTimeout) {
              clearTimeout(state.copyTimeout);
            }
            status.textContent = success
              ? 'Link copied to clipboard'
              : 'Unable to copy link automatically';
            status.style.color = success ? '#2f6d34' : '#b42318';
            if (success) {
              state.copyTimeout = window.setTimeout(() => {
                status.textContent = '';
              }, 2500);
            }
          };

          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(
              () => finalize(true),
              () => finalize(false)
            );
          } else {
            try {
              linkInput.focus();
              linkInput.select();
              const ok = document.execCommand('copy');
              finalize(ok);
            } catch (error) {
              finalize(false);
            }
          }
        });

        state.panelElements = {
          panel,
          title,
          openLink,
          copyButton,
          linkWrapper,
          linkInput,
          status,
          body,
        };
        return state.panelElements;
      };

      const hidePanel = () => {
        if (!state.panelElements) {
          return;
        }
        state.panelElements.panel.style.display = 'none';
      };

      const showPanel = info => {
        const elements = ensurePanel();
        const {
          panel,
          title,
          openLink,
          copyButton,
          linkWrapper,
          linkInput,
          status,
          body,
        } = elements;

        const communityName =
          info && info.object && info.object.community
            ? String(info.object.community)
            : 'Community details';
        title.textContent = communityName;

        let detailHref = '';
        if (info && info.object && info.object.detail_url) {
          const baseUrl =
            document.referrer && document.referrer.startsWith('http')
              ? document.referrer
              : window.parent && window.parent.location && window.parent.location.href
              ? window.parent.location.href
              : window.location.href;
          try {
            detailHref = new URL(info.object.detail_url, baseUrl).toString();
          } catch (error) {
            console.error('Unable to resolve community detail URL', error);
          }
        }

        if (detailHref) {
          openLink.href = detailHref;
          openLink.style.display = 'inline-flex';
          copyButton.style.display = 'inline-flex';
          linkWrapper.style.display = 'block';
          linkInput.value = detailHref;
        } else {
          openLink.href = '#';
          openLink.style.display = 'none';
          copyButton.style.display = 'none';
          linkWrapper.style.display = 'none';
          linkInput.value = '';
        }

        status.textContent = '';

        const tooltipHTML =
          info && info.object && info.object.tooltip_html
            ? String(info.object.tooltip_html)
            : "<div style='font-size:12px;color:#5f6c7b;'>No additional details available for this community.</div>";
        body.innerHTML = tooltipHTML;
        body.scrollTop = 0;

        panel.style.display = 'flex';
      };

      deckObject.setProps({
        onClick: (info, event) => {
          if (info && info.object) {
            showPanel(info);
          } else {
            hidePanel();
          }
          if (existingOnClick) {
            try {
              existingOnClick(info, event);
            } catch (error) {
              console.error('Error in existing onClick handler', error);
            }
          }
        },
        getCursor: state => {
          if (existingGetCursor) {
            try {
              const result = existingGetCursor(state);
              if (result) {
                return result;
              }
            } catch (error) {
              console.error('Error in existing getCursor handler', error);
            }
          }

          if (state && state.isDragging) {
            return 'grabbing';
          }
          if (state && state.isHovering) {
            return 'pointer';
          }
          return 'grab';
        },
      });
    })(deckInstance);
    """

    closing_tag = "</script>"
    index = html_string.rfind(closing_tag)
    if index == -1:
        return html_string
    return html_string[:index] + injection + html_string[index:]


def render_map(deck: pdk.Deck, *, height: int = 620) -> None:
    html_string = deck.to_html(
        as_string=True,
        notebook_display=False,
        iframe_height=height,
    )
    html_with_click = inject_click_handler(html_string)
    components.html(html_with_click, height=height, scrolling=False)


@st.cache_data(show_spinner=False)
def load_data(path: str = DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path, na_values=["NA", ""], keep_default_na=True)
    df["System Type"] = df["System ID Number"].apply(infer_system_type)
    return df


def main() -> None:
    st.set_page_config(page_title="Alaska Solar and Battery Projects", page_icon="☀️", layout="wide")

    data = load_data()
    community_records = create_community_records(data)

    query_params = st.query_params
    selected_values = query_params.get("community")
    selected_community = ""
    
    if isinstance(selected_values, (list, tuple)):
        value_candidates = list(selected_values)
    elif selected_values is None:
        value_candidates = []
    else:
        value_candidates = [selected_values]

    if value_candidates:
        raw_value = value_candidates[0]
        if isinstance(raw_value, str):
            selected_community = raw_value.strip()
        elif raw_value is not None:
            selected_community = str(raw_value).strip()

    detail_rendered = False
    if selected_community:
        detail_rendered = render_community_detail(selected_community, data)
        if detail_rendered:
            return

    if not community_records:
        st.warning("No community records with valid coordinates were found in the dataset.")
        return
    
    col1, col2, col3 = st.columns(spec=[0.12, 0.7, 0.25])

    with col1:
        st.image(pathlib.Path("images\\0824_Blue_UAF_Block_RGB.svg"))
    with col3:
        st.image(pathlib.Path("images\\acep_logo.svg"))

    st.title("Alaska Battery and Solar PV Installation Map")

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
        get_text="community",
        get_color="[35, 35, 35, 255]",
        get_size=16,
        get_alignment_baseline="top",
        get_text_anchor="middle",
        get_pixel_offset=[0, 18],
    )

    view_state = pdk.ViewState(latitude=64.2008, longitude=-152.4044, zoom=3.4, min_zoom=2.5, max_zoom=10, pitch=10)

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

    render_map(deck, height=640)

    st.markdown(
        "<div style='margin-top:8px;margin-bottom:18px;padding:10px 12px;border-radius:10px;"
        "background:rgba(11,114,133,0.08);color:#0b3954;font-size:13px;'>"
        "<strong>Tip:</strong> Click any community circle to pin a full details panel. "
        "Use the <em>Detailed Community Page</em> button or the shareable link to view "
        "the same information in a separate browser tab.</div>",
        unsafe_allow_html=True,
    )

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
        "This work was jointly funded by the Denali Commission (award #1659) as well as the U.S. Department of Energy Arctic Energy Office."
    )
    st.caption("<p style='font-size: 12px; text-align: center;'>The University of Alaska is an equal opportunity and equal access employer, " \
    "educational institution and provider. The University of Alaska does not discriminate on" \
    " the basis of race, religion, color, national origin, citizenship, age, sex, physical or" \
    " mental disability, status as a protected veteran, marital status, changes in marital status," \
    " pregnancy, childbirth or related medical conditions, parenthood, sexual orientation, gender" \
    " identity, political affiliation or belief, genetic information, or other legally protected status." \
    " The University’s commitment to nondiscrimination applies to all applicants, faculty, staff, students," \
    " student-employees, volunteers, affiliates and contractors in a manner consistent with all applicable laws," \
    " regulations, ordinances, orders, and Board of Regents’ Policies, University Regulations,"
    " and related internal processes and procedures. Contact information and complaint procedures" \
    " are included on UA's statement of nondiscrimination available at http://www.alaska.edu/nondiscrimination.</p>",
    unsafe_allow_html=True)

if __name__ == "__main__":
    main()
