"""BuildMC AI Desktop clone theme for the TARNO PySide6 GUI."""

from __future__ import annotations

COLORS = {
    "dark_900": "#0f0f13",
    "dark_800": "#18181b",
    "dark_700": "#27272a",
    "dark_600": "#3f3f46",
    "dark_500": "#52525b",
    "brand_400": "#a78bfa",
    "brand_500": "#8b5cf6",
    "brand_600": "#7c3aed",
    "brand_700": "#6d28d9",
    "brand_950": "#2e1065",
    "text_primary": "#f3f4f6",
    "text_secondary": "#9ca3af",
    "text_muted": "#6b7280",
    "success": "#2DD4BF",
    "warning": "#F59E0B",
    "error": "#FF4444",
    "border": "#27272a",
    "border_hover": "#3f3f46",
}


def get_stylesheet() -> str:
    c = COLORS
    return f"""
    * {{
        font-family: "Inter", "Segoe UI", "Segoe UI Variable", sans-serif;
        font-size: 14px;
        color: {c["text_primary"]};
        outline: none;
    }}

    QMainWindow {{
        background-color: {c["dark_900"]};
    }}

    QWidget {{
        background-color: transparent;
    }}

    /* ── Sidebar ── */
    #sidebar {{
        background-color: {c["dark_800"]};
        border-right: 1px solid {c["border"]};
    }}

    #sidebarBrand {{
        background: transparent;
        border-bottom: 1px solid {c["border"]};
    }}

    #brandTitle {{
        font-size: 20px;
        font-weight: 700;
        color: {c["brand_400"]};
    }}

    #brandSub {{
        font-size: 11px;
        color: {c["text_muted"]};
    }}

    #sidebarNavItem {{
        background: transparent;
        border: none;
        border-radius: 8px;
        padding: 10px 12px;
        margin: 2px 8px;
        text-align: left;
        font-size: 13px;
        color: {c["text_secondary"]};
    }}

    #sidebarNavItem:hover {{
        background-color: {c["dark_700"]};
        color: {c["text_primary"]};
    }}

    #sidebarNavItem:checked {{
        background-color: {c["brand_600"]};
        color: #ffffff;
        font-weight: 600;
    }}

    #sidebarNavItem:checked #sidebarNavLabel {{
        color: #ffffff;
    }}

    #sidebarNavItem:checked #sidebarNavIcon {{
        color: #ffffff;
    }}

    #sidebarFooter {{
        background: transparent;
        border-top: 1px solid {c["border"]};
        padding: 12px;
    }}

    #sidebarFooterText {{
        font-size: 10px;
        color: {c["text_muted"]};
    }}

    /* ── Page header ── */
    #pageHeader {{
        background-color: transparent;
        padding: 24px 24px 16px 24px;
    }}

    #pageTitle {{
        font-size: 24px;
        font-weight: 700;
        color: {c["text_primary"]};
    }}

    #pageSubtitle {{
        font-size: 13px;
        color: {c["text_secondary"]};
        margin-top: 4px;
    }}

    /* ── Cards ── */
    #card {{
        background-color: {c["dark_800"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 16px;
    }}

    #cardSection {{
        background-color: {c["dark_700"]};
        border-radius: 8px;
        padding: 12px;
    }}

    #cardTitle {{
        font-size: 16px;
        font-weight: 600;
        color: {c["text_primary"]};
    }}

    #cardSubtitle {{
        font-size: 12px;
        color: {c["text_secondary"]};
        margin-top: 2px;
    }}

    #cardValue {{
        font-size: 24px;
        font-weight: 700;
        color: {c["text_primary"]};
    }}

    #cardLabel {{
        font-size: 11px;
        color: {c["text_muted"]};
    }}

    #cardAccent {{
        font-size: 10px;
        color: {c["brand_400"]};
    }}

    /* ── Buttons ── */
    #btnPrimary {{
        background-color: {c["brand_600"]};
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        color: #ffffff;
        font-weight: 500;
        font-size: 13px;
    }}

    #btnPrimary:hover {{
        background-color: {c["brand_500"]};
    }}

    #btnPrimary:pressed {{
        background-color: {c["brand_700"]};
    }}

    #btnSecondary {{
        background-color: {c["dark_700"]};
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        color: {c["text_primary"]};
        font-weight: 500;
        font-size: 13px;
    }}

    #btnSecondary:hover {{
        background-color: {c["dark_600"]};
    }}

    #btnDanger {{
        background-color: #dc2626;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        color: #ffffff;
        font-weight: 500;
        font-size: 13px;
    }}

    #btnDanger:hover {{
        background-color: #ef4444;
    }}

    /* ── Inputs ── */
    #input {{
        background-color: {c["dark_800"]};
        border: 1px solid {c["dark_600"]};
        border-radius: 8px;
        padding: 10px 14px;
        color: {c["text_primary"]};
        font-size: 14px;
        selection-background-color: {c["brand_500"]};
    }}

    #input:focus {{
        border-color: {c["brand_500"]};
    }}

    /* ── Chat page ── */
    #chatScroll {{
        background-color: {c["dark_900"]};
        border: none;
    }}

    #chatContainer {{
        background-color: {c["dark_900"]};
    }}

    #chatCard {{
        background-color: {c["dark_800"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
    }}

    #bubbleUser {{
        background-color: {c["brand_600"]};
        border-radius: 8px;
        padding: 10px 14px;
        color: #ffffff;
        font-size: 13px;
    }}

    #bubbleAssistant {{
        background-color: {c["dark_700"]};
        border-radius: 8px;
        padding: 10px 14px;
        color: {c["text_primary"]};
        font-size: 13px;
    }}

    #bubbleName {{
        font-size: 11px;
        color: {c["text_muted"]};
        margin-bottom: 4px;
    }}

    #inputArea {{
        background-color: {c["dark_800"]};
        border-top: 1px solid {c["border"]};
        padding: 12px 16px;
    }}

    #chatInput {{
        background-color: {c["dark_800"]};
        border: 1px solid {c["dark_600"]};
        border-radius: 8px;
        padding: 12px 16px;
        color: {c["text_primary"]};
        font-size: 14px;
        selection-background-color: {c["brand_500"]};
    }}

    #chatInput:focus {{
        border-color: {c["brand_500"]};
    }}

    #sendButton {{
        background-color: {c["brand_600"]};
        border: none;
        border-radius: 8px;
        padding: 12px 20px;
        color: #ffffff;
        font-weight: 500;
        font-size: 13px;
        min-width: 44px;
    }}

    #sendButton:hover {{
        background-color: {c["brand_500"]};
    }}

    #sendButton:pressed {{
        background-color: {c["brand_700"]};
    }}

    #micButton {{
        background: transparent;
        border: 2px solid {c["dark_600"]};
        border-radius: 22px;
        padding: 8px;
        font-size: 18px;
        min-width: 44px;
        max-width: 44px;
        min-height: 44px;
        max-height: 44px;
    }}

    #micButton:hover {{
        border-color: {c["brand_500"]};
        background-color: {c["dark_700"]};
    }}

    #micButton[active="true"] {{
        border-color: {c["error"]};
        background-color: rgba(255, 68, 68, 0.12);
    }}

    /* ── Status bar ── */
    #statusBar {{
        background-color: {c["dark_800"]};
        border-top: 1px solid {c["border"]};
        padding: 4px 16px;
        font-size: 12px;
        color: {c["text_muted"]};
    }}

    #statusDot {{
        font-size: 10px;
    }}

    /* ── Toggle switch style ── */
    QCheckBox {{
        spacing: 8px;
        font-size: 13px;
    }}

    QCheckBox::indicator {{
        width: 40px;
        height: 22px;
        border-radius: 11px;
        background-color: {c["dark_600"]};
        border: 1px solid {c["border"]};
    }}

    QCheckBox::indicator:checked {{
        background-color: {c["brand_600"]};
        border-color: {c["brand_600"]};
    }}

    /* ── Scrollbar ── */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background: {c["dark_600"]};
        border-radius: 4px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {c["brand_500"]};
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        height: 0;
        background: none;
        border: none;
    }}

    QScrollBar:horizontal {{
        height: 0;
    }}

    /* ── Thinking indicator ── */
    #thinkingLabel {{
        color: {c["text_muted"]};
        font-style: italic;
        padding: 8px 16px;
        margin: 4px 60px 4px 16px;
    }}

    /* ── Combo box ── */
    QComboBox {{
        background-color: {c["dark_800"]};
        border: 1px solid {c["dark_600"]};
        border-radius: 8px;
        padding: 8px 12px;
        color: {c["text_primary"]};
        min-width: 160px;
    }}

    QComboBox:hover {{
        border-color: {c["brand_500"]};
    }}

    QComboBox::drop-down {{
        border: none;
        padding-right: 8px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {c["dark_800"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        selection-background-color: {c["dark_700"]};
        color: {c["text_primary"]};
        padding: 4px;
    }}

    QToolTip {{
        background-color: {c["dark_800"]};
        border: 1px solid {c["border"]};
        color: {c["text_primary"]};
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 12px;
    }}
    """
