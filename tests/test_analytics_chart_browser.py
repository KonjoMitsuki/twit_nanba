"""Real pointer and touchscreen gestures on isolated, synthetic SVG charts."""

import os
import shutil
from pathlib import Path

import pytest
from test_analytics_layout_browser import review_server

pytestmark = pytest.mark.skipif(
    os.getenv("ANALYTICS_BROWSER_TESTS") != "1", reason="Opt-in browser verification"
)
WEB = Path(__file__).resolve().parents[1] / "web"


def setup_chart(page, chart="line", dates=False, categories=False):
    page.set_content(
        '<meta name="viewport" content="width=device-width, initial-scale=1"><main style="max-width:900px;margin:20px auto"><div id="chart" class="chart-container"></div><button id="outside">外</button></main>'
    )
    page.add_style_tag(path=str(WEB / "css/analytics.css"))
    for script in ["analytics-chart-interactions.js", "analytics-charts.js"]:
        page.add_script_tag(path=str(WEB / script))
    page.evaluate(
        """({chart, dates, categories}) => {
      window.panel = {id:'test', chart, x:'x', y:['y'], style:{color:'#447869', legend:true, labels:false}};
      const points = Array.from({length:21}, (_, i) => ['A','B'].map((series,j) => ({
        x:dates ? new Date(Date.UTC(2026,9,20) + i*3600000).toISOString() : categories ? `分類${i}` : i*5,
        y:i*3+j*10, series, metric:'y', n:1, label:'作品'+i,
        start:i*5-2.5, end:i*5+2.5, q1:i*3-2, q3:i*3+2, median:i*3, low:i*3-4, high:i*3+4, outliers:[]
      }))).flat();
      window.result = {points, fields:{x:dates?'計測日時':'横軸', y:'いいね'}};
      window.draw = () => AnalysisCharts.render(document.querySelector('#chart'), panel, result);
      draw();
    }""",
        {"chart": chart, "dates": dates, "categories": categories},
    )


def domain(page):
    return page.locator(".chart-svg").evaluate(
        "el => ['xMin','xMax','yMin','yMax'].map(k => Number(el.dataset[k]))"
    )


def plot_point(page, x=0.5, y=0.5):
    return page.locator(".chart-svg").evaluate(
        """(el, ratios) => {
      const b=el.getBoundingClientRect(), W=el.viewBox.baseVal.width;
      return {x:b.x+(55+(W-77)*ratios[0])*b.width/W, y:b.y+(23+174*ratios[1])*b.height/245};
    }""",
        [x, y],
    )


