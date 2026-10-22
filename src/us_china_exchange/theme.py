"""SVG equivalents of uk_decline's vizstyle house style, without a runtime dependency."""

BG = "#F7F5F0"
TEXT = "#1A1A1A"
MUTED = "#6B6B6B"
GRID = "#D6D3CC"
BLUE = "#3D6F8C"
GOLD = "#C2993E"
GREEN = "#4A7C59"
FONT = "DejaVu Serif, Georgia, 'Times New Roman', serif"
CHART_WIDTH = 1000
CHART_HEIGHT = 600
PNG_WIDTH = 3000
PNG_HEIGHT = 1800
FONT_FILES = ("DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf", "DejaVuSerif-Italic.ttf")

CHART_THEMES = {
    "themarginoferror": {"label": "The Margin of Error", "background": BG},
    "substack": {"label": "Substack", "background": "#F5F5F5"},
}
PARTNER_COLORS = {"CHN": "#7B2D26", "HKG": BLUE, "MAC": GOLD, "TWN": GREEN}
COMPARISON_GEOGRAPHIES = ("CHN", "HKG", "MAC")
FIGURE_CATEGORIES = {
    "students": "Students",
    "visitors": "Visitor trips",
    "goods_trade": "Goods trade",
    "services_trade": "Services trade",
    "weibo": "Weibo research coverage",
    "language_learning": "Language learning",
    "business_presence": "Business presence",
}


def figure_category(measure):
    if measure in {"goods", "services"}:
        return measure + "_trade"
    return "visitors" if "visitors" in measure else "students"
