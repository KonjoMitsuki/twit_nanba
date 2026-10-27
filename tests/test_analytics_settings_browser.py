"""Editor tests use demo data or profiles in the isolated layout-test DB."""
import copy
import json
import os

import pytest

from processing.analysis_models import Panel
from test_analytics_layout_browser import review_browser, review_server

pytestmark = pytest.mark.skipif(
    os.getenv("ANALYTICS_BROWSER_TESTS") != "1", reason="Opt-in browser verification"
)


def section(page, name):
    if name == "about": name = "details"
    target = page.locator(f'#settings [data-section="{name}"]')
    if target.count(): target.evaluate("el => el.open = true")
    if name in {"axes", "style"}:
        page.locator('#settings [data-section="details"]').evaluate("el => el.open = true")


def saved_demo(page):
    return page.evaluate("JSON.parse(localStorage.getItem('xart_analysis_demo_demo_a_views'))")


def draft_demo(page):
    return page.evaluate("JSON.parse(localStorage.getItem('xart_analysis_demo_demo_a_drafts'))")


def open_menu(page):
    page.locator("#view-menu > summary").click()


def test_preview_debounce_close_discard_reload_and_panel_reset(review_server, review_browser):
    from playwright.sync_api import expect

    page = review_browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(review_server + "/analytics?demo=1#views")
    page.wait_for_selector(".chart-svg")
    initial = copy.deepcopy(saved_demo(page)[-1])
    panel_id = initial["config"]["panels"][0]["id"]
    page.locator("[data-settings]").first.click()
    assert page.locator("#settings").evaluate("el => el.tagName") == "ASIDE"
    assert page.locator("#settings details[data-section]").count() == 7
    requests = []
    page.on("request", lambda request: requests.append(request.post_data_json) if request.url.endswith("/demo-api/query") else None)
    section(page, "details")
    title = page.get_by_label("名前", exact=True)
    title.fill("プレビュー1")
    title.fill("プレビュー2")
    title.fill("プレビュー3")
    expect(page.locator(".panel h2").first).to_have_text("プレビュー3")
    assert len(requests) == 1  # unchanged panels reuse their previous query results
    assert page.locator("#settings").is_visible()
    assert saved_demo(page)[-1] == initial
    page.locator("#close-settings").click()
    assert draft_demo(page)[0]["config"]["panels"][0]["title"] == "プレビュー3"
    expect(page.locator("#save-status")).to_have_text("● 未保存")
    page.reload()  # demo drafts use the same existing draft-key format
    expect(page.locator(".panel h2").first).to_have_text("プレビュー3")
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#discard-changes").click()
    expect(page.locator(".panel h2").first).to_have_text(initial["config"]["panels"][0]["title"])
    page.locator("[data-settings]").first.click()
    section(page, "details")
    title.fill("リセット対象")
    section(page, "about")
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#reset-panel").click()
    draft = draft_demo(page)[0]
    assert draft["config"]["panels"][0]["id"] == panel_id
    assert draft["config"]["panels"][0]["title"] != "リセット対象"
    assert saved_demo(page)[-1] == initial
    page.locator("#undo-settings").click()
    expect(title).to_have_value("リセット対象")
    page.keyboard.press("Control+s")
    expect(page.locator("#save-status")).to_have_text("✓ 保存済み")
    assert saved_demo(page)[-1]["config"]["panels"][0]["title"] == "リセット対象"
    page.close()