def test_mouse_zoom_pan_crosshair_ticks_and_chart_types():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        setup_chart(page)
        original = domain(page)
        pos = plot_point(page)
        page.mouse.move(**pos)
        assert page.locator(".chart-tooltip").is_visible()
        assert page.locator(".chart-tooltip-row").count() == 2
        assert page.locator(".chart-crosshair").count() == 1
        page.mouse.wheel(0, -350)
        page.wait_for_function(
            "Number(document.querySelector('.chart-svg').dataset.xMin) > 0"
        )
        zoomed = domain(page)
        assert zoomed[1] - zoomed[0] < original[1] - original[0]
        assert zoomed[3] - zoomed[2] < original[3] - original[2]
        page.mouse.move(**pos)
        page.mouse.down()
        page.mouse.move(pos["x"] + 60, pos["y"] + 15, steps=8)
        page.mouse.up()
        page.wait_for_function(
            "lo => Number(document.querySelector('.chart-svg').dataset.xMin) < lo",
            arg=zoomed[0],
        )
        page.get_by_role("button", name="表示範囲をリセット").click()
        page.wait_for_function(
            "Number(document.querySelector('.chart-svg').dataset.xMin) === 0"
        )
        assert domain(page) == original
        page.evaluate(
            "panel.style.x_tick_interval=10; panel.style.y_tick_interval=20; draw()"
        )
        assert page.locator(".x-tick").count() == 11
        assert page.locator(".y-tick").evaluate_all(
            "els => els.map(el=>Number(el.dataset.value))"
        ) == [0, 20, 40, 60]
        page.locator(".chart-svg").focus()
        page.keyboard.press("ArrowRight")
        assert page.locator(".chart-tooltip").is_visible()
        page.keyboard.press("Escape")
        assert page.locator(".chart-tooltip").is_hidden()
        page.keyboard.press("+")
        page.wait_for_function(
            "Number(document.querySelector('.chart-svg').dataset.xMin) > 0"
        )
        page.keyboard.press("Home")
        page.wait_for_function(
            "Number(document.querySelector('.chart-svg').dataset.xMin) === 0"
        )
        page.locator('[data-legend="B|y"]').click()
        page.mouse.move(**plot_point(page))
        assert page.locator(".chart-tooltip-row").count() == 1
        page.mouse.move(0, 0)
        assert page.locator(".chart-tooltip").is_hidden()
        setup_chart(page, dates=True)
        page.evaluate(
            "panel.style.x_tick_interval=6;panel.style.x_tick_unit='hour';draw()"
        )
        assert page.locator(".x-tick").count() in [3, 4]
        ticks = page.locator(".x-tick").evaluate_all(
            "els=>els.map(el=>Number(el.dataset.value))"
        )
        assert ticks[1] - ticks[0] == 6 * 3600000
        assert "12:00" in page.locator(".x-tick").first.text_content()
        for kind in ["scatter", "bar", "box", "histogram"]:
            setup_chart(page, chart=kind, categories=kind == "box")
            if kind == "histogram":
                bars = page.locator(".chart-drawing g[data-tip] rect")
                assert bars.count() == page.evaluate("result.points.length")
                assert all(
                    "NaN" not in bar.get_attribute("x")
                    and bar.bounding_box()["width"] > 0
                    for bar in bars.all()
                )
            page.get_by_role("button", name="グラフを拡大", exact=True).click()
            page.wait_for_function(
                "() => !!document.querySelector('.chart-svg') && Number(document.querySelector('.chart-svg').dataset.xMin) > 0"
            )
            page.mouse.move(**plot_point(page))
            assert page.locator(".chart-tooltip").is_visible()
            if kind == "box":
                assert "Q1" in page.locator(".chart-tooltip").inner_text()
        assert not errors
        browser.close()


def test_touch_pinch_pan_and_inspect_mode():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        context = browser.new_context(
            viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True
        )
        page = context.new_page()
        page.set_viewport_size({"width": 375, "height": 812})
        setup_chart(page)
        cdp = context.new_cdp_session(page)
        before = domain(page)
        a, b = plot_point(page, 0.35), plot_point(page, 0.65)

        def touch(kind, points):
            cdp.send(
                "Input.dispatchTouchEvent",
                {
                    "type": kind,
                    "touchPoints": [
                        dict(point, id=i) for i, point in enumerate(points)
                    ],
                },
            )

        touch("touchStart", [a, b])
        touch("touchMove", [dict(a, x=a["x"] - 25), dict(b, x=b["x"] + 25)])
        touch("touchEnd", [])
        page.wait_for_function(
            "Number(document.querySelector('.chart-svg').dataset.xMin)>0"
        )
        after = domain(page)
        assert after[1] - after[0] < before[1] - before[0]
        mid = plot_point(page)
        touch("touchStart", [mid])
        touch("touchMove", [dict(mid, x=mid["x"] + 20)])
        touch("touchEnd", [])
        page.wait_for_function(
            "lo=>Number(document.querySelector('.chart-svg').dataset.xMin)<lo",
            arg=after[0],
        )
        page.get_by_role("button", name="値を見る", exact=True).tap()
        fixed = domain(page)
        touch("touchStart", [mid])
        touch("touchMove", [dict(mid, x=mid["x"] - 25)])
        assert page.locator(".chart-tooltip").is_visible()
        touch("touchEnd", [])
        assert domain(page) == fixed
        assert page.locator(".chart-tooltip-row").count() == 2
        page.get_by_role("button", name="移動", exact=True).tap()
        page.get_by_role("button", name="Y自動", exact=True).tap()
        manual = domain(page)
        mid = plot_point(page)
        touch("touchStart", [mid])
        touch("touchMove", [dict(mid, x=mid["x"] - 30, y=mid["y"] + 12)])
        touch("touchEnd", [])
        page.wait_for_function(
            "lo=>Number(document.querySelector('.chart-svg').dataset.yMin)>lo",
            arg=manual[2],
        )
        assert domain(page)[0] > manual[0]
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        browser.close()


