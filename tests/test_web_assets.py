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
    ]
    assert stylesheet_links("detail.html") == [
        "/css/tokens.css",
        "/css/base.css",
        "/css/components.css",
        "/css/detail.css",
        "/css/responsive.css",
    ]


def test_css_structure_has_one_font_import_and_one_mobile_query():
    styles = {
        path.name: path.read_text(encoding="utf-8")
        for path in CSS_DIR.glob("*.css")
    }

    assert set(styles) == {
        "tokens.css",
        "base.css",
        "components.css",
        "calendar.css",
        "detail.css",
        "responsive.css",
    }
    assert sum(style.count("@import") for style in styles.values()) == 1
    assert sum(style.count("@media") for style in styles.values()) == 1
    assert "@media (max-width: 700px)" in styles["responsive.css"]
    assert all("!important" not in style for style in styles.values())


def test_css_files_have_balanced_rule_blocks():
    for path in CSS_DIR.glob("*.css"):
        style = path.read_text(encoding="utf-8")
        assert style.count("{") == style.count("}"), path.name
