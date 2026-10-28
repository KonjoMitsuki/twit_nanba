/* Small dependency-free SVG charts. Statistics are computed by the server. */
(() => {
  const esc = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (char) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[char],
    );
  const fmt = (value) =>
    value == null
      ? "未計測"
      : new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 2 }).format(
          value,
        );
  const colors = [
    "#447869",
    "#b88043",
    "#6686a5",
    "#ad6d78",
    "#8776a2",
    "#667b45",
    "#3a868c",
    "#a56a3b",
  ];
  const small = (value) =>
    typeof value === "number"
      ? Math.abs(value) >= 10000
        ? `${fmt(value / 10000)}万`
        : fmt(value)
      : /^\d{4}-\d\d-\d\d/.test(String(value))
        ? String(value).slice(5, 10).replace("-", "/")
        : String(value);
  const key = (point) => `${point.series || ""}|${point.metric || ""}`;
  function lowerBound(series, value, coordinate, inclusive = false) {
    let lo = 0,
      hi = series.length;
    while (lo < hi) {
      const mid = (lo + hi) >>> 1,
        x = coordinate(series[mid].x);
      if (x < value || (inclusive && x === value)) lo = mid + 1;
      else hi = mid;
    }
    return lo;
  }
  // Keep first/last/extreme values in each screen column. Missing values still
  // break a line; source data remains intact for tooltips and aggregation.
  function sampleLine(series, xs) {
    const output = [];
    let bucket = [],
      column;
    const flush = () => {
      if (!bucket.length) return;
      let low = bucket[0],
        high = bucket[0];
      bucket.forEach((p) => {
        if (p.y < low.y) low = p;
        if (p.y > high.y) high = p;
      });
      const keep = new Set([bucket[0], low, high, bucket[bucket.length - 1]]);
      output.push(...bucket.filter((p) => keep.has(p)));
      bucket = [];
    };
    series.forEach((p) => {
      const next = Math.floor(xs(p.x));
      if (p.y == null) {
        flush();
        output.push(p);
        column = undefined;
      } else {
        if (next !== column) flush();
        column = next;
        bucket.push(p);
      }
    });
    flush();
    return output;
  }
  function chart(host, panel, result, viewportOnly = false) {
    const all = result.points || [];
    const signature = JSON.stringify([
      panel.chart,
      panel.x,
      panel.y,
      panel.source,
      panel.transform,
      panel.series,
      panel.style.x_min,
      panel.style.x_max,
    ]);
    if (host.chartSignature !== signature) {
      host.chartViewport = null;
      host.chartYMode = "auto";
      host.chartSignature = signature;
    }
    const ySettings = JSON.stringify([panel.style.y_min, panel.style.y_max]);
    if (host.chartYSettings !== ySettings) host.chartYMode = "auto";
    host.chartYSettings = ySettings;
    host.chartYMode ||= "auto";
    const prepared =
      viewportOnly && host.chartPrepared?.all === all ? host.chartPrepared : {};
    const pointIndexes = (prepared.pointIndexes ||= new Map(
      all.map((p, i) => [p, i]),
    ));
    let plot = null,
      base = null,
      view = null,
      xs = null,
      ys = null,
      xCoordinate = null,
      lineWindows = null,
      barBox = null;
    let temporal = false,
      numericAxis = false;
    const xValues = (prepared.xValues ||= [...new Set(all.map((p) => p.x))]);
    const xIndexes = (prepared.xIndexes ||= new Map(
      xValues.map((x, i) => [x, i]),
    ));
    if (!all.some((point) => point.y != null)) {
      host.chartInfo = { plot: null, direct() {}, hide() {} };
      host.innerHTML =
        '<div class="panel-empty">この条件に一致する計測データがありません。<br>期間・計測時点・フィルターを変更してください。</div>';
      return;
    }
    const preview =
      panel.chart !== "pie" &&
      document.body.classList.contains("has-settings") &&
      innerWidth < 1024 &&
      host.closest(".panel")?.classList.contains("is-selected");
    const W = Math.max(280, Math.floor(host.clientWidth || 600) - 20),
      H = preview
        ? Math.max(
            90,
            Math.min(
              245,
              host.clientHeight -
                (innerHeight <= 480 ? 0 : 44 + (panel.style.legend ? 44 : 0)),
            ),
          )
        : 245;
    const M = { l: 55, r: 22, t: preview ? 12 : 23, b: preview ? 28 : 48 },
      pw = W - M.l - M.r,
      ph = H - M.t - M.b;
    const palette = [
      panel.style.color,
      ...colors.filter((color) => color !== panel.style.color),
    ];
    const groups = (prepared.groups ||= [...new Set(all.map(key))]);
    const names = (prepared.names ||= Object.fromEntries(
      groups.map((k) => {
        const p = all.find((p) => key(p) === k);
        return [k, p.series || result.fields[p.metric] || p.metric];
      }),
    ));
    const hidden = host.hiddenSeries || new Set();
    host.hiddenSeries = hidden;
    const points = (prepared.points ||= all.filter(
      (p) => !hidden.has(panel.chart === "pie" ? `${p.x}|${key(p)}` : key(p)),
    ));
    const legend =
      panel.chart === "pie"
        ? all.map((p) => ({
            key: `${p.x}|${key(p)}`,
            label: [p.x, p.series].filter(Boolean).join(" / "),
          }))
        : groups.map((k) => ({ key: k, label: names[k] }));
    const legendUnique = (prepared.legendUnique ||= [
      ...new Map(legend.map((item) => [item.key, item])).values(),
    ]);
    const colorFor = (p) =>
      palette[
        (panel.chart === "pie"
          ? legendUnique.findIndex((item) => item.key === `${p.x}|${key(p)}`)
          : groups.indexOf(key(p))) % palette.length
      ];
    let svg = "";
    const text = (x, y, value, attrs = "") =>
      `<text x="${x}" y="${y}" ${attrs}>${esc(value)}</text>`;
    const tip = (p) =>
      `${p.label ? p.label + " · " : ""}${p.x} · ${p.series ? p.series + " · " : ""}${result.fields[p.metric] || p.metric}: ${fmt(p.y)}${p.n ? " / " + p.n + "件" : ""}`;
    const interactive = (content, message, point) =>
      `<g tabindex="0" role="img" ${point ? `data-point-index="${pointIndexes.get(point)}"` : ""} aria-label="${esc(message)}" data-tip="${esc(message)}"><title>${esc(message)}</title>${content}</g>`;
    if (panel.chart === "pie") {
      const sum = points.reduce((s, p) => s + (p.y || 0), 0),
        r = 76,
        cx = W / 2,
        cy = 111,
        circumference = 2 * Math.PI * r;
      let offset = 0;
      if (sum <= 0)
        svg = text(
          cx,
          cy,
          "合計が0のため割合を表示できません",
          'text-anchor="middle"',
        );
      else {
        points.forEach((p) => {
          const length = (p.y / sum) * circumference;
          svg += interactive(
            `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${colorFor(p)}" stroke-width="29" stroke-dasharray="${length} ${circumference - length}" stroke-dashoffset="${-offset}" transform="rotate(-90 ${cx} ${cy})"/>`,
            `${tip(p)} / ${fmt((p.y / sum) * 100)}%`,
            p,
          );
          offset += length;
        });
        svg += text(
          cx,
          cy - 2,
          fmt(sum),
          'text-anchor="middle" style="font-size:24px;fill:var(--ink);font-family:var(--mono)"',
        );
        svg += text(
          cx,
          cy + 19,
          panel.style.y_label || result.fields[panel.y[0]],
          'text-anchor="middle"',
        );
      }
    } else {
      const numeric = (prepared.numeric ??= all.every(
        (p) => typeof p.x === "number",
      ));
      temporal = prepared.temporal ??=
        !numeric &&
        all.every(
          (p) =>
            /^\d{4}-\d\d-\d\d/.test(String(p.x)) &&
            Number.isFinite(Date.parse(p.x)),
        );
      const coordinates = (prepared.coordinates ||= new Map(
        xValues.map((value) => [
          value,
          temporal
            ? Date.parse(
                /^\d{4}-\d\d-\d\d$/.test(String(value))
                  ? value + "T00:00:00+09:00"
                  : value,
              )
            : Number(value),
        ]),
      ));
      // Histogram edges are numeric coordinates that are not among the bin centers.
      const asNumber = (value) =>
        typeof value === "number" ? value : coordinates.get(value);
      const histogram = panel.chart === "histogram";
      numericAxis =
        (numeric || temporal) && !["box", "bar"].includes(panel.chart);
      let xmin = numericAxis
        ? (prepared.xmin ??= all.reduce(
            (min, p) => Math.min(min, histogram ? p.start : asNumber(p.x)),
            Infinity,
          ))
        : -0.5;
      let xmax = numericAxis
        ? (prepared.xmax ??= all.reduce(
            (max, p) => Math.max(max, histogram ? p.end : asNumber(p.x)),
            -Infinity,
          ))
        : xValues.length - 0.5;
      if (numericAxis && !temporal) {
        xmin = panel.style.x_min ?? xmin;
        xmax = panel.style.x_max ?? xmax;
      }
      if (xmax < xmin) {
        if (panel.style.x_max != null && panel.style.x_min == null)
          xmin = xmax - 1;
        else xmax = xmin + 1;
      }
      if (xmax === xmin) {
        xmin -= 0.5;
        xmax += 0.5;
      }
      const valuesOf = (p) =>
        panel.chart === "box" ? [p.low, p.high, ...p.outliers] : [p.y];
      const limits = (values) => {
        let low = Infinity,
          high = -Infinity;
        for (const value of values)
          if (Number.isFinite(value)) {
            low = Math.min(low, value);
            high = Math.max(high, value);
          }
        return low === Infinity ? [0, 1] : [low, high];
      };
      const yValues = (prepared.yValues ||= points.flatMap(valuesOf));
      const [low, high] = (prepared.yLimits ||= limits(yValues));
      let ymin = panel.style.y_min ?? Math.min(0, low),
        ymax = panel.style.y_max ?? Math.max(1, high) * 1.12;
      if (ymax <= ymin) {
        if (panel.style.y_max != null && panel.style.y_min == null)
          ymin = ymax - 1;
        else ymax = ymin + 1;
      }
      base = { xmin, xmax, ymin, ymax };
      view = { ...(host.chartViewport || base) };
      [view.xmin, view.xmax] = AnalysisChartInteractions.fit(
        view.xmin,
        view.xmax,
        base.xmin,
        base.xmax,
      );
      xCoordinate = (value) =>
        numericAxis ? asNumber(value) : xIndexes.get(value);
      const visibleValues = [];
      // Include line values at the viewport boundaries, even between measurements.
      const seriesGroups = (prepared.seriesGroups ||= new Map(
        groups.map((k) => [
          k,
          points
            .filter((p) => key(p) === k)
            .sort((a, b) => xCoordinate(a.x) - xCoordinate(b.x)),
        ]),
      ));
      if (panel.chart === "line") {
        lineWindows = new Map();
        for (const [k, source] of seriesGroups) {
          const first = lowerBound(source, view.xmin, xCoordinate);
          const last = lowerBound(source, view.xmax, xCoordinate, true);
          const series = source.slice(
            Math.max(0, first - 1),
            Math.min(source.length, last + 1),
          );
          lineWindows.set(k, series);
          series.forEach((p, index) => {
            const x = xCoordinate(p.x);
            if (x >= view.xmin && x <= view.xmax) visibleValues.push(p.y);
            const prev = series[index - 1];
            if (prev?.y != null && p.y != null) {
              const a = xCoordinate(prev.x);
              for (const edge of [view.xmin, view.xmax])
                if (a < edge && x > edge)
                  visibleValues.push(
                    prev.y + ((p.y - prev.y) * (edge - a)) / (x - a),
                  );
            }
          });
        }
      } else
        points.forEach((p) => {
          if (xCoordinate(p.x) >= view.xmin && xCoordinate(p.x) <= view.xmax)
            visibleValues.push(...valuesOf(p));
        });
      if (host.chartYMode !== "manual") {
        const [lo, hi] = limits(visibleValues);
        // Keep categorical/statistical charts' zero baseline. Time series fit the window.
        const padding =
          hi === lo ? Math.max(Math.abs(lo) * 0.05, 1) : (hi - lo) * 0.08;
        const fitWindow = (temporal && numericAxis) || panel.chart === "line";
        view.ymin =
          panel.style.y_min ?? (fitWindow ? lo - padding : Math.min(0, lo));
        view.ymax =
          panel.style.y_max ??
          (fitWindow ? hi + padding : Math.max(1, hi) * 1.12);
        if (view.ymax <= view.ymin) {
          if (panel.style.y_max != null && panel.style.y_min == null)
            view.ymin = view.ymax - 1;
          else view.ymax = view.ymin + 1;
        }
      }
      if (host.chartViewport) host.chartViewport = view;
      ({ xmin, xmax, ymin, ymax } = view);
      plot = { W, H, l: M.l, t: M.t, pw, ph };
      xs = (value) => M.l + ((xCoordinate(value) - xmin) / (xmax - xmin)) * pw;
      ys = (value) => M.t + ph - ((value - ymin) / (ymax - ymin)) * ph;
      if (panel.chart === "bar") {
        // Bars keep a gap between categories and sit side by side per series.
        const slot = pw / Math.max(1, xmax - xmin),
          barWidth = Math.min((slot * 0.76) / Math.max(1, groups.length), 56),
          groupWidth = barWidth * Math.max(1, groups.length);
        barBox = (p) => {
          const index = Math.max(0, groups.indexOf(key(p))),
            zero = ys(0),
            value = ys(p.y),
            height = Math.abs(value - zero);
          return {
            x: xs(p.x) - groupWidth / 2 + index * barWidth + 1,
            width: Math.max(1, barWidth - 2),
            y: height < 1 ? Math.min(zero, value) - 1 : Math.min(zero, value),
            height: Math.max(1, height),
          };
        };
      }
      const intervalX =
        panel.style.x_tick_interval == null
          ? null
          : numericAxis && temporal
            ? panel.style.x_tick_interval *
              { day: 86400000, hour: 3600000, minute: 60000, second: 1000 }[
                panel.style.x_tick_unit || "day"
              ]
            : numericAxis
              ? panel.style.x_tick_interval
              : Math.max(1, Math.ceil(panel.style.x_tick_interval));
      const numberLabel = (value, step) =>
        Math.abs(value) >= 10000
          ? small(value)
          : new Intl.NumberFormat("ja-JP", {
              maximumFractionDigits: Math.min(
                12,
                Math.max(2, Math.ceil(-Math.log10(step || 1)) + 1),
              ),
            }).format(value);
      const yTicks = AnalysisChartInteractions.ticks(
        ymin,
        ymax,
        panel.style.y_tick_interval,
        preview ? Math.max(2, Math.floor(ph / 32) + 1) : 5,
      );
      yTicks.forEach((value) => {
        const y = ys(value);
        svg += `<line x1="${M.l}" x2="${W - M.r}" y1="${y}" y2="${y}" class="grid-line"/>`;
        svg += text(
          M.l - 9,
          y + 4,
          numberLabel(value, panel.style.y_tick_interval || (ymax - ymin) / 4),
          `text-anchor="end" class="y-tick" data-value="${value}"`,
        );
      });
      const tickCount = Math.max(2, Math.min(6, Math.floor(pw / 75)));
      const xTicks = numericAxis
        ? AnalysisChartInteractions.ticks(
            xmin + (temporal && intervalX ? 32400000 : 0),
            xmax + (temporal && intervalX ? 32400000 : 0),
            intervalX,
            tickCount,
          ).map((value) => value - (temporal && intervalX ? 32400000 : 0))
        : AnalysisChartInteractions.ticks(
            Math.max(0, Math.ceil(xmin)),
            Math.min(xValues.length - 1, Math.floor(xmax)),
            intervalX || Math.max(1, Math.ceil((xmax - xmin) / tickCount)),
          );
      if (!numericAxis && xTicks.length === 0 && xValues.length === 1)
        xTicks.push(0);
      xTicks.forEach((value) => {
        const label = !numericAxis
          ? small(xValues[Math.round(value)])
          : temporal
            ? new Date(value).toLocaleString("ja-JP", {
                timeZone: "Asia/Tokyo",
                month: "numeric",
                day: "numeric",
                ...(xmax - xmin < 172800000 ||
                (intervalX && intervalX < 86400000)
                  ? {
                      hour: "2-digit",
                      minute: "2-digit",
                      ...(intervalX && intervalX < 60000
                        ? { second: "2-digit" }
                        : {}),
                    }
                  : {}),
              })
            : numberLabel(value, intervalX || (xmax - xmin) / (tickCount - 1));
        svg += text(
          Math.max(
            String(label).length * 3,
            Math.min(
              W - String(label).length * 3,
              M.l + ((value - xmin) / (xmax - xmin)) * pw,
            ),
          ),
          H - M.b + 19,
          label,
          `text-anchor="middle" class="x-tick" data-value="${value}"`,
        );
      });
      svg += text(
        M.l + pw / 2,
        H - 7,
        panel.style.x_label ||
          (histogram ? result.fields[panel.y[0]] : result.fields[panel.x]),
        'text-anchor="middle"',
      );
      svg += text(
        M.l,
        M.t - 11,
        panel.style.y_label ||
          (histogram
            ? "件数"
            : panel.y.length === 1
              ? result.fields[panel.y[0]]
              : "値"),
      );
      svg += `<defs><clipPath id="clip-${esc(panel.id)}"><rect x="${M.l - 2}" y="${M.t - 2}" width="${pw + 4}" height="${ph + 4}"/></clipPath></defs><g clip-path="url(#clip-${esc(panel.id)})">`;
      if (panel.chart === "line") {
        groups.forEach((k) => {
          const color = palette[groups.indexOf(k) % palette.length];
          // Keep one neighbour on either side for continuous clipped segments.
          const windowed = lineWindows.get(k);
          const series =
            windowed.length > pw * 2 ? sampleLine(windowed, xs) : windowed;
          let path = "",
            inSegment = false;
          series.forEach((p) => {
            if (p.y == null) {
              inSegment = false;
              return;
            }
            path += `${inSegment ? "L" : "M"}${xs(p.x)},${ys(p.y)} `;
            inSegment = true;
          });
          svg += `<path d="${path}" fill="none" stroke="${color}" stroke-width="2.2"/>`;
          // Dense lines use the shared crosshair rather than thousands of SVG targets.
          (series.length > pw ? [] : series)
            .filter((p) => p.y != null)
            .forEach((p) => {
              svg += interactive(
                `<circle cx="${xs(p.x)}" cy="${ys(p.y)}" r="14" fill="transparent"/><circle cx="${xs(p.x)}" cy="${ys(p.y)}" r="3" fill="${color}" stroke="white" stroke-width="1"/>`,
                tip(p),
                p,
                p,
              );
              if (panel.style.labels)
                svg += text(
                  xs(p.x),
                  ys(p.y) - 9,
                  fmt(p.y),
                  'text-anchor="middle"',
                );
            });
        });
      } else if (panel.chart === "scatter") {
        points.forEach((p) => {
          svg += interactive(
            `<circle cx="${xs(p.x)}" cy="${ys(p.y)}" r="12" fill="transparent"/><circle class="scatter-point" cx="${xs(p.x)}" cy="${ys(p.y)}" r="5" fill="${colorFor(p)}" fill-opacity=".65" stroke="white" stroke-width="1"/>`,
            tip(p),
            p,
          );
        });
      } else if (panel.chart === "box") {
        const step = pw / (xmax - xmin),
          boxW = Math.max(
            5,
            Math.min(34, (step * 0.5) / Math.max(groups.length, 1)),
          );
        points.forEach((p) => {
          const center =
              xs(p.x) +
              (groups.indexOf(key(p)) - (groups.length - 1) / 2) * (boxW + 3),
            color = colorFor(p);
          svg += interactive(
            `<line x1="${center}" x2="${center}" y1="${ys(p.low)}" y2="${ys(p.high)}" stroke="${color}"/><path d="M${center - boxW / 3},${ys(p.low)}h${(boxW * 2) / 3} M${center - boxW / 3},${ys(p.high)}h${(boxW * 2) / 3}" stroke="${color}"/><rect x="${center - boxW / 2}" y="${ys(p.q3)}" width="${boxW}" height="${Math.max(1, ys(p.q1) - ys(p.q3))}" fill="${color}" fill-opacity=".2" stroke="${color}"/><line x1="${center - boxW / 2}" x2="${center + boxW / 2}" y1="${ys(p.median)}" y2="${ys(p.median)}" stroke="${color}" stroke-width="2"/>${p.outliers.map((v) => `<circle cx="${center}" cy="${ys(v)}" r="2" fill="${color}"/>`).join("")}`,
            `${p.x} ${p.series} · 中央値 ${fmt(p.median)} · Q1 ${fmt(p.q1)} · Q3 ${fmt(p.q3)} · ${p.n}件`,
            p,
          );
        });
      } else if (histogram) {
        points.forEach((p) => {
          const width = Math.max(
              1,
              (((p.end - p.start) / (xmax - xmin)) * pw) /
                Math.max(1, groups.length),
            ),
            index = groups.indexOf(key(p));
          svg += interactive(
            `<rect x="${xs(p.start) + width * index + 1}" y="${ys(p.y)}" width="${Math.max(1, width - 2)}" height="${Math.max(0, ys(0) - ys(p.y))}" fill="${colorFor(p)}" fill-opacity=".8" rx="2"/>`,
            `${fmt(p.start)}〜${fmt(p.end)} · ${p.series} · ${fmt(p.y)}件`,
            p,
          );
        });
      } else if (panel.chart === "bar") {
        points.forEach((p) => {
          if (p.y == null) return;
          const box = barBox(p);
          svg += interactive(
            `<rect class="bar" x="${box.x}" y="${box.y}" width="${box.width}" height="${box.height}" fill="${colorFor(p)}" fill-opacity=".82" rx="2"/>`,
            tip(p),
            p,
          );
          if (panel.style.labels)
            svg += text(
              box.x + box.width / 2,
              p.y >= 0 ? box.y - 4 : box.y + box.height + 11,
              fmt(p.y),
              'text-anchor="middle"',
            );
        });
      }
      svg += '</g><g class="chart-inspection" pointer-events="none"></g>';
    }
    host.chartPrepared = Object.assign(prepared, { all });
    const existingSVG = host.querySelector(".chart-svg");
    if (viewportOnly && existingSVG && plot) {
      // TouchEvent targets stay fixed for a gesture, even with pointer capture.
      // Keep touched shapes attached while replacing their visual layer so the
      // next touchmove still reaches the scroll/pinch arbitration listener.
      const drawing = existingSVG.querySelector(".chart-drawing");
      if (host.chartTouchTargets?.size) {
        let keeper = existingSVG.querySelector(".chart-touch-targets");
        if (!keeper) {
          keeper = document.createElementNS("http://www.w3.org/2000/svg", "g");
          keeper.setAttribute("class", "chart-touch-targets");
          keeper.setAttribute("visibility", "hidden");
          keeper.setAttribute("pointer-events", "none");
          keeper.setAttribute("aria-hidden", "true");
          existingSVG.append(keeper);
        }
        for (const target of host.chartTouchTargets)
          if (drawing.contains(target)) keeper.append(target);
      }
      existingSVG.querySelector(".chart-drawing").innerHTML = svg;
      existingSVG.setAttribute("viewBox", `0 0 ${W} ${H}`);
    } else {
      const dataRows = all
        .slice(0, 200)
        .map(
          (p) =>
            `<tr>${panel.chart === "scatter" ? `<td>${esc(p.label)}</td>` : ""}<td>${esc(p.x)}</td><td>${esc(p.series || result.fields[p.metric])}</td><td>${esc(fmt(p.y))}</td>${panel.chart === "box" ? `<td>${fmt(p.median)}</td><td>${fmt(p.q1)} / ${fmt(p.q3)}</td>` : ""}</tr>`,
        )
        .join("");
      const toolbar = plot
        ? `<div class="chart-toolbar"><div role="group" aria-label="タッチ操作"><button type="button" data-chart-action="pan" aria-pressed="${host.chartTouchMode !== "inspect"}">移動</button><button type="button" data-chart-action="inspect" aria-pressed="${host.chartTouchMode === "inspect"}">値を見る</button></div><div><button type="button" data-chart-action="in" aria-label="グラフを拡大">＋</button><button type="button" data-chart-action="out" aria-label="グラフを縮小">−</button><button type="button" data-chart-action="auto-y" title="Y軸の自動調整を切り替える。軸のダブルクリックで自動に戻す">Y自動</button><button type="button" data-chart-action="reset" aria-label="表示範囲をリセット" title="表示範囲をリセット">表示範囲をリセット</button></div></div>`
        : "";
      host.innerHTML = `${toolbar}<div class="chart-stage"><svg class="chart-svg" tabindex="0" ${view ? `data-x-min="${view.xmin}" data-x-max="${view.xmax}" data-y-min="${view.ymin}" data-y-max="${view.ymax}"` : ""} viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(panel.title)}。詳細な数値は下の集計データから確認できます。">${plot ? '<rect class="chart-hit-area" width="100%" height="100%" fill="transparent"/>' : ""}<g class="chart-drawing">${svg}</g></svg><div class="chart-tooltip" role="status" aria-live="polite" hidden></div></div><p class="chart-gesture-help">${plot ? "グラフ内スワイプで移動、ピンチでズーム。X軸は左右スワイプでXズーム。Y方向の移動・ズームとY軸スワイプはY自動オフ時のみ。ページのスクロールはグラフ外か「値を見る」で。ホイールで時間ズーム。ダブルクリック：描画域は時間リセット、Y軸は自動。←→で値を確認。" : "図形に指やカーソルを置くと値を確認できます。"}</p>${panel.style.legend ? `<div class="chart-legend">${legendUnique.map((item, i) => `<button type="button" data-legend="${esc(item.key)}" aria-pressed="${!hidden.has(item.key)}" style="opacity:${hidden.has(item.key) ? ".4" : "1"}"><span class="legend-swatch" style="background:${palette[i % palette.length]}"></span>${esc(item.label)}</button>`).join("")}</div>` : ""}<details class="chart-data"><summary>集計データを見る（${all.length}点）</summary><div class="table-scroll"><table><thead><tr>${panel.chart === "scatter" ? "<th>作品・計測</th>" : ""}<th>横軸</th><th>系列</th><th>値</th>${panel.chart === "box" ? "<th>中央値</th><th>Q1 / Q3</th>" : ""}</tr></thead><tbody>${dataRows}</tbody></table></div>${all.length > 200 ? "<p>最初の200点を表示。条件を絞ると詳細を確認できます。</p>" : ""}</details>`;
    }
    const svgElement = host.querySelector(".chart-svg");
    if (view) {
      Object.assign(svgElement.dataset, {
        xMin: view.xmin,
        xMax: view.xmax,
        yMin: view.ymin,
        yMax: view.ymax,
      });
      svgElement.dataset.yMode = host.chartYMode;
      svgElement.dataset.touchMode = host.chartTouchMode || "pan";
      for (const [action, pressed] of [
        ["auto-y", host.chartYMode !== "manual"],
        ["pan", host.chartTouchMode !== "inspect"],
        ["inspect", host.chartTouchMode === "inspect"],
      ])
        host
          .querySelector(`[data-chart-action="${action}"]`)
          ?.setAttribute("aria-pressed", String(pressed));
    }
    const tooltip = host.querySelector(".chart-tooltip"),
      stage = host.querySelector(".chart-stage");
    const hide = () => {
      tooltip.hidden = true;
      const overlay = host.querySelector(".chart-inspection");
      if (overlay) overlay.innerHTML = "";
    };
    const display = (markup, px, py) => {
      if (tooltip.innerHTML !== markup) tooltip.innerHTML = markup;
      tooltip.hidden = false;
      tooltip.classList.toggle(
        "is-scrollable",
        tooltip.scrollHeight > tooltip.clientHeight,
      );
      const box = stage.getBoundingClientRect();
      const x = (px * box.width) / W,
        y = (py * box.height) / H;
      tooltip.style.left = `${Math.max(0, Math.min(box.width - tooltip.offsetWidth, x + 14))}px`;
      tooltip.style.top = `${Math.max(0, Math.min(box.height - tooltip.offsetHeight, y - tooltip.offsetHeight - 12))}px`;
    };
    const dateLabel = (value) =>
      temporal && /^\d{4}-\d\d-\d\d$/.test(String(value))
        ? String(value)
        : temporal
          ? new Date(value).toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" })
          : String(value);
    const visibleX = (p) =>
      !view || (xCoordinate(p.x) >= view.xmin && xCoordinate(p.x) <= view.xmax);
    const eligible = points.filter(
      (p) =>
        p.y != null &&
        visibleX(p) &&
        (!view || (p.y >= view.ymin && p.y <= view.ymax)),
    );
    const comparisonLine = panel.chart === "line" && Boolean(panel.series);
    tooltip.classList.toggle("is-comparison-line", comparisonLine);
    const statisticName =
      panel.transform === "none"
        ? {
            sum: "合計",
            mean: "平均",
            median: "中央値",
            min: "最小",
            max: "最大",
            count: "件数",
          }[panel.aggregate]
        : {
            delta: "増減",
            rate: "増減率",
            moving_average: "移動平均",
          }[panel.transform];
    const artworkCard = (artwork) => {
      const urls = artwork.image_urls || [];
      let src;
      for (const candidate of urls) {
        try {
          const url = new URL(candidate, location.href);
          if (!["https:", "http:"].includes(url.protocol)) continue;
          if (url.hostname.endsWith(".twimg.com"))
            url.searchParams.set("name", "small");
          src = url.href;
          break;
        } catch {
          /* Skip an invalid image reference. */
        }
      }
      const heart =
          '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/></svg>',
        repost =
          '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 8 3-3 3 3M7 5v12h8m5-1-3 3-3-3m3 3V7H9"/></svg>';
      const measured =
        artwork.measured_at && Number.isFinite(Date.parse(artwork.measured_at))
          ? new Date(artwork.measured_at).toLocaleString("ja-JP", {
              timeZone: "Asia/Tokyo",
            })
          : "";
      return `<article class="chart-artwork-card" data-artwork-card="${esc(artwork.id)}"><div class="chart-artwork-photo">${src ? `<img src="${esc(src)}" width="100" height="132" decoding="async" referrerpolicy="no-referrer" alt="${esc(artwork.title)}の投稿画像">` : ""}<span class="chart-artwork-placeholder" ${src ? "hidden" : ""}>${src ? "読み込めません" : "画像なし"}</span>${urls.length > 1 ? `<span class="chart-artwork-image-count">${urls.length}枚</span>` : ""}</div><div class="chart-artwork-info"><strong class="chart-artwork-title">${esc(artwork.title)}</strong><div class="chart-artwork-metric" aria-label="いいね ${esc(fmt(artwork.likes))}">${heart}<span>いいね</span><strong>${esc(fmt(artwork.likes))}</strong></div><div class="chart-artwork-metric" aria-label="リポスト ${esc(fmt(artwork.retweets))}">${repost}<span>リポスト</span><strong>${esc(fmt(artwork.retweets))}</strong></div><small class="chart-artwork-stage">${esc([artwork.stage ? artwork.stage + "時点" : "", measured].filter(Boolean).join(" · "))}</small></div></article>`;
    };
    const crosshair = (px, py) => {
      if (!plot) return "";
      const value = view.ymax - ((py - M.t) / ph) * (view.ymax - view.ymin);
      const xValue = view.xmin + ((px - M.l) / pw) * (view.xmax - view.xmin);
      const xLabel = temporal
        ? new Date(xValue).toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" })
        : numericAxis
          ? fmt(xValue)
          : String(xValues[Math.round(xValue)] ?? "");
      const yLabel = new Intl.NumberFormat("ja-JP", {
        maximumFractionDigits: Math.min(
          12,
          Math.max(2, Math.ceil(-Math.log10(view.ymax - view.ymin)) + 3),
        ),
      }).format(value);
      const width = Math.min(W, Math.max(48, xLabel.length * 6.4 + 12));
      const left = Math.max(0, Math.min(W - width, px - width / 2));
      const top = Math.max(M.t, Math.min(M.t + ph - 20, py - 10));
      return `<g class="chart-crosshair"><line x1="${px}" x2="${px}" y1="${M.t}" y2="${M.t + ph}"/><line x1="${M.l}" x2="${M.l + pw}" y1="${py}" y2="${py}"/></g><g class="chart-axis-readout"><rect x="${left}" y="${M.t + ph + 2}" width="${width}" height="20" rx="3"/>${text(left + width / 2, M.t + ph + 16, xLabel, 'text-anchor="middle" class="chart-crosshair-time"')}<rect x="0" y="${top}" width="${M.l - 2}" height="20" rx="3"/>${text(M.l - 6, top + 14, yLabel, 'text-anchor="end" class="chart-crosshair-value" textLength="' + Math.min(M.l - 10, yLabel.length * 6) + '" lengthAdjust="spacingAndGlyphs"')}</g>`;
    };
    const showPoints = (selected, px, py, heading) => {
      if (!selected.length) {
        hide();
        const overlay = host.querySelector(".chart-inspection");
        if (overlay) overlay.innerHTML = crosshair(px, py);
        return;
      }
      const artworks =
        panel.show_images === false || comparisonLine
          ? []
          : [
              ...new Map(
                selected
                  .filter((p) => p.artwork)
                  .map((p) => [`${p.artwork.id}:${p.artwork.row_id}`, p.artwork]),
              ).values(),
            ];
      const headingLabel = comparisonLine
        ? `${result.fields[panel.x] || panel.x}: ${heading}${panel.y.length === 1 ? ` · ${result.fields[panel.y[0]] || panel.y[0]}${statisticName ? `（${statisticName}）` : ""}` : ""}`
        : heading;
      const markup =
        `<strong class="chart-tooltip-header">${esc(headingLabel)}</strong>` +
        artworks.map(artworkCard).join("") +
        selected
          .map(
            (p) =>
              `<div class="chart-tooltip-row"><span><i style="background:${colorFor(p)}"></i>${esc(panel.chart === "scatter" ? p.label + " / " + names[key(p)] : names[key(p)])}</span><strong>${panel.chart === "box" ? `中央値 ${fmt(p.median)}<br>Q1 ${fmt(p.q1)} / Q3 ${fmt(p.q3)}<br>ひげ ${fmt(p.low)}〜${fmt(p.high)} / ${p.n}件` : esc(fmt(p.y))}${comparisonLine && p.n != null ? `<small class="chart-tooltip-count">${esc(fmt(p.n))}件</small>` : ""}</strong></div>`,
          )
          .join("");
      display(markup, px, py);
      tooltip.querySelectorAll(".chart-artwork-photo img").forEach((img) => {
        const failed = () => {
          img.hidden = true;
          img.nextElementSibling.hidden = false;
        };
        img.onerror = failed;
        if (img.complete && !img.naturalWidth) failed();
      });
      const overlay = host.querySelector(".chart-inspection");
      if (overlay)
        overlay.innerHTML =
          crosshair(px, py) +
          selected
            .filter((p) => p.y != null && p.y >= view.ymin && p.y <= view.ymax)
            .map(
              (p) =>
                `<circle cx="${xs(p.x)}" cy="${ys(p.y)}" r="5" fill="${colorFor(p)}" stroke="white" stroke-width="2"/>`,
            )
            .join("");
    };
    const inspect = (pos) => {
      if (panel.chart === "line") {
        const targetX =
          view.xmin + ((pos.x - M.l) / pw) * (view.xmax - view.xmin);
        let nearest = null,
          distance = Infinity;
        for (const series of prepared.seriesGroups.values()) {
          const index = lowerBound(series, targetX, xCoordinate);
          for (const p of [series[index - 1], series[index]]) {
            if (!p || !visibleX(p)) continue;
            const d = Math.abs(xCoordinate(p.x) - targetX);
            if (d < distance) {
              nearest = p;
              distance = d;
            }
          }
        }
        if (!nearest) {
          showPoints([], pos.x, pos.y, "");
          return;
        }
        const selected = [];
        for (const series of prepared.seriesGroups.values()) {
          let index = lowerBound(series, xCoordinate(nearest.x), xCoordinate);
          while (index < series.length && series[index].x === nearest.x)
            selected.push(series[index++]);
        }
        host.chartInspectionX = nearest.x;
        showPoints(selected, pos.x, pos.y, dateLabel(nearest.x));
      } else {
        if (!eligible.length) {
          showPoints([], pos.x, pos.y, "");
          return;
        }
        const distance = (p) => {
          if (panel.chart !== "bar" || !barBox)
            return Math.hypot(xs(p.x) - pos.x, ys(p.y) - pos.y);
          // Hit the whole bar, not only its top edge.
          const box = barBox(p);
          return Math.hypot(
            Math.max(box.x - pos.x, 0, pos.x - box.x - box.width),
            Math.max(box.y - pos.y, 0, pos.y - box.y - box.height),
          );
        };
        const nearest = eligible.reduce((a, b) =>
          distance(a) <= distance(b) ? a : b,
        );
        showPoints(
          [nearest],
          pos.x,
          pos.y,
          panel.chart === "histogram"
            ? `${fmt(nearest.start)}〜${fmt(nearest.end)}`
            : `${result.fields[panel.x]}: ${dateLabel(nearest.x)}`,
        );
      }
    };
    const direct = (event) => {
      const target = event.target.closest("[data-tip]");
      if (!target) return;
      const box = target.getBoundingClientRect(),
        area = stage.getBoundingClientRect();
      const px = ((box.x + box.width / 2 - area.x) * W) / area.width,
        py = ((box.y + box.height / 2 - area.y) * H) / area.height;
      const point = all[Number(target.dataset.pointIndex)];
      if (plot && panel.chart !== "line" && point)
        showPoints(
          [point],
          xs(point.x),
          ys(point.y),
          panel.chart === "histogram"
            ? `${fmt(point.start)}〜${fmt(point.end)}`
            : `${result.fields[panel.x]}: ${dateLabel(point.x)}`,
        );
      else if (plot) inspect({ x: px, y: py });
      else display(esc(target.dataset.tip), px, py);
    };
    AnalysisChartInteractions.bind(host, {
      plot,
      base,
      view,
      inspect,
      hide,
      direct,
      redraw: () => chart(host, panel, result, true),
      legend: (value) => {
        hidden.has(value) ? hidden.delete(value) : hidden.add(value);
        chart(host, panel, result);
      },
      step: (direction) => {
        const values = [
          ...new Set(points.filter(visibleX).map((p) => p.x)),
        ].sort((a, b) => xCoordinate(a) - xCoordinate(b));
        if (!values.length) return;
        const current = values.indexOf(host.chartInspectionX),
          next = Math.max(
            0,
            Math.min(values.length - 1, current < 0 ? 0 : current + direction),
          );
        host.chartInspectionX = values[next];
        inspect({ x: xs(values[next]), y: M.t + ph / 2 });
      },
    });
    if (host.chartRestoreFocus) {
      const action = host.chartRestoreFocus;
      host.chartRestoreFocus = null;
      host
        .querySelector(
          action === "svg" ? ".chart-svg" : `[data-chart-action="${action}"]`,
        )
        ?.focus({ preventScroll: true });
    }
  }
  window.AnalysisCharts = { render: chart, escape: esc, format: fmt };
})();