def test_post_card_images_counters_safe_content_and_small_screen():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 375, "height": 812})
        page.route(
            "https://example.test/art.svg",
            lambda route: route.fulfill(
                content_type="image/svg+xml",
                body='<svg xmlns="http://www.w3.org/2000/svg" width="100" height="132"><rect width="100" height="132" fill="#447869"/></svg>',
            ),
        )
        setup_chart(page, chart="scatter")
        page.evaluate(
            """() => { result.points = [{ x:10, y:100, metric:'y', label:'投稿名', artwork:{id:'a',row_id:'s',title:'<img src=x onerror=alert(1)>',image_urls:['https://example.test/art.svg','https://example.test/second.svg'],likes:100,retweets:0,stage:'24h'}}]; draw(); }"""
        )
        page.locator("[data-tip]").focus()
        page.wait_for_function(
            "document.querySelector('.chart-artwork-photo img')?.naturalWidth > 0"
        )
        assert (
            page.locator(".chart-artwork-title").inner_text()
            == "<img src=x onerror=alert(1)>"
        )
        assert page.locator(".chart-artwork-title img").count() == 0
        assert (
            page.locator('.chart-artwork-metric[aria-label="リポスト 0"]').count() == 1
        )
        assert page.locator(".chart-artwork-image-count").inner_text() == "2枚"
        assert not page.locator(".chart-tooltip").evaluate(
            "el => el.classList.contains('is-scrollable')"
        )
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        bounds = page.locator(".chart-tooltip").bounding_box()
        assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 375
        page.evaluate(
            "result.points[0].artwork.image_urls=['javascript:alert(1)']; result.points[0].artwork.likes=null;draw()"
        )
        page.locator("[data-tip]").focus()
        assert page.locator(".chart-artwork-photo img").count() == 0
        assert page.locator(".chart-artwork-placeholder").inner_text() == "画像なし"
        assert (
            page.locator('.chart-artwork-metric[aria-label="いいね 未計測"]').count()
            == 1
        )
        page.evaluate(
            "panel.chart='line'; result.points.push({...result.points[0],series:'B'}); draw()"
        )
        page.locator("[data-tip]").first.focus()
        assert page.locator(".chart-artwork-card").count() == 1
        assert page.locator(".chart-tooltip-row").count() == 2
        browser.close()


def test_bar_chart_uses_categorical_slots_and_full_bar_hit_area():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 900, "height": 700})
        setup_chart(page, chart="bar", categories=True)
        bars = page.locator(".bar")
        assert bars.count() == 42
        boxes = bars.evaluate_all(
            "els => els.slice(0, 2).map(el => ({x:Number(el.getAttribute('x')), "
            "width:Number(el.getAttribute('width')), y:Number(el.getAttribute('y')), "
            "height:Number(el.getAttribute('height'))}))"
        )
        # Two series sit side by side inside one category, without touching.
        assert boxes[0]["x"] + boxes[0]["width"] <= boxes[1]["x"]
        assert boxes[0]["width"] > 0 and boxes[1]["height"] > boxes[0]["height"]
        # The whole bar is a hit target, not only the top edge.
        box = bars.nth(1).bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] * 0.8)
        tooltip = page.locator(".chart-tooltip")
        assert tooltip.is_visible()
        assert "分類0" in tooltip.inner_text()
        labels_before = page.locator(".chart-svg text:not(.chart-axis-readout text)").count()
        page.evaluate("panel.style.labels=true; draw()")
        assert page.locator(".chart-svg text:not(.chart-axis-readout text)").count() == labels_before + 42
        browser.close()


