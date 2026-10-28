from html.parser import HTMLParser
from pathlib import Path


WEB_DIR = Path(__file__).resolve().parent.parent / "web"
CSS_DIR = WEB_DIR / "css"


class StylesheetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stylesheets = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "link" and attributes.get("rel") == "stylesheet":
            self.stylesheets.append(attributes.get("href"))


def stylesheet_links(filename):
    parser = StylesheetParser()
    parser.feed((WEB_DIR / filename).read_text(encoding="utf-8"))
    return parser.stylesheets


def test_pages_load_split_stylesheets_in_cascade_order():
    assert stylesheet_links("index.html") == [
        "/css/tokens.css",
        "/css/base.css",
        "/css/components.css",
        "/css/calendar.css",
        "/css/responsive.css",
        "/css/calendar-navigation.css",
    ]
    assert stylesheet_links("detail.html") == [
        "/css/tokens.css",
        "/css/base.css",
        "/css/components.css",
        "/css/detail.css",
        "/css/responsive.css",
        "/css/apple-hig.css?v=20261028-dashboard-panels",
    ]


def test_css_structure_uses_system_fonts_and_responsive_layers():
    styles = {
        path.name: path.read_text(encoding="utf-8")
        for path in CSS_DIR.glob("*.css")
    }

    assert set(styles) == {
        "tokens.css",
        "base.css",
        "components.css",
        "calendar.css",
        "calendar-navigation.css",
        "detail.css",
        "responsive.css",
        "analytics.css",
        "analytics-settings.css",
        "apple-hig.css",
    }
    assert sum(style.count("@import") for style in styles.values()) == 0
    assert styles["apple-hig.css"].count("@media") >= 3
    assert "@media (max-width: 700px)" in styles["responsive.css"]
    assert stylesheet_links("analytics.html") == ["/css/analytics.css", "/css/apple-hig.css?v=20261028-dashboard-panels", "/css/analytics-settings.css"]
    assert all("!important" not in style for name, style in styles.items() if name != "analytics-settings.css")
    assert styles["analytics-settings.css"].count("!important") == 1
    assert "[hidden] { display: none !important; }" in styles["analytics-settings.css"]


def test_css_files_have_balanced_rule_blocks():
    for path in CSS_DIR.glob("*.css"):
        style = path.read_text(encoding="utf-8")
        assert style.count("{") == style.count("}"), path.name
        assert style.count("/*") == style.count("*/"), path.name