def test_chart_fields_preserve_hidden_values_and_locked_editor(review_server, review_browser):
    from playwright.sync_api import expect

    page = review_browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(review_server + "/analytics?demo=1#views")
    page.wait_for_selector(".chart-svg")
    page.locator("[data-settings]").first.click()
    expected = {
        "line": {"x"}, "bar": {"x"}, "pie": {"x"}, "scatter": {"x"},
        "box": {"x"}, "histogram": {"bins"}, "table": {"show_images"},
    }
    fields = {"x", "series", "aggregate", "allocation", "transform", "bins", "show_images", "table_group"}
    section(page, "axes")
    page.locator('[data-field="transform"]').select_option("moving_average")
    page.locator('[data-field="window"]').fill("11")
    for chart, visible in expected.items():
        page.locator(f'[data-chart-card][value="{chart}"]').locator("..").click()
        actual = set(page.locator('#settings [data-section="axes"] [data-field]').evaluate_all("els => els.map(el => el.dataset.field)")) & fields
        assert actual == visible
        assert not page.locator("[data-y]").count()
        if chart in {"pie", "scatter", "box", "histogram"}:
            assert page.locator("[data-single-y]").count() == 1
        elif chart in {"line", "bar"}:
            assert page.locator("[data-add-y]").count() == 1
        section(page, "style")
        if chart == "pie":
            assert page.locator('[data-field="style.x_min"], [data-field="style.y_max"]').count() == 0
    page.locator('[data-chart-card][value="line"]').locator("..").click()
    expect(page.locator('[data-field="transform"]')).to_have_value("moving_average")
    expect(page.locator('[data-field="window"]')).to_have_value("11")
    page.locator('[data-field="transform"]').select_option("none")
    page.keyboard.press("Control+s")
    expect(page.locator("#save-status")).to_have_text("✓ 保存済み")
    page.locator("#toggle-lock").click()
    expect(page.locator("#settings-lock-message")).to_be_visible()
    assert page.locator("#settings-body input, #settings-body select, #settings-body button:not(.setting-info)").evaluate_all("els => els.every(el => el.disabled)")
    page.locator("#toggle-lock").click()
    expect(page.locator("#settings-lock-message")).to_be_hidden()
    expect(page.get_by_label("名前", exact=True)).to_be_enabled()
    expect(page.locator("#view-lock-state")).to_be_hidden()
    page.close()


def test_rebuild_is_draft_and_undoable(review_server, review_browser):
    from playwright.sync_api import expect

    page = review_browser.new_page()
    page.goto(review_server + "/analytics?demo=1#views")
    page.wait_for_selector(".chart-svg")
    before = saved_demo(page)[-1]
    open_menu(page)
    page.locator("#rebuild-view").click()
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator('[data-rebuild="0"]').click()
    expect(page.locator(".panel")).to_have_count(1)
    after = draft_demo(page)[0]
    assert (after["id"], after["name"], after.get("locked", False)) == (before["id"], before["name"], before.get("locked", False))
    assert after["config"]["layout"] == "single"
    assert saved_demo(page)[-1] == before
    page.locator("#undo-settings").click()
    expect(page.locator(".panel")).to_have_count(4)
    assert draft_demo(page)[0]["config"] == before["config"]
    page.close()


def test_legacy_all_fields_roundtrip_and_inline_validation(review_server, review_browser):
    from playwright.sync_api import expect

    page = review_browser.new_page(viewport={"width": 1440, "height": 1000})
    profile = page.request.post(review_server + "/api/profiles", data={"name": "互換性テスト"}).json()
    headers = {"X-Analysis-Profile": profile["id"]}
    panels = []
    for chart in ["table", "line", "bar", "pie", "scatter", "box", "histogram"]:
        panel = Panel(id=f"legacy_{chart}", chart=chart).model_dump()
        panel.update(title=f"旧設定 {chart}", x="date", y=["likes"], series="character", period_days=90,
                     from_date="2026-01-01", to_date="2026-12-31", aggregate="median", allocation="combination",
                     filters=[{"join":"or", "rules":[{"field":"likes", "op":"gte", "value":0}]}], filter_join="or",
                     formulas=[{"key":"calc_legacy", "label":"独自指標", "expression":"likes * 2", "scope":"row"}],
                     table_sorts=[{"field":"likes", "desc":True},{"field":"date", "desc":False}],
                     table_group="date", table_group_dates="month", table_group_order="desc",
                     table_group_multivalue="combination", table_collapsed_groups=["old-key"], show_images=False)
        panel["style"].update(color="#447869", legend=False, labels=True, x_label="投稿日", y_label="反応",
                              x_min=0, x_max=100, y_min=0, y_max=10000, x_tick_interval=3, y_tick_interval=25,
                              x_tick_unit="hour", sort="y_desc")
        if chart == "line":
            panel.update(transform="moving_average", window=9, compare_previous=True)
        panels.append(panel)
    response = page.request.post(review_server + "/api/analytics/views", headers=headers, data={"name":"全設定の旧ビュー", "config":{"version":1,"layout":"dashboard","panels":panels}})
    assert response.status == 201, response.text()
    before = response.json()
    page.add_init_script(f"localStorage.setItem('xart_profile_id', JSON.stringify({json.dumps(profile['id'])}))")
    page.goto(review_server + "/analytics#views")
    page.wait_for_selector("[data-settings]")
    for index in range(7):
        page.locator("[data-settings]").nth(index).click()
        for key in ["filters", "style", "advanced", "about"]:
            section(page, key)
        expect(page.get_by_label("名前", exact=True)).to_have_value(panels[index]["title"])
        page.locator("#close-settings").click()
    page.locator("[data-settings]").first.click()
    section(page, "details")
    page.get_by_label("名前", exact=True).fill("変更")
    section(page, "details")
    page.get_by_label("名前", exact=True).fill(panels[0]["title"])
    page.keyboard.press("Control+s")
    expect(page.locator("#save-status")).to_have_text("✓ 保存済み")
    after = page.request.get(review_server + "/api/analytics/views", headers=headers).json()["views"][0]
    assert after["config"] == before["config"]
    assert after["revision"] == before["revision"] + 1
    section(page, "details")
    page.locator('[data-field="period_days"]').fill("-1")
    expect(page.locator('[data-field="period_days"]')).to_have_attribute("aria-invalid", "true")
    assert page.locator("#settings-error").count() == 0
    assert page.locator(".field-error").count() == 1
    page.locator('[data-field="period_days"]').fill("90")
    page.locator('[data-chart-card][value="line"]').locator("..").click()
    section(page, "details")
    page.locator('[data-field="style.x_min"]').fill("150")
    expect(page.locator('[data-field="style.x_min"]')).to_have_attribute("aria-invalid", "true")
    assert page.locator(".field-error").count() == 1
    page.close()