@pytest.fixture
def chart_page():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=shutil.which("chromium"), headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        page.set_default_timeout(5000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        setup_chart(page, dates=True)
        yield page
        browser.close()
        assert not errors


@pytest.fixture
def chart_review_browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=shutil.which("chromium"), headless=True,
            args=["--no-sandbox"],
        )
        yield browser
        browser.close()


def axis_point(page, axis):
    return page.locator(".chart-svg").first.evaluate(
        """(el, axis) => {
        const b=el.getBoundingClientRect(), v=el.viewBox.baseVal;
        return {x:b.x+(axis==='y'?30:55+(v.width-77)/2)*b.width/v.width,
                y:b.y+(axis==='x'?208:100)*b.height/v.height};
        }""", axis,
    )


def drag(page, start, dx=0, dy=0):
    page.mouse.move(**start)
    page.mouse.down()
    page.mouse.move(start["x"] + dx, start["y"] + dy, steps=8)
    page.mouse.up()
    page.evaluate("() => new Promise(requestAnimationFrame)")


def test_independent_axes_cursor_anchor_and_resets(chart_page):
    page = chart_page
    original = domain(page)
    page.evaluate("window.originalSVG=document.querySelector('.chart-svg'); window.originalToolbar=document.querySelector('.chart-toolbar')")
    # Wheel events within the same animation frame accumulate around the cursor.
    pos = plot_point(page, 0.25)
    page.mouse.move(**pos)
    ratio = page.evaluate("""pos => { for(let i=0;i<5;i++) document.querySelector('.chart-hit-area').dispatchEvent(
        new WheelEvent('wheel',{bubbles:true,cancelable:true,clientX:pos.x,clientY:pos.y,deltaY:-70})); const e=new WheelEvent('wheel',{clientX:pos.x});const svg=document.querySelector('.chart-svg'),b=svg.getBoundingClientRect(),p=document.querySelector('#chart').chartInfo.plot;return ((e.clientX-b.x)*p.W/b.width-p.l)/p.pw; }""", pos)
    page.evaluate("() => new Promise(requestAnimationFrame)")
    zoomed = domain(page)
    anchor = lambda r: r[0] + (r[1]-r[0])*ratio
    assert anchor(zoomed) == pytest.approx(anchor(original), abs=1)
    assert zoomed[1]-zoomed[0] < original[1]-original[0]
    assert zoomed[2] > original[2]  # Autoscale follows the visible window.
    assert page.locator(".chart-crosshair line").count() == 2
    assert "/" in page.locator(".chart-crosshair-time").text_content()
    assert page.locator(".chart-crosshair-value").text_content()
    assert page.locator(".chart-tooltip-row").count() == 2
    assert page.evaluate("originalSVG===document.querySelector('.chart-svg') && originalToolbar===document.querySelector('.chart-toolbar')")

    # Dragging the time axis left stretches time, with the right edge fixed.
    drag(page, axis_point(page, "x"), dx=-70)
    scaled_x = domain(page)
    assert scaled_x[1] == pytest.approx(zoomed[1], abs=1)
    assert scaled_x[1]-scaled_x[0] < zoomed[1]-zoomed[0]
    # Dragging the value axis up stretches values around the current center.
    drag(page, axis_point(page, "y"), dy=-35)
    manual = domain(page)
    assert manual[:2] == scaled_x[:2]
    assert manual[3]-manual[2] < scaled_x[3]-scaled_x[2]
    assert (manual[3]+manual[2])/2 == pytest.approx((scaled_x[3]+scaled_x[2])/2)
    assert page.locator(".chart-svg").get_attribute("data-y-mode") == "manual"
    drag(page, plot_point(page), dx=35, dy=20)
    panned = domain(page)
    assert panned[0] < manual[0]
    assert panned[2] > manual[2] and panned[3] > manual[3]
    assert panned[3]-panned[2] == pytest.approx(manual[3]-manual[2])
    page.mouse.move(**plot_point(page))
    page.mouse.wheel(0, -120)
    page.wait_for_function("old => document.querySelector('#chart').chartInfo.view.xmin!==old", arg=panned[0])
    assert domain(page)[2:] == panned[2:]
    page.mouse.dblclick(**plot_point(page))
    page.wait_for_function("document.querySelector('#chart').chartInfo.view.xmin === document.querySelector('#chart').chartInfo.base.xmin")
    assert domain(page)[:2] == original[:2]
    assert domain(page)[2:] == panned[2:]
    page.mouse.dblclick(**axis_point(page, "y"))
    page.wait_for_function("document.querySelector('.chart-svg').dataset.yMode==='auto'")
    assert domain(page) == original


