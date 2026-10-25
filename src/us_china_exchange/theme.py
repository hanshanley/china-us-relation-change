"""SVG equivalents of uk_decline's vizstyle house style, without a runtime dependency."""

import math
from xml.etree import ElementTree

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
FLOW_COLORS = {"to_us": PARTNER_COLORS, "from_us": dict(PARTNER_COLORS, CHN=BLUE, HKG="#7B2D26")}
COMPARISON_GEOGRAPHIES = ("CHN", "HKG", "MAC")
FIGURE_CATEGORIES = {
    "students": "Students",
    "visitors": "Visitor trips",
    "goods_trade": "Goods trade",
    "services_trade": "Services trade",
    "weibo": "Weibo research coverage",
    "language_learning": "Language learning",
    "business_presence": "Business presence",
    "immigration": "Immigration",
    "opinions": "Public opinion",
}


def linear_axis(peak):
    extent = peak * 1.08 or 1
    power = 10 ** math.floor(math.log10(extent / 4))
    ratio = extent / (4 * power)
    step = min((1, 2, 2.5, 5, 10), key=lambda v: abs(math.log(v / ratio))) * power
    count = math.ceil(extent / step)
    return count * step, [i * step for i in range(count + 1)]


def axis_label(value, unit=""):
    prefix = "$" if unit == "USD" else ""
    for scale, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(value) >= scale:
            return prefix + f"{value / scale:,.6f}".rstrip("0").rstrip(".") + suffix
    return prefix + f"{value:,.6f}".rstrip("0").rstrip(".")


def figure_category(measure):
    if measure in {"goods", "services"}:
        return measure + "_trade"
    return "visitors" if "visitors" in measure else "students"


def png_dimensions(svg):
    _, _, width, height = map(float, ElementTree.fromstring(svg).attrib["viewBox"].split())
    if width <= 0 or height <= 0:
        raise ValueError("Export viewBox must have positive dimensions")
    return PNG_WIDTH, round(PNG_WIDTH * height / width)