@pytest.mark.parametrize("demo", [True, False])
def test_bulk_reset_requires_download_and_count_and_preserves_locked_views(review_server, review_browser, demo, tmp_path):
    from playwright.sync_api import expect

    page = review_browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    if not demo:
        target = page.request.post(review_server + "/api/profiles", data={"name":"リセット対象"}).json()
        other = page.request.post(review_server + "/api/profiles", data={"name":"別の利用者"}).json()
        headers = {"X-Analysis-Profile":target["id"]}
        other_headers = {"X-Analysis-Profile":other["id"]}
        for name in ["削除するビュー", "ロックしたビュー"]:
            view = page.request.post(review_server + "/api/analytics/views", headers=headers, data={"name":name}).json()
        locked = page.request.patch(review_server + f"/api/analytics/views/{view['id']}/lock", headers=headers, data={"locked":True,"revision":view["revision"]})
        assert locked.status == 200, locked.text()
        assert locked.json()["locked"] is True
        other_view = page.request.post(review_server + "/api/analytics/views", headers=other_headers, data={"name":"別利用者のビュー"}).json()
        calendar = page.request.get(review_server + "/api/calendar?year=2026&month=10").json()
        page.add_init_script(f"localStorage.setItem('xart_profile_id', JSON.stringify({json.dumps(target['id'])}))")
    page.goto(review_server + ("/analytics?demo=1#views" if demo else "/analytics#views"))
    page.wait_for_selector("#view-name")
    if demo:
        page.locator("#toggle-lock").click()
        expect(page.locator("#view-lock-state")).to_be_visible()
    count = page.locator("#view-list [data-view]").count()
    page.get_by_role("button", name="すべてのビューをリセット…", exact=True).click()
    expect(page.locator("#confirm-reset-views")).to_be_disabled()
    page.locator("#reset-views-count").fill(str(count))
    expect(page.locator("#confirm-reset-views")).to_be_disabled()
    with page.expect_download() as download:
        page.locator("#download-views").click()
    path = tmp_path / "backup.json"
    download.value.save_as(path)
    backup = json.loads(path.read_text())
    assert len(backup["views"]) == count
    assert sum(view.get("locked", False) for view in backup["views"]) == 1, backup
    assert download.value.suggested_filename.startswith("analytics-views-backup-")
    page.locator("#reset-views-count").fill("999")
    expect(page.locator("#confirm-reset-views")).to_be_disabled()
    page.locator("#reset-views-count").fill(str(count))
    page.locator("#confirm-reset-views").click()
    expect(page.locator("#view-list [data-view]")).to_have_count(1)
    expect(page.locator("#toast")).to_contain_text("ロック中のため 1 件を残しました")
    expect(page.locator("#empty-views")).to_be_visible()
    if demo:
        assert len(saved_demo(page)) == 1
    else:
        assert page.request.get(review_server + "/api/analytics/views", headers=other_headers).json()["views"] == [other_view]
        assert page.request.get(review_server + "/api/calendar?year=2026&month=10").json() == calendar
    page.locator("#view-list [data-view]").click()
    page.locator("#toggle-lock").click()
    expect(page.locator("#view-lock-state")).to_be_hidden()
    page.get_by_role("button", name="すべてのビューをリセット…", exact=True).click()
    with page.expect_download():
        page.locator("#download-views").click()
    page.locator("#reset-views-count").fill("1")
    page.locator("#confirm-reset-views").click()
    expect(page.locator("#empty-views")).to_be_visible()
    page.reload()
    expect(page.locator("#empty-views")).to_be_visible()
    page.close()