def test_y_auto_button_toggles_and_manual_plot_drag_pans_y():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1100, "height": 900})
        setup_chart(page)
        button = page.get_by_role("button", name="Y自動", exact=True)
        initial = domain(page)
        assert button.get_attribute("aria-pressed") == "true"
        button.click()
        page.wait_for_function("document.querySelector('.chart-svg').dataset.yMode==='manual'")
        assert button.get_attribute("aria-pressed") == "false"
        drag(page, plot_point(page), dy=35)
        moved = domain(page)
        assert moved[:2] == initial[:2]
        assert moved[2] > initial[2] and moved[3] > initial[3]
        assert moved[3]-moved[2] == pytest.approx(initial[3]-initial[2])
        button.click()
        page.wait_for_function("document.querySelector('.chart-svg').dataset.yMode==='auto'")
        assert button.get_attribute("aria-pressed") == "true"
        assert domain(page) == initial
        browser.close()


def test_demo_dashboard_histogram_has_visible_bars(review_server, chart_review_browser):
    page = chart_review_browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(review_server + "/analytics?demo=1#views")
    page.locator("#new-view").click()
    page.locator('#create-templates [data-template="2"]').click()
    panel = page.locator(".panel").filter(has=page.locator('h2:text-is("24hいいねの分布")'))
    panel.locator(".chart-svg").wait_for()
    bars = panel.locator(".chart-drawing g[data-tip] rect")
    assert bars.count() == 12
    assert all(
        "NaN" not in bar.get_attribute("x") and bar.bounding_box()["width"] > 0
        for bar in bars.all()
    )
    growth = page.locator(".panel").filter(has=page.locator('h2:text-is("投稿後のいいね推移")'))
    svg = growth.locator(".chart-svg")
    plot_center = """el => { const b = el.getBoundingClientRect(), p = el.closest('.chart-container').chartInfo.plot;
        return {x:b.x+(p.l+p.pw/2)*b.width/p.W, y:b.y+(p.t+p.ph/2)*b.height/p.H}; }"""
    position = svg.evaluate(plot_center)
    page.mouse.move(**position)
    tooltip = growth.locator(".chart-tooltip")
    assert tooltip.is_visible()
    assert "投稿後の経過時間（h）" in tooltip.inner_text()
    assert "いいね（平均）" in tooltip.inner_text()
    assert growth.locator(".chart-tooltip-row").count() > 0
    assert growth.locator(".chart-artwork-card").count() == 0
    page.close()


