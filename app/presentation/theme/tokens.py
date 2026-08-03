"""
Design tokens ported 1:1 from the approved UI mockup (navy sidebar / blue accent).

Single source of truth for color, spacing and type values used across the
presentation layer. Widgets and QSS should reference these constants rather
than hardcoding hex values, so the whole app can be re-themed from here.
"""
from __future__ import annotations

# ---------------------------------------------------------------- Sidebar
NAVY = "#10131c"
NAVY_RAISED = "#171b28"
NAVY_LINE = "#262b3b"
NAVY_TEXT = "#eef0f5"
NAVY_TEXT_SOFT = "#8b93a6"
NAVY_LABEL = "#5b6478"

# Navigation at rest. Separate from NAVY_TEXT_SOFT, which also sets the
# hover border on every input in the app: the rail needed lifting without
# dragging those with it.
NAV_IDLE = "#c3cad9"
NAV_GROUP = "#7e88a0"
NAV_HOVER = "#20263a"

# ---------------------------------------------------------------- Canvas
CANVAS = "#f5f6f8"
SURFACE = "#ffffff"
LINE = "#e5e7eb"
LINE_SOFT = "#eef0f3"

# ---------------------------------------------------------------- Text
INK = "#111827"
INK_SOFT = "#4b5563"
MUTED = "#6b7280"

# ---------------------------------------------------------------- Accent
PRIMARY = "#2554eb"
PRIMARY_HOVER = "#1e45cc"
PRIMARY_TINT = "#eaf0fe"

# ---------------------------------------------------------------- Semantic
SUCCESS = "#16a34a"
SUCCESS_TINT = "#e6f7ec"
INFO = "#2563eb"
INFO_TINT = "#e5edfe"
WARNING = "#ea580c"
WARNING_TINT = "#fdedd9"
DANGER = "#dc2626"
DANGER_TINT = "#fce8e8"

# ---------------------------------------------------------------- Shape
RADIUS = 10
RADIUS_SM = 6

# ---------------------------------------------------------------- Type
FONT_FAMILY = "Segoe UI"

FONT_SIZE_TITLE = 15
FONT_SIZE_BODY = 10
FONT_SIZE_LABEL = 8
FONT_SIZE_VALUE = 15

WEIGHT_REGULAR = 400
WEIGHT_MEDIUM = 500
WEIGHT_SEMIBOLD = 600

# ---------------------------------------------------------------- Layout
SIDEBAR_WIDTH = 232
HEADER_HEIGHT = 52
STATUSBAR_HEIGHT = 26