def test_revision_conflict_retains_draft_and_recovers_as_new_view(review_server, review_browser):
    from playwright.sync_api import expect

    page = review_browser.new_page()
    profile = page.request.post(review_server + "/api/profiles", data={"name":"競合テスト"}).json()
    headers = {"X-Analysis-Profile":profile["id"]}
    view = page.request.post(review_server + "/api/analytics/views", headers=headers, data={"name":"競合前"}).json()
    page.add_init_script(f"localStorage.setItem('xart_profile_id', JSON.stringify({json.dumps(profile['id'])}))")
    page.goto(review_server + "/analytics#views")
    page.locator("[data-settings]").click()
    section(page, "details")
    page.get_by_label("名前", exact=True).fill("保持する下書き")
    updated = page.request.patch(review_server + f"/api/analytics/views/{view['id']}", headers=headers,
                                 data={"name":"別タブの更新", "config":view["config"], "revision":view["revision"]})
    assert updated.status == 200
    page.keyboard.press("Control+s")
    expect(page.locator("#conflict-dialog")).to_be_visible()
    drafts = page.evaluate(f"JSON.parse(localStorage.getItem('xart_analysis_user_{profile['id']}_drafts'))")
    assert drafts[0]["config"]["panels"][0]["title"] == "保持する下書き"
    page.locator("#recover-view").click()
    expect(page.locator("#conflict-dialog")).to_be_hidden()
    expect(page.locator("#view-name")).to_have_value("競合前（復元）")
    views = page.request.get(review_server + "/api/analytics/views", headers=headers).json()["views"]
    assert len(views) == 2
    assert next(item for item in views if item["id"] == view["id"])["name"] == "別タブの更新"
    assert next(item for item in views if item["id"] != view["id"])["config"]["panels"][0]["title"] == "保持する下書き"
    page.close()


def test_keyboard_create_add_edit_save_reset(review_server, review_browser):
    from playwright.sync_api import expect

    page = review_browser.new_page(viewport={"width":1440,"height":1000})
    page.goto(review_server + "/analytics?demo=1#views")
    page.wait_for_selector(".chart-svg")

    def tab_to(selector):
        for _ in range(180):
            if page.locator(selector).evaluate("el => el === document.activeElement"):
                return
            page.keyboard.press("Tab")
        pytest.fail(f"Keyboard could not reach {selector}")

    tab_to("#new-view")
    page.keyboard.press("Enter")
    tab_to("#create-templates [data-template='0']")
    page.keyboard.press("Enter")
    expect(page.locator("#view-name")).to_have_value("作品テーブル")
    tab_to("#add-panel")
    page.keyboard.press("Enter")
    tab_to("#panel-types [data-panel-type='1']")
    page.keyboard.press("Enter")
    expect(page.locator("#settings")).to_be_visible()
    tab_to("#settings [data-section='details'] > summary")
    page.keyboard.press("Enter")
    tab_to("#settings [data-field='title']")
    page.keyboard.press("Control+a")
    page.keyboard.type("Keyboard panel")
    page.keyboard.press("Control+s")
    expect(page.locator("#save-status")).to_have_text("✓ 保存済み")
    tab_to("#reset-panel")
    page.once("dialog", lambda dialog: dialog.accept())
    page.keyboard.press("Enter")
    expect(page.get_by_label("名前", exact=True)).to_have_value("投稿後のいいね推移")
    expect(page.locator("#save-status")).to_have_text("● 未保存")
    page.keyboard.press("Escape")
    expect(page.locator("#settings")).to_be_hidden()
    page.keyboard.press("Control+z")
    expect(page.locator("#save-status")).to_have_text("● 未保存")
    page.keyboard.press("Control+s")
    expect(page.locator("#save-status")).to_have_text("✓ 保存済み")
    page.close()