def test_comparison_line_tooltip_keeps_series_values_without_artwork_cards(chart_review_browser):
    page = chart_review_browser.new_page(viewport={"width": 1100, "height": 900})
    setup_chart(page, dates=True)
    page.evaluate("""() => {
      panel.source = 'snapshots'; panel.series = 'character';
      panel.aggregate = 'mean'; panel.transform = 'none';
      result.points.forEach((p, i) => p.artwork = {
        id: String(i), row_id: String(i), title: '作品' + i,
        image_urls: [], likes: p.y, retweets: 0
      });
      draw();
    }""")
    page.mouse.move(**plot_point(page))
    tooltip = page.locator(".chart-tooltip")
    assert tooltip.is_visible()
    assert page.locator(".chart-tooltip-row").count() == 2
    assert page.locator(".chart-tooltip-count").all_text_contents() == ["1件", "1件"]
    assert "いいね（平均）" in tooltip.inner_text()
    assert page.locator(".chart-artwork-card").count() == 0
    page.evaluate("panel.series=''; draw()")
    page.mouse.move(0, 0)
    page.mouse.move(**plot_point(page))
    assert page.locator(".chart-artwork-card").count() == 2
    page.close()


def test_phone_comparison_values_scroll_with_page(chart_review_browser):
    context = chart_review_browser.new_context(
        viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True
    )
    page = context.new_page()
    setup_chart(page, dates=True)
    page.evaluate("""() => {
      document.body.style.minHeight = '1600px';
      panel.series = 'character'; panel.aggregate = 'mean'; panel.transform = 'none';
      result.points = Array.from({length: 15}, (_, i) => ({
        ...result.points[0], series: 'キャラ' + i, y: i * 10, n: i + 1
      }));
      draw();
      const info = document.querySelector('#chart').chartInfo;
      info.inspect({x: info.plot.l + info.plot.pw / 2, y: info.plot.t + info.plot.ph / 2});
    }""")
    tooltip = page.locator(".chart-tooltip")
    assert tooltip.is_visible()
    assert page.locator(".chart-tooltip-row").count() == 15
    assert tooltip.evaluate("el => getComputedStyle(el).position") == "static"
    assert tooltip.evaluate("el => el.scrollHeight <= el.clientHeight")
    box = tooltip.bounding_box()
    start = {"x": box["x"] + box["width"] / 2, "y": box["y"] + 40}
    cdp = context.new_cdp_session(page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [dict(start, id=0)]})
    for distance in [20, 60, 120]:
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [dict(start, id=0, y=start["y"] - distance)]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    page.wait_for_function("scrollY > 0")
    context.close()


def test_settings_refresh_and_manual_scale_are_separate(chart_page):
    page = chart_page
    page.evaluate("panel.style.y_min=10;panel.style.y_max=100;draw()")
    assert domain(page)[2:] == [10, 100]
    drag(page, axis_point(page, "y"), dy=-30)
    manual = domain(page)
    page.evaluate("result=structuredClone(result); result.points.push({...result.points.at(-1),x:new Date(Date.parse(result.points.at(-1).x)+3600000).toISOString(),y:1000});draw()")
    assert domain(page)[2:] == manual[2:]
    assert page.evaluate("[panel.style.y_min,panel.style.y_max]") == [10, 100]
    page.get_by_role("button", name="Y自動", exact=True).click()
    page.wait_for_function("document.querySelector('.chart-svg').dataset.yMode==='auto'")
    assert domain(page)[2:] == [10, 100]
    pos = plot_point(page)
    page.mouse.move(**pos)
    page.mouse.wheel(0, -250)
    page.wait_for_function("document.querySelector('#chart').chartViewport!==null")
    before = domain(page)
    # New result objects and cosmetic settings preserve the viewport.
    page.evaluate("result=structuredClone(result);panel.style.color='#6686a5';draw()")
    assert domain(page) == before
    page.evaluate("panel.style.y_max=120;draw()")
    assert domain(page)[3] == 120
    assert domain(page)[:2] == before[:2]
    page.evaluate("panel.x='another_time_field';draw()")
    assert domain(page)[0] < before[0]


