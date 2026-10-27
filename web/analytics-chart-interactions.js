/* Independent viewport math and shared mouse/touch gesture state for SVG charts. */
(() => {
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  function ticks(min, max, interval, count = 5) {
    if (max === min && Number.isFinite(min)) return [min];
    if (!(max > min)) return [];
    if (!(interval > 0))
      return Array.from(
        { length: count },
        (_, i) => min + ((max - min) * i) / (count - 1),
      );
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
    const span = clamp(max - min, (high - low) / 1000, high - low);
    const start = clamp(min, low, high - span);
    return [start, start + span];
  }
  function zoom(view, base, factor, anchor = 0.5) {
    // Clamp the span BEFORE positioning it, so the cursor stays anchored at limits.
    const span = clamp(
      (view.xmax - view.xmin) * factor,
      (base.xmax - base.xmin) / 1000,
      base.xmax - base.xmin,
    );
    const center = view.xmin + (view.xmax - view.xmin) * anchor;
    const [xmin, xmax] = fit(
      center - span * anchor,
      center + span * (1 - anchor),
      base.xmin,
      base.xmax,
    );
    return { ...view, xmin, xmax };
  }
  function pan(view, base, dx) {
    const [xmin, xmax] = fit(
      view.xmin + dx,
      view.xmax + dx,
      base.xmin,
      base.xmax,
    );
    return { ...view, xmin, xmax };
  }
  function panY(view, dy) {
    const span = view.ymax - view.ymin;
    const shift = clamp(dy, -span * 10000, span * 10000);
    return { ...view, ymin: view.ymin + shift, ymax: view.ymax + shift };
  }
  function scaleY(view, base, factor) {
    const center = (view.ymin + view.ymax) / 2;
    const reference = base.ymax - base.ymin;
    const span = clamp(
      (view.ymax - view.ymin) * factor,
      Math.max(reference / 10000, Math.abs(center) * Number.EPSILON * 16, 1e-9),
      reference * 10000,
    );
    return { ...view, ymin: center - span / 2, ymax: center + span / 2 };
  }
  function bind(host, info) {
    host.chartInfo = info;
    if (host.chartBound) return;
    host.chartBound = true;
    const pointers = new Map();
    let gesture = null,
      frame = null,
      suppressClick = false,
      hover = null;
    const local = (x, y) => {
      const svg = host.querySelector(".chart-svg"),
        b = svg.getBoundingClientRect(),
        p = host.chartInfo.plot;
      return {
        x: ((x - b.left) * p.W) / b.width,
        y: ((y - b.top) * p.H) / b.height,
      };
    };
    const region = (pos) => {
      const p = host.chartInfo.plot;
      if (pos.y >= p.t && pos.y <= p.t + p.ph && pos.x < p.l) return "y";
      if (pos.x >= p.l && pos.x <= p.l + p.pw) {
        if (pos.y >= p.t + p.ph) return "x";
        if (pos.y >= p.t) return "plot";
      }
      return null;
    };
    const current = () => host.chartViewport || host.chartInfo.view;
    const draw = () => {
      if (frame != null) return;
      frame = requestAnimationFrame(() => {
        frame = null;
        if (!host.isConnected || !host.chartInfo.plot) return;
        host.chartInfo.redraw();
        if (hover && !gesture) host.chartInfo.inspect(hover);
      });
    };
    const changeZoom = (factor, anchor = 0.5) => {
      host.chartViewport = zoom(current(), host.chartInfo.base, factor, anchor);
      if (!hover) host.chartInfo.hide();
      draw();
    };
    const startGesture = (area, touch = false) => {
      const ps = [...pointers.values()];
      gesture = {
        view: { ...current() },
        start: ps[0],
        area,
        touch,
        midpoint:
          ps.length > 1
            ? { x: (ps[0].x + ps[1].x) / 2, y: (ps[0].y + ps[1].y) / 2 }
            : ps[0],
        distance:
          ps.length > 1 ? Math.hypot(ps[1].x - ps[0].x, ps[1].y - ps[0].y) : 0,
        moved: false,
        direction: null,
      };
    };
    const down = (id, pos, touch) => {
      const area = region(pos);
      if (!area) return false;
      pointers.set(id, pos);
      startGesture(pointers.size > 1 ? "plot" : area, touch);
      hover = null;
      if (area === "y") host.chartYMode = "manual";
      if (pointers.size > 1 || area !== "plot") host.chartInfo.hide();
      else host.chartInfo.inspect(pos);
      return true;
    };
    const move = (id, pos) => {
      const i = host.chartInfo,
        g = gesture,
        p = i.plot;
      pointers.set(id, pos);
      const ps = [...pointers.values()];
      if (!g) return false;
      let next;
      if (ps.length > 1 && g.distance > 0) {
        const mid = (ps[0].x + ps[1].x) / 2;
        const distance = Math.hypot(ps[1].x - ps[0].x, ps[1].y - ps[0].y);
        if (distance < 1) return true;
        next = zoom(
          g.view,
          i.base,
          g.distance / distance,
          clamp((g.midpoint.x - p.l) / p.pw, 0, 1),
        );
        next = pan(
          next,
          i.base,
          (-(mid - g.midpoint.x) / p.pw) * (next.xmax - next.xmin),
        );
      } else {
        const dx = pos.x - g.start.x,
          dy = pos.y - g.start.y;
        if (!g.moved && Math.hypot(dx, dy) <= 5) return false;
        if (g.touch && g.area === "plot") {
          g.direction ||=
            Math.abs(dy) > Math.abs(dx) ? "vertical" : "horizontal";
          if (g.direction === "vertical") {
            i.hide();
            return false;
          }
          if (host.chartTouchMode === "inspect") {
            i.inspect(pos);
            return true;
          }
        }
        if (g.area === "y") {
          host.chartYMode = "manual";
          next = scaleY(
            g.view,
            i.base,
            Math.exp(clamp((dy / p.ph) * 2, -10, 10)),
          );
        } else if (g.area === "x")
          next = zoom(
            g.view,
            i.base,
            Math.exp(clamp((dx / p.pw) * 3, -10, 10)),
            1,
          );
        else {
          next = pan(
            g.view,
            i.base,
            (-dx / p.pw) * (g.view.xmax - g.view.xmin),
          );
          if (host.chartYMode === "manual")
            next = panY(next, (dy / p.ph) * (g.view.ymax - g.view.ymin));
        }
      }
      host.chartViewport = next;
      g.moved = suppressClick = true;
      i.hide();
      draw();
      return true;
    };
    const end = (id) => {
      pointers.delete(id);
      if (pointers.size) startGesture(gesture?.area || "plot", gesture?.touch);
      else {
        gesture = null;
        host.chartTouchTargets?.clear();
      }
    };
    host.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || !event.target.closest(".chart-svg")) return;
      if (!host.chartInfo.plot) {
        host.chartInfo.direct(event);
        return;
      }
      if (event.pointerType === "touch") {
        if (!pointers.size) {
          host.querySelector(".chart-touch-targets")?.replaceChildren();
          host.chartTouchTargets = new Set();
        }
        host.chartTouchTargets.add(event.target);
      }
      suppressClick = false;
      if (
        down(
          event.pointerId,
          local(event.clientX, event.clientY),
          event.pointerType === "touch",
        )
      ) {
        if (event.pointerType !== "touch") event.preventDefault();
        host.querySelector(".chart-svg").setPointerCapture(event.pointerId);
      }
    });
    host.addEventListener("pointermove", (event) => {
      if (event.target.closest(".chart-tooltip")) return;
      const i = host.chartInfo;
      if (!i.plot) {
        i.direct(event);
        return;
      }
      const pos = local(event.clientX, event.clientY);
      if (pointers.has(event.pointerId)) move(event.pointerId, pos);
      else if (event.pointerType !== "touch") {
        const area = region(pos);
        host.querySelector(".chart-svg").style.cursor =
          area === "y" ? "ns-resize" : area === "x" ? "ew-resize" : "grab";
        if (area === "plot") {
          hover = pos;
          i.inspect(pos);
        } else {
          hover = null;
          i.hide();
        }
      }
    });
    const endPointer = (event) => {
      end(event.pointerId);
      const svg = host.querySelector(".chart-svg");
      if (svg?.hasPointerCapture(event.pointerId))
        svg.releasePointerCapture(event.pointerId);
    };
    host.addEventListener("pointerup", endPointer);
    host.addEventListener("pointercancel", (event) => {
      endPointer(event);
      host.chartInfo.hide();
    });
    host.addEventListener("lostpointercapture", (event) => {
      if (pointers.has(event.pointerId)) end(event.pointerId);
    });
    host.addEventListener("pointerleave", () => {
      hover = null;
      if (!pointers.size) host.chartInfo.hide();
    });
    // Pointer events own gesture state. Cancel native touch movement only after
    // horizontal intent (or two fingers), so vertical swipes can scroll the page.
    host.addEventListener(
      "touchstart",
      (event) => {
        if (gesture?.touch && pointers.size > 1 && event.cancelable)
          event.preventDefault();
      },
      { passive: false },
    );
    host.addEventListener(
      "touchmove",
      (event) => {
        if (!gesture?.touch || !host.chartInfo.plot) return;
        if (
          event.cancelable &&
          (pointers.size > 1 ||
            gesture.area !== "plot" ||
            gesture.direction === "horizontal")
        )
          event.preventDefault();
      },
      { passive: false },
    );
    host.addEventListener(
      "wheel",
      (event) => {
        if (!host.chartInfo.plot || !event.target.closest(".chart-svg")) return;
        const pos = local(event.clientX, event.clientY),
          p = host.chartInfo.plot;
        if (region(pos) !== "plot") return;
        event.preventDefault();
        hover = pos;
        const units =
          event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? p.ph : 1;
        changeZoom(
          Math.exp(clamp(event.deltaY * units * 0.002, -1, 1)),
          (pos.x - p.l) / p.pw,
        );
      },
      { passive: false },
    );
    const reset = (all = false, y = false) => {
      const i = host.chartInfo,
        v = current();
      if (y || all) host.chartYMode = "auto";
      host.chartViewport = all
        ? null
        : y
          ? { ...v }
          : { ...v, xmin: i.base.xmin, xmax: i.base.xmax };
      hover = null;
      i.hide();
      draw();
    };
    host.addEventListener("dblclick", (event) => {
      if (!event.target.closest(".chart-svg") || !host.chartInfo.plot) return;
      const area = region(local(event.clientX, event.clientY));
      if (area === "y") reset(false, true);
      else if (area === "plot" || area === "x") reset();
    });
    host.addEventListener("click", (event) => {
      const button = event.target.closest("[data-chart-action]"),
        legend = event.target.closest("[data-legend]");
      if (button) {
        const action = button.dataset.chartAction;
        host.chartRestoreFocus = action;
        if (action === "reset") reset(true);
        else if (action === "auto-y") {
          if (host.chartYMode === "manual") reset(false, true);
          else {
            host.chartViewport = { ...current() };
            host.chartYMode = "manual";
            hover = null;
            host.chartInfo.hide();
            draw();
          }
        } else if (action === "in" || action === "out")
          changeZoom(action === "in" ? 0.7 : 1 / 0.7);
        else {
          host.chartTouchMode = action;
          draw();
        }
      } else if (legend) host.chartInfo.legend(legend.dataset.legend);
      else if (!suppressClick) host.chartInfo.direct(event);
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
        if (event.key === "0" || event.key === "Home") reset(true);
        else changeZoom(event.key === "-" ? 1 / 0.7 : 0.7);
      } else if (
        event.shiftKey &&
        ["ArrowLeft", "ArrowRight"].includes(event.key)
      ) {
        event.preventDefault();
        host.chartViewport = pan(
          current(),
          i.base,
          (event.key === "ArrowLeft" ? -0.1 : 0.1) *
            (current().xmax - current().xmin),
        );
        draw();
      } else if (["ArrowLeft", "ArrowRight"].includes(event.key)) {
        event.preventDefault();
        i.step(event.key === "ArrowLeft" ? -1 : 1);
      }
    });
  }
  const api = { ticks, fit, zoom, pan, panY, scaleY, bind };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.AnalysisChartInteractions = api;
})();