@pytest.mark.skipif(not os.getenv("ANALYTICS_GUIDE_IMAGES"), reason="Explicit demo screenshot generation only")
def test_capture_demo_guide_images(review_server, review_browser):
    """Run with ANALYTICS_GUIDE_IMAGES=docs/images/analytics to refresh the guide."""
    from pathlib import Path
    from playwright.sync_api import expect

    output = Path(os.environ["ANALYTICS_GUIDE_IMAGES"])
    output.mkdir(parents=True, exist_ok=True)
    page = review_browser.new_page(viewport={"width":390,"height":844}, has_touch=True, reduced_motion="reduce")
    page.goto(review_server + "/analytics?demo=1#views")
    page.wait_for_selector(".chart-svg")

    def capture(name):
        page.evaluate("window.scrollTo(0,0)")
        page.screenshot(path=str(output / name), type="jpeg", quality=85)

    capture("views.jpg")
    page.locator("#view-select").select_option(label="キャラクターの勢い")
    page.wait_for_selector(".chart-svg")
    capture("chart.jpg")
    page.locator("[data-settings]").click()
    page.locator("#sheet-handle").click()
    page.wait_for_timeout(250)
    capture("settings-mobile.jpg")
    page.set_viewport_size({"width":1440,"height":1000})
    page.locator('#settings [data-section="axes"]').evaluate("el => el.open = true")
    page.locator('[data-field="x"]').select_option("measured_at")
    page.wait_for_timeout(500)
    capture("settings.jpg")
    page.locator("#close-settings").click()
    page.keyboard.press("Control+s")
    expect(page.locator("#save-status")).to_have_text("✓ 保存済み")
    page.set_viewport_size({"width":390,"height":844})
    capture("saved.jpg")
    page.locator("#toggle-lock").click()
    expect(page.locator("#view-lock-state")).to_be_visible()
    capture("locked.jpg")
    page.locator("#view-select").select_option(label="作品テーブル")
    page.wait_for_selector(".character-cell")
    capture("table.jpg")
    page.locator(".character-cell").first.click()
    expect(page.locator("#character-dialog")).to_be_visible()
    capture("characters.jpg")
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    page.locator("#new-view").click()
    capture("templates.jpg")
    page.keyboard.press("Escape")
    page.locator("#add-panel").click()
    page.locator('[data-panel-type="4"]').click()
    page.locator("#close-settings").click()
    page.wait_for_selector(".scatter-point")
    page.locator(".scatter-point").first.click()
    capture("scatter.jpg")
    page.close()


def test_sheet_handle_resize_drag_and_escape_keep_draft(review_server, review_browser):
    from playwright.sync_api import expect

    page = review_browser.new_page(viewport={"width":390,"height":844}, has_touch=True)
    page.goto(review_server + "/analytics?demo=1#views")
    page.wait_for_selector(".chart-svg")
    page.locator("[data-settings]").first.click()
    section(page, "details")
    page.get_by_label("名前", exact=True).fill("シート下書き")
    handle = page.locator("#sheet-handle")
    before = page.locator("#settings").bounding_box()["height"]
    handle.focus()
    page.keyboard.press("Space")
    expect(handle).to_have_attribute("aria-expanded", "true")
    assert page.locator("#settings").bounding_box()["height"] > before
    page.keyboard.press("Space")
    expect(handle).to_have_attribute("aria-expanded", "false")
    box = handle.bounding_box()
    page.mouse.move(box["x"] + 50, box["y"] + 20)
    page.mouse.down()
    page.mouse.move(box["x"] + 50, box["y"] - 60, steps=5)
    page.mouse.up()
    expect(handle).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("Escape")
    expect(page.locator("#settings")).to_be_hidden()
    assert draft_demo(page)[0]["config"]["panels"][0]["title"] == "シート下書き"
    page.close()


def test_single_panel_tabs_update_the_open_editor(review_server, review_browser):
    from playwright.sync_api import expect

    page = review_browser.new_page(viewport={"width":1440,"height":1000})
    page.goto(review_server + "/analytics?demo=1#views")
    page.wait_for_selector(".chart-svg")
    page.locator("#view-select").select_option(label="作品テーブル") if page.locator("#view-select").is_visible() else page.locator("#view-list button", has_text="作品テーブル").click()
    page.locator("#add-panel").click()
    page.locator('[data-panel-type="4"]').click()
    expect(page.get_by_label("名前", exact=True)).to_have_value("いいねとインプレッション")
    page.locator("#single-tabs button").first.click()
    expect(page.get_by_label("名前", exact=True)).to_have_value("作品テーブル")
    section(page, "details")
    page.get_by_label("名前", exact=True).fill("先頭の表だけ編集")
    draft = draft_demo(page)[0]
    assert draft["config"]["panels"][0]["title"] == "先頭の表だけ編集"
    assert draft["config"]["panels"][1]["title"] == "いいねとインプレッション"
    page.locator("#single-tabs button").last.click()
    expect(page.get_by_label("名前", exact=True)).to_have_value("いいねとインプレッション")
    page.close()