@pytest.mark.parametrize("values", [[7, 7], [-10, -2], [None, None]])
def test_constant_negative_and_missing_values(chart_page, values):
    page = chart_page
    page.evaluate("values => {result.points=result.points.slice(0,2).map((p,i)=>({...p,y:values[i]}));draw()}", values)
    if values == [None, None]:
        assert page.locator(".panel-empty").is_visible()
        assert page.locator(".chart-svg").count() == 0
    else:
        r = domain(page)
        assert r[2] < min(values) <= max(values) < r[3]
        assert "NaN" not in page.locator(".chart-svg").inner_html()


def test_empty_time_window_and_hidden_series(chart_page):
    page = chart_page
    page.evaluate("""() => {
      result.points = [0,10].map((i)=>({...result.points[0],x:new Date(Date.UTC(2026,9,20)+i*3600000).toISOString(),y:i?20:null})); draw();
      const h=document.querySelector('#chart'), b=h.chartInfo.base;
      h.chartViewport={...b,xmin:b.xmin+3600000,xmax:b.xmin+2*3600000}; h.chartInfo.redraw();
    }""")
    r = domain(page)
    assert r[3] > r[2]
    page.mouse.move(**plot_point(page))
    assert page.locator(".chart-crosshair line").count() == 2
    page.locator("[data-legend]").click()
    assert domain(page)[3] > domain(page)[2]



def test_large_dataset_keeps_dom_and_requests_bounded(chart_page):
    page = chart_page
    stats = page.evaluate("""async () => {
      result.points=Array.from({length:50000},(_,i)=>({x:new Date(Date.UTC(2026,9,20)+i*60000).toISOString(),y:i===12345?999:Math.sin(i/20)*20+50,metric:'y'}));
      draw(); const h=document.querySelector('#chart'), svg=h.querySelector('svg'), toolbar=h.querySelector('.chart-toolbar');
      window.requests=0;window.fetch=()=>{requests++;throw Error('Unexpected API request')};
      const times=[];h.querySelector('.chart-data').open=true;
      for(let i=0;i<12;i++) {
        h.chartViewport=AnalysisChartInteractions.zoom(h.chartViewport||h.chartInfo.view,h.chartInfo.base,.95,.3);
        const start=performance.now();h.chartInfo.redraw();times.push(performance.now()-start);
      }
      window.chartTimings=times;
      return {times,nodes:svg.querySelectorAll('*').length,requests,sameSVG:svg===h.querySelector('svg'),sameToolbar:toolbar===h.querySelector('.chart-toolbar'),dataOpen:h.querySelector('.chart-data').open,sourcePoints:result.points.length};
    }""")
    assert stats['requests'] == 0
    assert stats['sameSVG'] and stats['sameToolbar'] and stats['dataOpen']
    assert stats['nodes'] < 5000
    assert stats['sourcePoints'] == 50000
    assert sorted(stats['times'])[len(stats['times'])//2] < 200
    print(f"50000 points viewport redraw: median={sorted(stats['times'])[6]:.1f}ms, max={max(stats['times']):.1f}ms, SVG nodes={stats['nodes']}")


@pytest.mark.parametrize("width,height", [(375, 812), (844, 390)])
def test_touch_keeps_vertical_page_scroll_and_tooltips_in_bounds(width, height):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which("chromium"), args=["--no-sandbox"])
        context = browser.new_context(viewport={"width": width, "height": height}, is_mobile=True, has_touch=True)
        page = context.new_page()
        page.set_default_timeout(5000)
        setup_chart(page, dates=True)
        page.evaluate("document.body.style.minHeight='2000px'")
        cdp = context.new_cdp_session(page)

        def touch(kind, points):
            cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [dict(p, id=i) for i, p in enumerate(points)]})

        # Native page scrolling must remain available when a swipe starts on the plot.
        before = domain(page)
        pos = plot_point(page, 0.5, 0.85)
        touch("touchStart", [pos])
        for distance in [15, 30, 60, 90]:
            touch("touchMove", [dict(pos, y=pos['y']-distance)])
        touch("touchEnd", [])
        page.wait_for_function("scrollY > 0")
        assert domain(page) == before
        page.evaluate("scrollTo(0,0)")
        # Two-finger pinch, including vertical movement, remains a chart operation.
        a, b = plot_point(page, 0.3), plot_point(page, 0.7)
        touch("touchStart", [a, b])
        touch("touchMove", [dict(a, x=a['x']-15, y=a['y']-5), dict(b, x=b['x']+15, y=b['y']+5)])
        touch("touchEnd", [])
        page.wait_for_function("document.querySelector('#chart').chartInfo.view.xmin > document.querySelector('#chart').chartInfo.base.xmin")
        # CDP mobile viewports can round their page scale by a fraction of a percent.
        assert page.evaluate("visualViewport.scale") == pytest.approx(1, abs=0.005)
        page.get_by_role("button", name="値を見る", exact=True).tap()
        pos = plot_point(page, 0.9)
        touch("touchStart", [pos])
        touch("touchMove", [dict(pos, x=pos['x']-20)])
        tooltip = page.locator('.chart-tooltip').bounding_box()
        assert tooltip and tooltip['x'] >= 0 and tooltip['x']+tooltip['width'] <= width+1
        assert page.locator('.chart-crosshair line').count() == 2
        for box in page.locator('.chart-axis-readout rect').evaluate_all("els=>els.map(e=>{const b=e.getBoundingClientRect();return {x:b.x,right:b.right}})"):
            assert box['x'] >= 0 and box['right'] <= width+1
        touch("touchEnd", [])
        browser.close()


