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
    if (!all.some((point) => point.y != null)) {
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
    const interactive = (content, message) =>
      `<g tabindex="0" role="img" aria-label="${esc(message)}" data-tip="${esc(message)}"><title>${esc(message)}</title>${content}</g>`;
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
      const xValues = [...new Set(all.map((p) => p.x))];
      const numeric = all.every((p) => typeof p.x === "number");
      const temporal =
        !numeric &&
        all.every(
          (p) =>
            /^\d{4}-\d\d-\d\d/.test(String(p.x)) &&
            Number.isFinite(Date.parse(p.x)),
        );
      const asNumber = (value) =>
        temporal ? Date.parse(value) : Number(value);
      const histogram = panel.chart === "histogram";
      const numericAxis = (numeric || temporal) && panel.chart !== "box";
      let xmin = numericAxis
        ? Math.min(...all.map((p) => (histogram ? p.start : asNumber(p.x))))
        : 0;
      let xmax = numericAxis
        ? Math.max(...all.map((p) => (histogram ? p.end : asNumber(p.x))))
        : xValues.length - 1;
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
      const xs = (value) =>
        numericAxis
          ? M.l + ((asNumber(value) - xmin) / (xmax - xmin)) * pw
          : M.l +
            ((xValues.indexOf(value) + 0.5) / Math.max(1, xValues.length)) * pw;
      const yValues = points
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
      const ys = (value) => M.t + ph - ((value - ymin) / (ymax - ymin)) * ph;
      for (let i = 0; i <= 4; i++) {
        const y = M.t + (ph * i) / 4;
        svg += `<line x1="${M.l}" x2="${W - M.r}" y1="${y}" y2="${y}" class="grid-line"/>`;
        svg += text(
          M.l - 9,
          y + 4,
          small(ymax - ((ymax - ymin) * i) / 4),
          'text-anchor="end"',
        );
      }
      const tickCount = Math.max(2, Math.min(6, Math.floor(pw / 75)));
      if (numericAxis) {
        for (let i = 0; i < tickCount; i++) {
          const value = xmin + ((xmax - xmin) * i) / (tickCount - 1);
          const label = temporal
            ? new Date(value).toLocaleDateString("ja-JP", {
                month: "numeric",
                day: "numeric",
              })
            : small(Number(value.toFixed(2)));
          svg += text(
            M.l + (pw * i) / (tickCount - 1),
            H - M.b + 19,
            label,
            'text-anchor="middle"',
          );
        }
      } else
        xValues.forEach((value, i) => {
          if (i % Math.max(1, Math.ceil(xValues.length / tickCount)) === 0)
            svg += text(
              xs(value),
              H - M.b + 19,
              small(value),
              'text-anchor="middle"',
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
          );
        });
      } else if (panel.chart === "box") {
        const step = pw / Math.max(xValues.length, 1),
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
            `<rect x="${xs(p.start) + width * index + 1}" y="${ys(p.y)}" width="${Math.max(1, width - 2)}" height="${Math.max(0, ys(ymin) - ys(p.y))}" fill="${colorFor(p)}" fill-opacity=".8" rx="2"/>`,
            `${fmt(p.start)}〜${fmt(p.end)} · ${p.series} · ${fmt(p.y)}件`,
          );
        });
      }
      svg += "</g>";
    }
    const dataRows = all
      .slice(0, 200)
      .map(
        (p) =>
          `<tr>${panel.chart === "scatter" ? `<td>${esc(p.label)}</td>` : ""}<td>${esc(p.x)}</td><td>${esc(p.series || result.fields[p.metric])}</td><td>${esc(fmt(p.y))}</td>${panel.chart === "box" ? `<td>${fmt(p.median)}</td><td>${fmt(p.q1)} / ${fmt(p.q3)}</td>` : ""}</tr>`,
      )
      .join("");
    host.innerHTML = `<svg class="chart-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(panel.title)}。詳細な数値は下の集計データから確認できます。">${svg}</svg><p class="chart-tooltip" aria-live="polite">点や図形をタップすると数値を確認できます</p>${panel.style.legend ? `<div class="chart-legend">${legendUnique.map((item, i) => `<button type="button" data-legend="${esc(item.key)}" aria-pressed="${!hidden.has(item.key)}" style="opacity:${hidden.has(item.key) ? ".4" : "1"}"><span class="legend-swatch" style="background:${palette[i % palette.length]}"></span>${esc(item.label)}</button>`).join("")}</div>` : ""}<details class="chart-data"><summary>集計データを見る（${all.length}点）</summary><div class="table-scroll"><table><thead><tr>${panel.chart === "scatter" ? "<th>作品・計測</th>" : ""}<th>横軸</th><th>系列</th><th>値</th>${panel.chart === "box" ? "<th>中央値</th><th>Q1 / Q3</th>" : ""}</tr></thead><tbody>${dataRows}</tbody></table></div>${all.length > 200 ? "<p>最初の200点を表示。条件を絞ると詳細を確認できます。</p>" : ""}</details>`;
    const showTip = (event) => {
      const target = event.target.closest("[data-tip]");
      if (target)
        host.querySelector(".chart-tooltip").textContent = target.dataset.tip;
    };
    host.onpointerover = showTip;
    host.onclick = (event) => {
      showTip(event);
      const button = event.target.closest("[data-legend]");
      if (button) {
        hidden.has(button.dataset.legend)
          ? hidden.delete(button.dataset.legend)
          : hidden.add(button.dataset.legend);
        chart(host, panel, result);
      }
    };
    host.onfocusin = showTip;
  }
  window.AnalysisCharts = { render: chart, escape: esc, format: fmt };
})();
