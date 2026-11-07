"""Design tokens (dark navy / charcoal / muted blue). Edit values here to revise the palette."""

# ---- Core palette
BACKGROUND = "#111827"      # main background
SIDEBAR = "#0B1220"         # sidebar background
CARD = "#1B2535"            # cards and panels
ELEVATED = "#243044"        # elevated surfaces (buttons, dialog panels)
TEXT = "#C8D0DC"            # primary text (silver-gray, never pure white)
MUTED = "#929EAF"           # secondary text
FAINT = "#758195"           # muted text (placeholders, disabled, fine print)
ACCENT = "#527DAF"          # primary blue
ACCENT_TINT = "#293D56"     # hover and selected states
BORDER = "#303C4E"          # borders and dividers

SUCCESS = "#75B798"
WARNING = "#D8B574"
ERROR = "#D98282"

# ---- Button states (derived; every button must stay visible on the dark surfaces)
ACCENT_EDGE = "#6A93C2"          # thin lighter edge on primary buttons
ACCENT_DISABLED_BORDER = "#3A5575"
BUTTON_BG = "#2A374D"            # secondary button surface (lighter than cards)
BUTTON_BORDER = "#4A5A73"
BUTTON_HOVER_BG = "#33445F"
BUTTON_PRESSED_BG = "#202B3D"
BUTTON_DISABLED_BG = "#1F2A3C"
BUTTON_DISABLED_BORDER = "#3A4659"
FOCUS_RING = "#B7CCE6"           # keyboard focus outline colour
DANGER_BORDER = "#7A474B"
DANGER_HOVER_BG = "#4A2D31"
DANGER_PRESSED_BG = "#2F1D20"
LINK_BORDER = "#35507A"
LINK_HOVER_BG = "#314A6B"
LINK_PRESSED_BG = "#223650"

# ---- Supporting shades (derived from the palette above)
ACCENT_TEXT = "#86A9D2"     # lighter blue for links and in-progress text (readable on dark)
ACCENT_HOVER = "#4B76A8"        # darker on hover keeps label contrast >= 4.5:1
ACCENT_PRESSED = "#3E6592"
ACCENT_DISABLED = "#2B4059"
TEXT_ON_ACCENT = "#F8FAFC"  # text on primary buttons (off-white)
HOVER_SUBTLE = "#212D3F"    # quiet hover on cards, rows and secondary buttons
ROW_DIVIDER = "#263245"
FIELD_BORDER = "#46556B"
DISABLED_TEXT = FAINT
SCROLL_HANDLE = "#3B4A60"
SCROLL_HOVER = "#51627C"
PANEL = ELEVATED

WARNING_TEXT = WARNING
ERROR_TEXT = ERROR
SUCCESS_TINT = "#20362E"
WARNING_TINT = "#38301F"
ERROR_TINT = "#3A2528"
INFO_TEXT = ACCENT_TEXT
INFO_TINT = ACCENT_TINT
NEUTRAL_TINT = ELEVATED
BANNER = "#2A2519"

SUCCESS_BORDER = "#2F5546"
WARNING_BORDER = "#5A4B2D"
ERROR_BORDER = "#5C3A3E"
INFO_BORDER = "#35507A"

# kind -> (foreground, background) for status badges
BADGE_COLORS = {
    "success": (SUCCESS, SUCCESS_TINT),
    "warning": (WARNING_TEXT, WARNING_TINT),
    "error": (ERROR_TEXT, ERROR_TINT),
    "info": (INFO_TEXT, INFO_TINT),
    "neutral": (MUTED, NEUTRAL_TINT),
}

# kind -> border colour for notice boxes
NOTICE_BORDERS = {
    "success": SUCCESS_BORDER,
    "warning": WARNING_BORDER,
    "error": ERROR_BORDER,
    "info": INFO_BORDER,
}

# kind -> solid colour for dots
KIND_COLORS = {
    "success": SUCCESS,
    "warning": WARNING,
    "error": ERROR,
    "info": ACCENT,
    "neutral": FAINT,
}

# Usage bar colours: blues and grays (state colours stay reserved for status)
BAR_PALETTE = [ACCENT, "#6F95C2", "#8FB0D6", "#4A5D78", FAINT, FIELD_BORDER]