def test_repeated_render_does_not_duplicate_wheel_listeners(chart_page):
    page = chart_page
    page.evaluate("for(let i=0;i<25;i++) draw(); const h=document.querySelector('#chart');window.redraws=0;const original=h.chartInfo.redraw;h.chartInfo.redraw=()=>{redraws++;original()}")
    before = domain(page)
    pos = plot_point(page)
    page.mouse.move(**pos)
    page.mouse.wheel(0, -100)
    page.wait_for_function("redraws > 0")
    after = domain(page)
    import math

    assert after[1]-after[0] == pytest.approx((before[1]-before[0])*math.exp(-0.2), abs=1)
    assert page.evaluate('redraws') == 1


def test_touch_drag_starting_on_data_point_survives_redraws():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
        context = browser.new_context(viewport={'width':375,'height':812},is_mobile=True,has_touch=True)
        page = context.new_page()
        setup_chart(page, dates=True)
        page.locator('[data-chart-action="in"]').click()
        page.wait_for_function("document.querySelector('#chart').chartViewport!==null")
        before = domain(page)
        target = page.locator('[data-point-index="10"] circle').last
        box = target.bounding_box()
        start = {'x':box['x']+box['width']/2,'y':box['y']+box['height']/2,'id':0}
        cdp = context.new_cdp_session(page)
        cdp.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[start]})
        for dx in [10,20,30,40]:
            cdp.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[dict(start,x=start['x']+dx)]})
            page.evaluate('() => new Promise(requestAnimationFrame)')
        cdp.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
        page.evaluate('() => new Promise(requestAnimationFrame)')
        after = domain(page)
        assert after[0] < before[0]
        assert after[1]-after[0] == pytest.approx(before[1]-before[0],abs=1)
        # The full drag distance, rather than only its first frame, is applied.
        shift = page.locator('#chart').evaluate("h=>40*h.chartInfo.plot.W/h.querySelector('svg').getBoundingClientRect().width/h.chartInfo.plot.pw*(h.chartInfo.view.xmax-h.chartInfo.view.xmin)")
        assert before[0]-after[0] == pytest.approx(shift,rel=0.05)
        browser.close()
