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
  function chart(host, panel, result) {
    const all = result.points || [];
    const signature = JSON.stringify([
      panel.chart,
      panel.x,
      panel.y,
      panel.style,
    ]);
    if (host.chartSource !== result || host.chartSignature !== signature) {
      host.chartViewport = null;
      host.chartSource = result;
      host.chartSignature = signature;
    }
    let plot = null,
      base = null,
      view = null,
      xs = null,
      ys = null,
      xCoordinate = null;
    let temporal = false,
      numericAxis = false;
    const xValues = [...new Set(all.map((p) => p.x))];
    if (!all.some((point) => point.y != null)) {
      host.chartInfo = { plot: null, direct() {}, hide() {} };
      host.innerHTML =
        '<div class="panel-empty">この条件に一致する計測データがありません。<br>期間・計測時点・フィルターを変更してください。</div>';
      return;
    }
    const W = Math.max(280, Math.floor(host.clientWidth || 600) - 20),
      H = 245;
    const M = { l: 55, r: 22, t: 23, b: 48 },
      pw = W - M.l - M.r,
      ph = H - M.t - M.b;
    const palette = [
      panel.style.color,
      ...colors.filter((color) => color !== panel.style.color),
    ];
    const groups = [...new Set(all.map(key))];
    const names = Object.fromEntries(
      groups.map((k) => {
        const p = all.find((p) => key(p) === k);
        return [k, p.series || result.fields[p.metric] || p.metric];
      }),
    );
    const hidden = host.hiddenSeries || new Set();
    host.hiddenSeries = hidden;
    const points = all.filter(
      (p) => !hidden.has(panel.chart === "pie" ? `${p.x}|${key(p)}` : key(p)),
    );
    const legend =
      panel.chart === "pie"
        ? all.map((p) => ({
            key: `${p.x}|${key(p)}`,
            label: [p.x, p.series].filter(Boolean).join(" / "),
          }))
        : groups.map((k) => ({ key: k, label: names[k] }));
    const legendUnique = [
      ...new Map(legend.map((item) => [item.key, item])).values(),
    ];
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
      `<g tabindex="0" role="img" ${point ? `data-point-index="${all.indexOf(point)}"` : ""} aria-label="${esc(message)}" data-tip="${esc(message)}"><title>${esc(message)}</title>${content}</g>`;
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
      const numeric = all.every((p) => typeof p.x === "number");
      temporal =
        !numeric &&
        all.every(
          (p) =>
            /^\d{4}-\d\d-\d\d/.test(String(p.x)) &&
            Number.isFinite(Date.parse(p.x)),
        );
      const asNumber = (value) =>
        temporal
          ? Date.parse(
              /^\d{4}-\d\d-\d\d$/.test(String(value))
                ? value + "T00:00:00+09:00"
                : value,
            )
          : Number(value);
      const histogram = panel.chart === "histogram";
      numericAxis = (numeric || temporal) && panel.chart !== "box";
      let xmin = numericAxis
        ? Math.min(...all.map((p) => (histogram ? p.start : asNumber(p.x))))
        : -0.5;
      let xmax = numericAxis
        ? Math.max(...all.map((p) => (histogram ? p.end : asNumber(p.x))))
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
      const yValues = all
        .flatMap((p) =>
          panel.chart === "box" ? [p.low, p.high, ...p.outliers] : [p.y],
        )
        .filter((v) => v != null);
      let ymin = panel.style.y_min ?? Math.min(0, ...yValues),
        ymax = panel.style.y_max ?? Math.max(1, ...yValues) * 1.12;
      if (ymax <= ymin) {
        if (panel.style.y_max != null && panel.style.y_min == null)
          ymin = ymax - 1;
        else ymax = ymin + 1;
      }
      base = { xmin, xmax, ymin, ymax };
      view = host.chartViewport || base;
      ({ xmin, xmax, ymin, ymax } = view);
      plot = { W, H, l: M.l, t: M.t, pw, ph };
      xCoordinate = (value) =>
        numericAxis ? asNumber(value) : xValues.indexOf(value);
      xs = (value) => M.l + ((xCoordinate(value) - xmin) / (xmax - xmin)) * pw;
      ys = (value) => M.t + ph - ((value - ymin) / (ymax - ymin)) * ph;
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
          M.l + ((value - xmin) / (xmax - xmin)) * pw,
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
          const series = points.filter((p) => key(p) === k),
            color = palette[groups.indexOf(k) % palette.length];
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
          series
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
      }
      svg += '</g><g class="chart-inspection" pointer-events="none"></g>';
    }
    const dataRows = all
      .slice(0, 200)
      .map(
        (p) =>
          `<tr>${panel.chart === "scatter" ? `<td>${esc(p.label)}</td>` : ""}<td>${esc(p.x)}</td><td>${esc(p.series || result.fields[p.metric])}</td><td>${esc(fmt(p.y))}</td>${panel.chart === "box" ? `<td>${fmt(p.median)}</td><td>${fmt(p.q1)} / ${fmt(p.q3)}</td>` : ""}</tr>`,
      )
      .join("");
    const toolbar = plot
      ? `<div class="chart-toolbar"><div role="group" aria-label="タッチ操作"><button type="button" data-chart-action="pan" aria-pressed="${host.chartTouchMode !== "inspect"}">移動</button><button type="button" data-chart-action="inspect" aria-pressed="${host.chartTouchMode === "inspect"}">値を見る</button></div><div><button type="button" data-chart-action="in" aria-label="グラフを拡大">＋</button><button type="button" data-chart-action="out" aria-label="グラフを縮小">−</button><button type="button" data-chart-action="reset">表示範囲をリセット</button></div></div>`
      : "";
    host.innerHTML = `${toolbar}<div class="chart-stage"><svg class="chart-svg" tabindex="0" ${view ? `data-x-min="${view.xmin}" data-x-max="${view.xmax}" data-y-min="${view.ymin}" data-y-max="${view.ymax}"` : ""} viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(panel.title)}。詳細な数値は下の集計データから確認できます。">${svg}</svg><div class="chart-tooltip" role="status" aria-live="polite" hidden></div></div><p class="chart-gesture-help">${plot ? "ドラッグ・1本指で移動／ホイール・2本指でズーム。「値を見る」でなぞって確認。＋−でズーム、←→で値、Homeでリセット。" : "図形に指やカーソルを置くと値を確認できます。"}</p>${panel.style.legend ? `<div class="chart-legend">${legendUnique.map((item, i) => `<button type="button" data-legend="${esc(item.key)}" aria-pressed="${!hidden.has(item.key)}" style="opacity:${hidden.has(item.key) ? ".4" : "1"}"><span class="legend-swatch" style="background:${palette[i % palette.length]}"></span>${esc(item.label)}</button>`).join("")}</div>` : ""}<details class="chart-data"><summary>集計データを見る（${all.length}点）</summary><div class="table-scroll"><table><thead><tr>${panel.chart === "scatter" ? "<th>作品・計測</th>" : ""}<th>横軸</th><th>系列</th><th>値</th>${panel.chart === "box" ? "<th>中央値</th><th>Q1 / Q3</th>" : ""}</tr></thead><tbody>${dataRows}</tbody></table></div>${all.length > 200 ? "<p>最初の200点を表示。条件を絞ると詳細を確認できます。</p>" : ""}</details>`;
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
    const showPoints = (selected, px, py, heading) => {
      if (!selected.length) {
        hide();
        return;
      }
      const markup =
        `<strong class="chart-tooltip-header">${esc(heading)}</strong>` +
        selected
          .map(
            (p) =>
              `<div class="chart-tooltip-row"><span><i style="background:${colorFor(p)}"></i>${esc(panel.chart === "scatter" ? p.label + " / " + names[key(p)] : names[key(p)])}</span><strong>${panel.chart === "box" ? `中央値 ${fmt(p.median)}<br>Q1 ${fmt(p.q1)} / Q3 ${fmt(p.q3)}<br>ひげ ${fmt(p.low)}〜${fmt(p.high)} / ${p.n}件` : esc(fmt(p.y))}</strong></div>`,
          )
          .join("");
      display(markup, px, py);
      const overlay = host.querySelector(".chart-inspection");
      if (overlay)
        overlay.innerHTML =
          (panel.chart === "line"
            ? `<line class="chart-crosshair" x1="${px}" x2="${px}" y1="${M.t}" y2="${M.t + ph}"/>`
            : "") +
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
        const candidates = points.filter(visibleX);
        if (!candidates.length) {
          hide();
          return;
        }
        const nearest = candidates.reduce((a, b) =>
          Math.abs(xs(a.x) - pos.x) <= Math.abs(xs(b.x) - pos.x) ? a : b,
        );
        const selected = candidates.filter((p) => p.x === nearest.x);
        host.chartInspectionX = nearest.x;
        showPoints(selected, xs(nearest.x), pos.y, dateLabel(nearest.x));
      } else {
        if (!eligible.length) {
          hide();
          return;
        }
        const nearest = eligible.reduce((a, b) =>
          Math.hypot(xs(a.x) - pos.x, ys(a.y) - pos.y) <=
          Math.hypot(xs(b.x) - pos.x, ys(b.y) - pos.y)
            ? a
            : b,
        );
        showPoints(
          [nearest],
          xs(nearest.x),
          ys(nearest.y),
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
      redraw: () => chart(host, panel, result),
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
