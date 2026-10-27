"""Density budgets for the progressive analytics editor (synthetic data only)."""
import json
import os
from pathlib import Path

import pytest

from test_analytics_layout_browser import review_browser, review_server

pytestmark = pytest.mark.skipif(os.getenv("ANALYTICS_BROWSER_TESTS") != "1", reason="Opt-in browser verification")

MEASURE = """() => {
  const root = document.querySelector('#settings');
  const shown = node => {
    const el = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
    if (el.closest('[hidden],.sr-only,[popover]:not(:popover-open)')) return false;
    for (let at = el; at && at !== root; at = at.parentElement) {
      if (at.parentElement?.tagName === 'DETAILS' && !at.parentElement.open && at.tagName !== 'SUMMARY') return false;
      const css = getComputedStyle(at);
      if (css.display === 'none' || css.visibility === 'hidden') return false;
    }
    return true;
  };
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let text = '', node;
  while (node = walker.nextNode()) {
    if (!shown(node) || node.parentElement.closest('option,select,script,style')) continue;
    const range = document.createRange(); range.selectNodeContents(node);
    if ([...range.getClientRects()].some(box => box.width > 1 && box.height > 1)) text += node.textContent.replace(/\\s+/g, '');
  }
  for (const select of root.querySelectorAll('select')) if (shown(select)) text += select.selectedOptions[0]?.textContent.replace(/\\s+/g,'') || '';
  const fields = [...root.querySelectorAll('[data-field],[data-source-card],[data-chart-card],[data-single-y],[data-add-y]')].filter(shown);
  const explicit = [...root.querySelectorAll("[data-setting-control]")].filter(shown).map(el => el.dataset.settingControl);
  const groups = explicit.length ? [...new Set(explicit)] : [...new Set(fields.map(el => el.hasAttribute('data-source-card') ? 'source' : el.hasAttribute('data-chart-card') ? 'chart' : el.hasAttribute('data-single-y') || el.hasAttribute('data-add-y') ? 'y' : el.dataset.field))];
  const descriptions = [...root.querySelectorAll('.settings-help,.settings-section-desc,.choice-use,.choice-row,.choice-example,.choice-period')].filter(shown);
  return {characters:[...text].length, fields:groups, descriptions:descriptions.length, text,
    labels:[...root.querySelectorAll('.setting-label > label,.setting-label > span')].filter(shown).map(el => el.textContent.trim()),
    summaries:[...root.querySelectorAll('details[data-section]:not([open]) > summary > span')].map(el => el.textContent.trim())};
}"""


@pytest.mark.skipif(not os.getenv("ANALYTICS_DENSITY_BASELINE"), reason="Explicit pre-change measurement only")
def test_capture_pre_change_density(review_server, review_browser):
    measurements = {}
    for width, height in [(1440,800),(390,844)]:
        page = review_browser.new_page(viewport={"width":width,"height":height})
        page.goto(review_server + "/analytics?demo=1#views")
        page.wait_for_selector(".chart-svg")
        page.locator("#add-panel").click()
        page.locator('[data-panel-type="1"]').click()
        if width < 1024:
            page.locator("#sheet-handle").click()
        measurements[f"{width}x{height}"] = page.evaluate(MEASURE)
        measurements[f"{width}x{height}"]["axes_bottom"] = page.locator('#settings [data-section="axes"]').bounding_box()["y"] + page.locator('#settings [data-section="axes"]').bounding_box()["height"]
        measurements[f"{width}x{height}"]["body_bottom"] = page.locator('#settings-body').bounding_box()["y"] + page.locator('#settings-body').bounding_box()["height"]
        page.screenshot(path=f"/tmp/analytics-density-{width}.png")
        page.close()
    Path(os.environ["ANALYTICS_DENSITY_BASELINE"]).write_text(json.dumps(measurements, ensure_ascii=False, indent=2)+"\n")


