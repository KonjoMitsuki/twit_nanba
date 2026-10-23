"""Real pointer and touchscreen gestures on isolated, synthetic SVG charts."""

import os
import shutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ANALYTICS_BROWSER_TESTS") != "1", reason="Opt-in browser verification"
)
WEB = Path(__file__).resolve().parents[1] / "web"


def setup_chart(page, chart="line", dates=False, categories=False):
    page.set_content(
        '<main style="max-width:900px;margin:20px auto"><div id="chart" class="chart-container"></div><button id="outside">外</button></main>'
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
        for kind in ["scatter", "box", "histogram"]:
            setup_chart(page, chart=kind, categories=kind == "box")
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
