/* Axis math and pointer controls shared by the SVG charts. */
(() => {
  function ticks(min, max, interval, count = 5) {
    if (max === min && Number.isFinite(min)) return [min];
    if (!(max > min)) return [];
    if (!(interval > 0))
      return Array.from(
        { length: count },
        (_, i) => min + ((max - min) * i) / (count - 1),
      );
    // Keep a small interval safe without changing the saved setting.
    const stride = Math.max(1, Math.ceil((max - min) / interval / 200));
    const step = Number.isFinite(stride)
      ? interval * stride
      : (max - min) / 200;
    const first = Math.ceil(min / step - 1e-10) * step;
    return Array.from(
      {
        length: Math.min(
          201,
          Math.max(0, Math.floor((max - first) / step + 1e-9) + 1),
        ),
      },
      (_, i) => Number((first + step * i).toPrecision(13)),
    );
  }
  function fit(min, max, low, high) {
    const span = Math.min(high - low, Math.max((high - low) / 1000, max - min));
    const start = Math.min(high - span, Math.max(low, min));
    return [start, start + span];
  }
  function zoom(view, base, factor, ax = 0.5, ay = 0.5) {
    const resize = (min, max, low, high, anchor) => {
      const span = (max - min) * factor,
        center = min + (max - min) * anchor;
      return fit(
        center - span * anchor,
        center + span * (1 - anchor),
        low,
        high,
      );
    };
    const [xmin, xmax] = resize(view.xmin, view.xmax, base.xmin, base.xmax, ax);
    const [ymin, ymax] = resize(view.ymin, view.ymax, base.ymin, base.ymax, ay);
    return { xmin, xmax, ymin, ymax };
  }
  function pan(view, base, dx, dy) {
    const [xmin, xmax] = fit(
      view.xmin + dx,
      view.xmax + dx,
      base.xmin,
      base.xmax,
    );
    const [ymin, ymax] = fit(
      view.ymin + dy,
      view.ymax + dy,
      base.ymin,
      base.ymax,
    );
    return { xmin, xmax, ymin, ymax };
  }
  function bind(host, info) {
    host.chartInfo = info;
    if (host.chartBound) return;
    host.chartBound = true;
    const pointers = new Map();
    let gesture = null,
      frame = null,
      suppressClick = false;
    const local = (x, y) => {
      const svg = host.querySelector(".chart-svg"),
        box = svg.getBoundingClientRect(),
        p = host.chartInfo.plot;
      return {
        x: ((x - box.left) * p.W) / box.width,
        y: ((y - box.top) * p.H) / box.height,
      };
    };
    const inside = (p) => {
      const b = host.chartInfo.plot;
      return p.x >= b.l && p.x <= b.l + b.pw && p.y >= b.t && p.y <= b.t + b.ph;
    };
    const draw = () => {
      if (frame != null) return;
      frame = requestAnimationFrame(() => {
        frame = null;
        if (host.isConnected) host.chartInfo.redraw();
      });
    };
    const changeZoom = (factor, x = 0.5, y = 0.5) => {
      const i = host.chartInfo;
      host.chartViewport = zoom(i.view, i.base, factor, x, y);
      i.hide();
      draw();
    };
    const startGesture = () => {
      const ps = [...pointers.values()],
        i = host.chartInfo;
      gesture = {
        view: { ...i.view },
        start: ps[0],
        midpoint:
          ps.length > 1
            ? { x: (ps[0].x + ps[1].x) / 2, y: (ps[0].y + ps[1].y) / 2 }
            : ps[0],
        distance:
          ps.length > 1 ? Math.hypot(ps[1].x - ps[0].x, ps[1].y - ps[0].y) : 0,
        moved: false,
      };
    };
    host.addEventListener("pointerdown", (event) => {
      if (!event.target.closest(".chart-svg") || event.button !== 0) return;
      if (!host.chartInfo.plot) {
        host.chartInfo.direct(event);
        return;
      }
      const pos = local(event.clientX, event.clientY);
      if (!inside(pos)) return;
      event.preventDefault();
      pointers.set(event.pointerId, pos);
      host.setPointerCapture(event.pointerId);
      startGesture();
      if (pointers.size > 1) host.chartInfo.hide();
      else host.chartInfo.inspect(pos, event);
    });
    host.addEventListener("pointermove", (event) => {
      if (event.target.closest(".chart-tooltip")) return;
      const i = host.chartInfo;
      if (!i.plot) {
        i.direct(event);
        return;
      }
      const pos = local(event.clientX, event.clientY);
      if (!pointers.has(event.pointerId)) {
        if (event.pointerType !== "touch" && inside(pos)) i.inspect(pos, event);
        else if (!inside(pos)) i.hide();
        return;
      }
      pointers.set(event.pointerId, pos);
      const ps = [...pointers.values()],
        g = gesture,
        p = i.plot;
      if (ps.length > 1 && g.distance > 0) {
        const mid = { x: (ps[0].x + ps[1].x) / 2, y: (ps[0].y + ps[1].y) / 2 };
        const distance = Math.hypot(ps[1].x - ps[0].x, ps[1].y - ps[0].y);
        if (distance < 1) return;
        let next = zoom(
          g.view,
          i.base,
          g.distance / distance,
          (g.midpoint.x - p.l) / p.pw,
          1 - (g.midpoint.y - p.t) / p.ph,
        );
        next = pan(
          next,
          i.base,
          (-(mid.x - g.midpoint.x) / p.pw) * (next.xmax - next.xmin),
          ((mid.y - g.midpoint.y) / p.ph) * (next.ymax - next.ymin),
        );
        host.chartViewport = next;
        g.moved = suppressClick = true;
        i.hide();
        draw();
      } else if (
        event.pointerType === "touch" &&
        host.chartTouchMode === "inspect"
      ) {
        i.inspect(pos, event);
      } else if (
        Math.hypot(pos.x - g.start.x, pos.y - g.start.y) > 5 ||
        g.moved
      ) {
        host.chartViewport = pan(
          g.view,
          i.base,
          (-(pos.x - g.start.x) / p.pw) * (g.view.xmax - g.view.xmin),
          ((pos.y - g.start.y) / p.ph) * (g.view.ymax - g.view.ymin),
        );
        g.moved = suppressClick = true;
        i.hide();
        draw();
      }
    });
    const end = (event) => {
      pointers.delete(event.pointerId);
      if (host.hasPointerCapture(event.pointerId))
        host.releasePointerCapture(event.pointerId);
      if (pointers.size) startGesture();
      else gesture = null;
    };
    host.addEventListener("pointerup", end);
    host.addEventListener("pointercancel", (event) => {
      end(event);
      host.chartInfo.hide();
    });
    host.addEventListener("lostpointercapture", (event) => {
      pointers.delete(event.pointerId);
      if (!pointers.size) gesture = null;
    });
    host.addEventListener("pointerleave", () => {
      if (!pointers.size) host.chartInfo.hide();
    });
    host.addEventListener(
      "wheel",
      (event) => {
        if (!host.chartInfo.plot || !event.target.closest(".chart-svg")) return;
        const pos = local(event.clientX, event.clientY),
          i = host.chartInfo,
          p = i.plot;
        if (!inside(pos)) return;
        event.preventDefault();
        changeZoom(
          Math.exp(
            Math.max(
              -1,
              Math.min(
                1,
                event.deltaY * (event.deltaMode === 1 ? 16 : 1) * 0.002,
              ),
            ),
          ),
          (pos.x - p.l) / p.pw,
          1 - (pos.y - p.t) / p.ph,
        );
      },
      { passive: false },
    );
    host.addEventListener("dblclick", (event) => {
      if (event.target.closest(".chart-svg") && host.chartInfo.plot) {
        host.chartViewport = null;
        host.chartInfo.hide();
        draw();
      }
    });
    host.addEventListener("click", (event) => {
      const button = event.target.closest("[data-chart-action]"),
        legend = event.target.closest("[data-legend]");
      if (button) {
        const action = button.dataset.chartAction;
        host.chartRestoreFocus = action;
        if (action === "reset") {
          host.chartViewport = null;
          host.chartInfo.hide();
          draw();
        } else if (action === "in" || action === "out")
          changeZoom(action === "in" ? 0.7 : 1 / 0.7);
        else {
          host.chartTouchMode = action;
          draw();
        }
      } else if (legend) {
        host.chartInfo.legend(legend.dataset.legend);
      } else if (!suppressClick) host.chartInfo.direct(event);
      suppressClick = false;
    });
    host.addEventListener("focusin", (event) => {
      if (event.target.closest("[data-tip]")) host.chartInfo.direct(event);
    });
    host.addEventListener("keydown", (event) => {
      if (!event.target.closest(".chart-svg")) return;
      const i = host.chartInfo;
      if (event.key === "Escape") {
        i.hide();
        return;
      }
      if (!i.plot) return;
      if (["+", "=", "-", "0", "Home"].includes(event.key)) {
        event.preventDefault();
        host.chartRestoreFocus = "svg";
        if (event.key === "0" || event.key === "Home") {
          host.chartViewport = null;
          i.hide();
          draw();
        } else changeZoom(event.key === "-" ? 1 / 0.7 : 0.7);
      } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        i.step(event.key === "ArrowLeft" ? -1 : 1);
      }
    });
  }
  const api = { ticks, zoom, pan, bind };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.AnalysisChartInteractions = api;
})();