@pytest.mark.parametrize("panel_type", range(7))
@pytest.mark.parametrize("width,height", [(1440,800),(390,844)])
def test_new_panel_density_budget(review_server, review_browser, panel_type, width, height):
    page = review_browser.new_page(viewport={"width":width,"height":height}, reduced_motion="reduce")
    page.goto(review_server + "/analytics?demo=1#views")
    page.wait_for_selector(".chart-svg")
    page.locator("#add-panel").click()
    assert page.locator("#panel-types [data-purpose]").count() == 0
    assert page.locator("#panel-types small").count() == 0
    page.locator(f'[data-panel-type="{panel_type}"]').click()
    if width < 1024:
        page.locator("#sheet-handle").click()
    measured = page.evaluate(MEASURE)
    assert measured["descriptions"] == 0, measured
    assert len(measured["fields"]) <= 6, measured
    assert all(len(label) <= 8 for label in measured["labels"]), measured
    assert all(len(summary) <= 20 for summary in measured["summaries"]), measured
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    for section in ["format","data","axes"]:
        assert page.locator(f'#settings [data-section="{section}"]').evaluate("el => el.open")
    for section in ["filters","style","advanced","details"]:
        target = page.locator(f'#settings [data-section="{section}"]')
        if target.count(): assert not target.evaluate("el => el.open")
    if panel_type == 1:
        before = json.loads((Path(__file__).parents[1] / "docs/analytics-settings-density-baseline.json").read_text())
        assert measured["characters"] <= before[f"{width}x{height}"]["characters"] / 2, measured
        axes = page.locator('#settings [data-section="axes"]').bounding_box()
        body = page.locator("#settings-body").bounding_box()
        assert axes["y"] + axes["height"] <= body["y"] + body["height"], (axes,body)
        if width < 1024:
            page.locator(".panel.is-selected .chart-svg").wait_for()
            plot = page.locator(".panel.is-selected .chart-svg").bounding_box()
            preview = page.locator(".panel.is-selected").bounding_box()
            assert plot["height"] >= 44
            assert plot["y"] >= preview["y"] and plot["y"] + plot["height"] <= preview["y"] + preview["height"]
    page.close()


def test_help_and_empty_sections_are_progressive(review_server, review_browser):
    from playwright.sync_api import expect

    page = review_browser.new_page(viewport={"width":1440,"height":800})
    page.goto(review_server + "/analytics?demo=1#views")
    page.wait_for_selector(".chart-svg")
    page.locator("#add-panel").click()
    page.locator('[data-panel-type="1"]').click()
    help_button = page.get_by_role("button",name="種類の説明",exact=True)
    help_button.focus()
    page.keyboard.press("Enter")
    expect(page.locator(".setting-popover:popover-open")).to_contain_text("1回の計測")
    page.keyboard.press("Escape")
    expect(page.locator(".setting-popover:popover-open")).to_have_count(0)
    expect(page.locator("#settings")).to_be_visible()
    for name in ["filters","advanced"]:
        target = page.locator(f'#settings [data-section="{name}"]')
        target.locator("summary").first.click()
        content = target.locator(".settings-section-content")
        assert content.locator("p").count() == 0
        assert content.get_by_role("button").count() == 1
    page.locator("#add-formula").click()
    page.locator('[data-example="rate"]').click()
    expect(page.locator('[data-field="formulas.0.expression"]')).to_have_value("likes / impressions * 100")
    page.locator("[data-remove-formula]").click()
    page.locator("#add-filter-group").click()
    page.locator("[data-remove-rule]").click()
    for name in ["filters","advanced"]:
        content = page.locator(f'#settings [data-section="{name}"] .settings-section-content')
        assert content.get_by_role("button").count() == 1
    page.close()


def test_dates_are_only_disclosed_for_custom_period_and_survive_undo(review_server, review_browser):
    from playwright.sync_api import expect

    page = review_browser.new_page(viewport={"width":1440,"height":800})
    page.goto(review_server + "/analytics?demo=1#views")
    page.wait_for_selector(".chart-svg")
    page.locator("#add-panel").click()
    page.locator('[data-panel-type="1"]').click()
    assert page.locator('[data-field="from_date"]').count() == 0
    page.locator("[data-custom-period]").click()
    page.locator('[data-field="from_date"]').fill("2026-10-01")
    page.locator('[data-field="to_date"]').fill("2026-10-15")
    page.locator('[data-preset-days="30"]').click()
    assert page.locator('[data-field="from_date"]').count() == 0
    page.locator("#undo-settings").click()
    expect(page.locator('[data-field="from_date"]')).to_have_value("2026-10-01")
    expect(page.locator('[data-field="to_date"]')).to_have_value("2026-10-15")
    expect(page.locator("[data-custom-period]")).to_have_attribute("aria-pressed","true")
    page.close()
