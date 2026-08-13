"""Dark TARNO theme for the PySide6 control UI."""

from __future__ import annotations

COLORS = {
    "dark_900": "#0a0a0c",
    "dark_800": "#111114",
    "dark_700": "#1c1c21",
    "dark_600": "#2a2a31",
    "dark_500": "#3e3e47",
    "accent_400": "#5eead4",
    "accent_500": "#2dd4bf",
    "accent_600": "#14b8a6",
    "text_primary": "#f1f5f9",
    "text_secondary": "#94a3b8",
    "text_muted": "#64748b",
    "success": "#2dd4bf",
    "warning": "#f59e0b",
    "error": "#f87171",
    "border": "#27272a",
    "border_hover": "#3f3f46",
}


def get_stylesheet() -> str:
    c = COLORS
    return f"""
    * {{
        font-family: "Segoe UI", "Segoe UI Variable", "Inter", sans-serif;
        font-size: 14px;
        color: {c["text_primary"]};
        outline: none;
    }}

    QMainWindow, QDialog {{
        background-color: {c["dark_900"]};
    }}

    QWidget {{
        background-color: transparent;
    }}

    QLabel {{
        color: {c["text_primary"]};
    }}

    QMainWindow::title {{
        color: {c["text_primary"]};
    }}

    #statusBar {{
        background-color: {c["dark_800"]};
        border-top: 1px solid {c["border"]};
        padding: 6px 16px;
        font-size: 12px;
        color: {c["text_secondary"]};
    }}

    #statusText {{
        color: {c["text_secondary"]};
        font-size: 12px;
    }}

    #statusDot {{
        color: {c["success"]};
        font-size: 14px;
    }}

    #btnPrimary {{
        background-color: {c["accent_600"]};
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        color: #000000;
        font-weight: 600;
        font-size: 13px;
    }}

    #btnPrimary:hover {{
        background-color: {c["accent_500"]};
    }}

    #btnPrimary:pressed {{
        background-color: {c["accent_400"]};
    }}

    #btnSecondary {{
        background-color: {c["dark_700"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 8px 16px;
        color: {c["text_primary"]};
        font-weight: 500;
        font-size: 13px;
    }}

    #btnSecondary:hover {{
        background-color: {c["dark_600"]};
        border-color: {c["border_hover"]};
    }}

    #btnSecondary:pressed {{
        background-color: {c["dark_500"]};
    }}

    #btnDanger {{
        background-color: #991b1b;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        color: #ffffff;
        font-weight: 500;
        font-size: 13px;
    }}

    #btnDanger:hover {{
        background-color: #b91c1c;
    }}

    #input {{
        background-color: {c["dark_800"]};
        border: 1px solid {c["dark_600"]};
        border-radius: 8px;
        padding: 10px 14px;
        color: {c["text_primary"]};
        font-size: 14px;
        selection-background-color: {c["accent_600"]};
    }}

    #input:focus {{
        border-color: {c["accent_500"]};
    }}

    QLineEdit {{
        background-color: {c["dark_800"]};
        border: 1px solid {c["dark_600"]};
        border-radius: 8px;
        padding: 10px 14px;
        color: {c["text_primary"]};
        font-size: 14px;
        selection-background-color: {c["accent_600"]};
    }}

    QLineEdit:focus {{
        border-color: {c["accent_500"]};
    }}

    QTextEdit, QPlainTextEdit {{
        background-color: {c["dark_800"]};
        border: 1px solid {c["dark_600"]};
        border-radius: 8px;
        padding: 10px;
        color: {c["text_primary"]};
        font-size: 13px;
    }}

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
        background: {c["accent_500"]};
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
    """
