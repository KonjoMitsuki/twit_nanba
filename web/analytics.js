/* Personal view designer. Real data uses public named profiles; demo is synthetic. */
(() => {
  const $ = (selector) => document.querySelector(selector);
  const esc = AnalysisCharts.escape,
    fmt = AnalysisCharts.format;
  const DEMO = new URLSearchParams(location.search).get("demo") === "1";
  const characterSuggestionLimit = AnalysisCharacters.LIMIT;
  let characterSuggestionNames = [];
  let characterActiveSuggestion = -1;
  const icons = {
    chart: '<path d="M4 18V6m0 12h16M7 14l4-5 4 3 5-7"/>',
    calendar:
      '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
    unlock:
      '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 7-2.6m-3 9.6v2"/>',
    refresh: '<path d="M20 11a8 8 0 1 0-2 7M20 4v7h-7"/>',
    copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
    dashboard:
      '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    table:
      '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M3 14h18M9 4v16"/>',
    line: '<path d="M3 3v18h18M6 15l5-7 4 3 5-6"/>',
    scatter:
      '<path d="M3 3v18h18"/><circle cx="7" cy="15" r="1"/><circle cx="11" cy="9" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="19" cy="5" r="1"/>',
    pie: '<path d="M12 3v9h9A9 9 0 1 1 12 3Z"/><path d="M15 2v7h7a9 9 0 0 0-7-7Z"/>',
    box: '<path d="M3 12h18M5 8v8m14-8v8M8 7h8v10H8Zm4 0v10"/>',
    histogram:
      '<path d="M3 21h18M5 21V12h4v9m0 0V5h4v16m0 0V9h4v12m0 0V15h4v6"/>',
    bar: '<path d="M3 21h18"/><rect x="4" y="11" width="3" height="7" rx=".5"/><rect x="10.5" y="4" width="3" height="14" rx=".5"/><rect x="17" y="8" width="3" height="10" rx=".5"/>',
    settings:
      '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2" fill="white"/><circle cx="16" cy="12" r="2" fill="white"/><circle cx="10" cy="18" r="2" fill="white"/>',
    up: '<path d="m6 14 6-6 6 6"/>',
    down: '<path d="m6 10 6 6 6-6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
    check: '<path d="m5 12 4 4L20 5"/>',
    data: '<path d="M4 6c0-1.66 3.58-3 8-3s8 1.34 8 3v12c0 1.66-3.58 3-8 3s-8-1.34-8-3V6Z"/><path d="M4 12c0 1.66 3.58 3 8 3s8-1.34 8-3M4 6c0 1.66 3.58 3 8 3s8-1.34 8-3"/>',
    users:
      '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    sort: '<path d="m3 16 4 4 4-4M7 20V4m14 4-4-4-4 4m4-4v16"/>',
    filter: '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
    formula: '<path d="M7 4h10M7 20h10M6 8l4 4-4 4m6-4h6m-6 4h6"/>',
    style: '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.92 0 1.5-.74 1.5-1.5 0-.42-.16-.8-.42-1.08-.26-.28-.42-.66-.42-1.08 0-.92.75-1.67 1.67-1.67H16c3.31 0 6-2.69 6-6 0-4.97-4.48-9.83-10-8.67Z"/>',
  };
  const icon = (name) =>
    `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.chart}</svg>`;
  const hydrateIcons = (root) =>
    (root || document)
      .querySelectorAll("[data-icon]")
      .forEach((el) => (el.innerHTML = icon(el.dataset.icon)));
  hydrateIcons();
  const state = {
    user: null,
    profiles: [],
    metadata: null,
    views: [],
    view: null,
    panel: 0,
    tab: "data",
    results: new Map(),
    generation: 0,
    dirty: new Set(),
    saving: new Set(),
    savingAll: false,
    recovery: [],
    history: [],
    historyGroup: { key: null, at: 0 },
    characterRow: null,
    characterSelection: [],
    newCharacters: [],
  };
  const chartNames = {
    table: "テーブル（一覧表）",
    line: "折れ線グラフ（推移）",
    bar: "棒グラフ（比較）",
    pie: "円グラフ（構成比）",
    scatter: "散布図（相関）",
    box: "箱ひげ図（分布）",
    histogram: "ヒストグラム（度数分布）",
  };
  const sourceNames = {
    artworks: "作品データ（ステージ別）",
    snapshots: "計測ログ（時系列推移）",
    followers: "フォロワー推移",
  };
  const aggregates = {
    mean: "平均値 (mean)",
    median: "中央値 (median)",
    sum: "合計 (sum)",
    min: "最小値 (min)",
    max: "最大値 (max)",
    count: "件数・作品数 (count)",
  };
  const sourceCards = {
    artworks: {
      name: "作品を比較",
      row: "1作品 = 1行",
      use: "選んだ時点の成績を横並びで比べます",
      example: "例: 24時間後いいねランキング",
      period: "投稿日が基準",
      icon: "table",
    },
    snapshots: {
      name: "投稿後の伸びを追う",
      row: "1計測 = 1行",
      use: "5分後から48時間後までの変化を見ます",
      example: "例: キャラクター別の成長曲線",
      period: "投稿日が基準",
      icon: "line",
    },
    followers: {
      name: "フォロワーの推移",
      row: "アカウント全体で1行",
      use: "作品とは別にフォロワー数の増減を見ます",
      example: "例: 日ごとのフォロワー増",
      period: "計測日が基準",
      icon: "users",
    },
  };
  const chartCards = {
    table: {
      name: "テーブル",
      use: "作品を一覧で確認",
      icon: "table",
    },
    line: { name: "折れ線", use: "時系列の推移", icon: "line" },
    bar: { name: "棒", use: "項目を比較", icon: "bar" },
    pie: { name: "円", use: "構成比を見る", icon: "pie" },
    scatter: { name: "散布図", use: "2項目の相関", icon: "scatter" },
    box: { name: "箱ひげ図", use: "分布を比較", icon: "box" },
    histogram: {
      name: "ヒストグラム",
      use: "度数分布を見る",
      icon: "histogram",
    },
  };
  function stageLabel(name) {
    const match = /^(\d+)([mh])$/.exec(String(name || ""));
    if (!match) return name || "";
    const [, amount, unit] = match;
    return unit === "m" ? `${amount}分後` : `${amount}時間後`;
  }
  // crypto.randomUUID is unavailable outside secure contexts (plain http://IP).
  function randomHex() {
    const bytes = new Uint8Array(16);
    if (typeof crypto !== "undefined" && crypto.getRandomValues) {
      crypto.getRandomValues(bytes);
    } else {
      for (let index = 0; index < bytes.length; index += 1) {
        bytes[index] = Math.floor(Math.random() * 256);
      }
    }
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join(
      "",
    );
  }
  const id = (prefix) => {
    const uuid =
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID().replaceAll("-", "")
        : randomHex();
    return `${prefix}_${uuid.slice(0, 12)}`;
  };
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const storageKey = (suffix) =>
    `xart_analysis_${DEMO ? "demo" : "user"}_${state.user?.id}_${suffix}`;
  const getStored = (key, fallback) => {
    try {
      return JSON.parse(localStorage.getItem(key)) ?? fallback;
    } catch {
      return fallback;
    }
  };
  const store = (key, value) => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      toast(
        "ブラウザーの保存容量が不足しています。設定を保存できない場合があります",
      );
    }
  };
  function panelDefaults(overrides = {}) {
    return {
      id: id("panel"),
      title: "キャラクター別の成績",
      chart: "line",
      source: "artworks",
      stage: "24h",
      x: "character",
      y: ["likes"],
      series: "",
      aggregate: "mean",
      allocation: "full",
      period_days: 0,
      from_date: "",
      to_date: "",
      filters: [],
      filter_join: "and",
      formulas: [],
      transform: "none",
      window: 7,
      compare_previous: false,
      bins: 12,
      show_images: true,
      columns: [
        "title",
        "date",
        "character",
        "likes",
        "retweets",
        "impressions",
      ],
      table_sort: "date",
      table_desc: true,
      table_sorts: null,
      table_group: "",
      table_group_order: "asc",
      table_group_dates: "day",
      table_group_multivalue: "individual",
      table_collapsed_groups: [],
      style: {
        color: "#447869",
        legend: true,
        labels: false,
        x_tick_interval: null,
        y_tick_interval: null,
        x_tick_unit: "day",
        x_label: "",
        y_label: "",
        y_min: null,
        y_max: null,
        sort: "x_asc",
      },
      ...overrides,
    };
  }
  function templates() {
    return [
      {
        name: "作品テーブル",
        icon: "table",
        description: "作品を一覧で確認し、キャラクターを編集",
        config: {
          version: 1,
          layout: "single",
          panels: [panelDefaults({ chart: "table", title: "作品テーブル" })],
        },
      },
      {
        name: "キャラクターの勢い",
        icon: "line",
        description: "投稿後の伸びをキャラクターごとに比較",
        config: {
          version: 1,
          layout: "single",
          panels: [
            panelDefaults({
              title: "投稿後のいいね推移",
              source: "snapshots",
              x: "elapsed_hours",
              series: "character",
            }),
          ],
        },
      },
      {
        name: "分析ダッシュボード",
        icon: "dashboard",
        description: "伸び・構成・分布をひとつのページに",
        config: {
          version: 1,
          layout: "dashboard",
          panels: [
            panelDefaults({
              title: "投稿後のいいね推移",
              source: "snapshots",
              x: "elapsed_hours",
              series: "character",
            }),
            panelDefaults({ title: "キャラクター別の成績分布", chart: "box" }),
            panelDefaults({
              title: "キャラクター別の反応構成",
              chart: "pie",
              aggregate: "sum",
            }),
            panelDefaults({
              title: "24hいいねの分布",
              chart: "histogram",
              x: "likes",
            }),
          ],
        },
      },
    ];
  }
  function panelTypeTemplates() {
    return [
      {
        name: "テーブル",
        icon: "table",
        description: "作品を一覧で確認し、表示列を選ぶ",
        defaults: { chart: "table", title: "作品テーブル" },
      },
      {
        name: "折れ線",
        icon: "line",
        description: "投稿後の伸びを時系列で見る",
        defaults: {
          chart: "line",
          title: "投稿後のいいね推移",
          source: "snapshots",
          x: "elapsed_hours",
          y: ["likes"],
          series: "character",
          aggregate: "mean",
        },
      },
      {
        name: "棒グラフ",
        icon: "bar",
        description: "カテゴリごとの値を横並びで比べる",
        defaults: {
          chart: "bar",
          title: "キャラクター別のいいね",
          x: "character",
          y: ["likes"],
          aggregate: "mean",
        },
      },
      {
        name: "円",
        icon: "pie",
        description: "キャラクター別などの構成比を見る",
        defaults: {
          chart: "pie",
          title: "キャラクター別の反応構成",
          x: "character",
          y: ["likes"],
          aggregate: "sum",
        },
      },
      {
        name: "散布図",
        icon: "scatter",
        description: "2つの数値項目の関係を見る",
        defaults: {
          chart: "scatter",
          title: "いいねとインプレッション",
          x: "impressions",
          y: ["likes"],
          series: "character",
        },
      },
      {
        name: "箱ひげ図",
        icon: "box",
        description: "グループごとのばらつきを見る",
        defaults: {
          chart: "box",
          title: "キャラクター別の成績分布",
          x: "character",
          y: ["likes"],
        },
      },
      {
        name: "ヒストグラム",
        icon: "histogram",
        description: "数値の出現頻度を見る",
        defaults: {
          chart: "histogram",
          title: "24hいいねの分布",
          x: "likes",
          y: ["likes"],
          bins: 12,
        },
      },
    ];
  }
  function applySource(panel, source) {
    panel.source = source;
    panel.x =
      source === "followers"
        ? "date"
        : source === "snapshots"
          ? "elapsed_hours"
          : "character";
    panel.y = [source === "followers" ? "followers" : "likes"];
    panel.series = source === "snapshots" ? "character" : "";
    panel.filters = [];
    panel.formulas = [];
    panel.columns =
      source === "followers"
        ? ["date", "measured_at", "followers"]
        : [
            "title",
            "date",
            "character",
            "likes",
            "retweets",
            "impressions",
          ];
    panel.table_sort = "date";
    panel.table_sorts = null;
    panel.table_group = "";
    panel.table_collapsed_groups = [];
    if (panel.chart === "scatter") {
      const validX = state.metadata.sources[source].some(
        (field) =>
          field.key === panel.x && ["number", "date"].includes(field.type),
      );
      if (!validX)
        panel.x =
          source === "artworks"
            ? "impressions"
            : source === "snapshots"
              ? "elapsed_hours"
              : "date";
    }
    if (panel.chart === "histogram") panel.x = panel.y[0];
    if (panel.chart === "pie") panel.y = panel.y.slice(0, 1);
  }
  function confirmSourceChange(panel) {
    return (
      !(panel.filters?.length || panel.formulas?.length) ||
      confirm(
        "データの種類を変えると、絞り込みと計算式がリセットされます。変更しますか？",
      )
    );
  }
  function applyChart(panel, chart) {
    panel.chart = chart;
    panel.transform = "none";
    if (["pie", "table", "scatter"].includes(chart))
      panel.compare_previous = false;
    if (chart === "pie") panel.y = panel.y.slice(0, 1);
    if (chart === "scatter") {
      const validX =
        state.metadata.sources[panel.source].some(
          (field) =>
            field.key === panel.x && ["number", "date"].includes(field.type),
        ) ||
        panel.formulas.some(
          (formula) => formula.key === panel.x && formula.scope === "row",
        );
      if (!validX)
        panel.x =
          panel.source === "artworks"
            ? "impressions"
            : panel.source === "snapshots"
              ? "elapsed_hours"
              : "date";
      const numericRows = fieldOptions(panel, {
        numeric: true,
        rowOnly: true,
      });
      panel.y = panel.y.filter((key) => key in numericRows);
      if (!panel.y.length)
        panel.y = [panel.source === "followers" ? "followers" : "likes"];
      if (panel.allocation === "split") panel.allocation = "full";
    }
    if (chart === "histogram") {
      if (!panel.y.length)
        panel.y = [panel.source === "followers" ? "followers" : "likes"];
      panel.x = panel.y[0];
      panel.series = "";
    }
    if (chart === "bar") {
      const numericX = state.metadata.sources[panel.source].some(
        (field) => field.key === panel.x && field.type === "number",
      );
      if (numericX)
        panel.x =
          panel.source === "snapshots"
            ? "elapsed_hours"
            : panel.source === "followers"
              ? "date"
              : "character";
    }
  }
  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(state.user && !DEMO ? { "X-Analysis-Profile": state.user.id } : {}),
        ...options.headers,
      },
    });
    if (!response.ok) {
      let detail;
      try {
        detail = (await response.json()).detail;
      } catch {
        detail = "通信に失敗しました";
      }
      const error = new Error(
        Array.isArray(detail)
          ? detail.map((item) => item.msg).join("\n")
          : detail,
      );
      error.status = response.status;
      throw error;
    }
    return response.status === 204 ? null : response.json();
  }
  let toastTimer;
  function toast(message) {
    $("#toast").textContent = message;
    $("#toast").hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => ($("#toast").hidden = true), 4500);
  }
  function setError(message) {
    $("#page-error").textContent = message || "";
    $("#page-error").hidden = !message;
  }
  function saveStatus(message, error = false) {
    $("#save-status").textContent = message;
    $("#save-status").toggleAttribute("data-error", error);
    const settingsState = $("#settings-save-state");
    if (settingsState) {
      settingsState.textContent =
        message === "未保存"
          ? "未保存のビューがあります（「保存」で確定）"
          : message === "保存済み"
            ? "すべてのビューは保存済みです"
            : message;
      settingsState.toggleAttribute("data-error", error);
    }
  }
  function updateSaveButtons() {
    const disabled =
      !state.view || !state.dirty.size || state.savingAll || state.saving.size > 0;
    ["#save-view", "#save-settings"].forEach((selector) => {
      const button = $(selector);
      if (button) button.disabled = disabled;
    });
  }
  function updateSaveState() {
    if (!state.view) {
      saveStatus("");
      updateSaveButtons();
      return;
    }
    const saving = state.savingAll || state.saving.size > 0;
    const dirty = state.dirty.size > 0;
    saveStatus(saving ? "保存中…" : dirty ? "未保存" : "保存済み");
    updateSaveButtons();
  }
  function currentPanel() {
    return state.view?.config.panels[state.panel];
  }
  function rememberChange(key = "") {
    if (!state.view) return;
    const now = Date.now();
    const last = state.history.at(-1);
    if (
      last &&
      last.viewId === state.view.id &&
      key &&
      key === state.historyGroup.key &&
      now - state.historyGroup.at < 1200
    ) {
      state.historyGroup.at = now;
      updateUndoButton();
      return;
    }
    state.history.push({
      viewId: state.view.id,
      name: state.view.name,
      config: clone(state.view.config),
    });
    if (state.history.length > 20) state.history.shift();
    state.historyGroup = { key, at: now };
    updateUndoButton();
  }
  function updateUndoButton() {
    const button = $("#undo-settings");
    if (!button) return;
    button.disabled = !state.history.some(
      (entry) => entry.viewId === state.view?.id,
    );
  }
  function undoChange() {
    let entry;
    while ((entry = state.history.pop())) {
      if (entry.viewId === state.view?.id) break;
    }
    if (!entry || entry.viewId !== state.view?.id) {
      updateUndoButton();
      return;
    }
    state.view.name = entry.name;
    state.view.config = entry.config;
    state.panel = Math.min(state.panel, state.view.config.panels.length - 1);
    state.historyGroup = { key: null, at: 0 };
    changed({ render: false });
    renderWorkspace();
    if ($("#settings").open) renderSettings();
    updateUndoButton();
    toast("変更を元に戻しました");
  }
  function fieldLabel(panel, key) {
    return (
      state.metadata?.sources?.[panel.source]?.find(
        (field) => field.key === key,
      )?.label || key
    );
  }
  function periodLabel(panel) {
    if (panel.from_date || panel.to_date)
      return `${panel.from_date || "指定なし"}〜${panel.to_date || "指定なし"}`;
    if (panel.period_days) return `直近${panel.period_days}日`;
    return "全期間";
  }
  function describePanel(panel) {
    const parts = [periodLabel(panel)];
    parts.push(sourceCards[panel.source]?.name || sourceNames[panel.source]);
    if (panel.source === "artworks") parts.push(`${stageLabel(panel.stage)}時点`);
    else if (panel.source === "snapshots") parts.push("全ステージ");
    else parts.push("アカウント全体");
    if (panel.chart === "table") {
      parts.push(`表示列 ${panel.columns?.length || 0}項目`);
      if (panel.table_group)
        parts.push(`グループ: ${fieldLabel(panel, panel.table_group)}`);
      const sorts = AnalysisTable.sortsFor(panel);
      if (sorts.length)
        parts.push(
          `${sorts[0].desc ? "降順" : "昇順"}: ${fieldLabel(panel, sorts[0].field)}`,
        );
    } else {
      parts.push(`横軸: ${fieldLabel(panel, panel.x)}`);
      parts.push(
        `縦軸: ${(panel.y || []).map((key) => fieldLabel(panel, key)).join(" / ") || "未選択"}`,
      );
      if (panel.series)
        parts.push(`色分け: ${fieldLabel(panel, panel.series)}`);
      if (
        !["box", "histogram", "scatter"].includes(panel.chart) &&
        panel.aggregate
      )
        parts.push(
          (aggregates[panel.aggregate] || panel.aggregate).split(" (")[0],
        );
      if (panel.transform && panel.transform !== "none") {
        parts.push(
          {
            delta: "増加数",
            rate: "増加率",
            moving_average: "移動平均",
          }[panel.transform] || panel.transform,
        );
      }
    }
    parts.push(chartNames[panel.chart]?.split("（")[0] || panel.chart);
    const filterCount = (panel.filters || []).reduce(
      (total, group) => total + group.rules.length,
      0,
    );
    if (filterCount) parts.push(`絞り込み ${filterCount}件`);
    if (panel.formulas?.length) parts.push(`計算式 ${panel.formulas.length}件`);
    return parts.join(" · ");
  }
  function targetLabel(panel) {
    const data = state.results.get(panel.id)?.data;
    if (!data) return "対象を集計中…";
    const unit = panel.source === "followers" ? "計測" : "作品";
    const parts = [`対象 ${fmt(data.artwork_count)}${unit}`];
    if (data.missing_stage_count)
      parts.push(`未計測 ${fmt(data.missing_stage_count)}作品`);
    if (data.excluded_count) parts.push(`除外 ${fmt(data.excluded_count)}件`);
    if (panel.chart !== "table" && data.points?.length)
      parts.push(`${fmt(data.points.length)}点`);
    return parts.join(" · ");
  }
  function updateSettingsHeader(panel = currentPanel()) {
    if (!panel || !state.view) return;
    const context = $("#settings-context");
    if (context)
      context.innerHTML = `<span>${esc(state.view.name)}</span><span aria-hidden="true">/</span><strong>${esc(panel.title)}</strong>`;
    const summary = $("#settings-summary");
    if (summary)
      summary.innerHTML = `<p class="settings-summary-line">${esc(describePanel(panel))}</p><p class="settings-summary-target">${esc(targetLabel(panel))}</p>`;
  }
  function saveDrafts() {
    if (!state.user) return;
    store(storageKey("drafts"), [
      ...state.views.filter((v) => state.dirty.has(v.id)),
      ...state.recovery,
    ]);
  }
  function changed({ render = true } = {}) {
    if (!state.view) return;
    setError("");
    const settingsError = $("#settings-error");
    if (settingsError) {
      settingsError.hidden = true;
      settingsError.textContent = "";
    }
    state.dirty.add(state.view.id);
    saveDrafts();
    updateSaveState();
    renderViewList();
    if (render) renderPanels();
  }
  function saveChanges() {
    if (
      !state.view ||
      !state.dirty.size ||
      state.savingAll ||
      state.saving.size
    ) {
      updateSaveState();
      return;
    }
    const views = state.views.filter(
      (view) => state.dirty.has(view.id) && !state.saving.has(view.id),
    );
    state.savingAll = true;
    updateSaveState();
    (async () => {
      try {
        for (const view of views) await saveView(view);
      } finally {
        state.savingAll = false;
        updateSaveState();
      }
    })();
  }
  async function saveView(view) {
    if (!view) return;
    if (state.saving.has(view.id) || !state.dirty.has(view.id)) return;
    if (!view.name.trim()) {
      saveStatus("ビュー名を入力してください", true);
      $("#view-name").focus();
      return;
    }
    const snapshot = {
      name: view.name,
      config: clone(view.config),
      revision: view.revision,
    };
    const snapshotJson = JSON.stringify(snapshot.config);
    let saveError = null;
    let errorMessage = "";
    state.saving.add(view.id);
    updateSaveState();
    try {
      if (DEMO) {
        store(storageKey("views"), state.views);
        view.revision++;
      } else {
        const saved = await api(
          `/api/analytics/views/${encodeURIComponent(view.id)}`,
          {
            method: "PATCH",
            body: JSON.stringify(snapshot),
          },
        );
        view.revision = saved.revision;
        view.updated_at = saved.updated_at;
      }
      if (
        view.name === snapshot.name &&
        JSON.stringify(view.config) === snapshotJson
      )
        state.dirty.delete(view.id);
      setError("");
      const settingsError = $("#settings-error");
      if (settingsError) {
        settingsError.hidden = true;
        settingsError.textContent = "";
      }
    } catch (error) {
      if (error.status === 409) {
        state.recovery = state.recovery.filter((v) => v.id !== view.id);
        state.recovery.push(clone(view));
        state.dirty.delete(view.id);
        openConflict();
        saveError = "保存できませんでした · 競合を解決してください";
      } else {
        state.dirty.add(view.id);
        saveError = "未保存 · 保存を再試行してください";
      }
      errorMessage = error.message;
    } finally {
      state.saving.delete(view.id);
      saveDrafts();
      updateSaveState();
      renderViewList();
    }
    if (saveError) {
      saveStatus(saveError, true);
      setError(errorMessage);
      if ($("#settings").open) {
        $("#settings-error").hidden = false;
        $("#settings-error").textContent = errorMessage;
      }
    }
  }
  async function toggleViewLock() {
    const view = state.view;
    if (!view) return;
    if (state.savingAll || state.saving.size) {
      toast("設定を保存中です。完了後にロックを変更してください");
      return;
    }
    const locked = !view.locked;
    if (
      locked &&
      (state.dirty.has(view.id) ||
        state.recovery.some((draft) => draft.id === view.id))
    ) {
      toast("未保存の変更があります。保存・復元してからロックしてください");
      return;
    }
    const button = $("#toggle-lock");
    if (button) button.disabled = true;
    try {
      if (DEMO) {
        view.locked = locked;
        view.revision++;
        store(storageKey("views"), state.views);
      } else {
        const saved = await api(
          `/api/analytics/views/${encodeURIComponent(view.id)}/lock`,
          {
            method: "PATCH",
            body: JSON.stringify({ locked, revision: view.revision }),
          },
        );
        Object.assign(view, saved);
      }
      if (locked) {
        state.history = [];
        state.historyGroup = { key: null, at: 0 };
        updateUndoButton();
        if ($("#settings").open) $("#settings").close();
      }
      renderViewList();
      renderWorkspace();
      updateSaveState();
      toast(locked ? "ビューをロックしました" : "ビューのロックを解除しました");
    } catch (error) {
      setError(error.message);
    } finally {
      if ($("#toggle-lock")) $("#toggle-lock").disabled = false;
    }
  }
  function openConflict() {
    if (state.recovery.length) {
      $("#conflict-error").textContent = "";
      if (!$("#conflict-dialog").open) $("#conflict-dialog").showModal();
    }
  }
  async function resolveConflict(copy) {
    const draft = state.recovery[0];
    if (!draft) return;
    const buttons = $("#conflict-dialog").querySelectorAll("button");
    buttons.forEach((button) => (button.disabled = true));
    try {
      const created = copy
        ? await api("/api/analytics/views", {
            method: "POST",
            body: JSON.stringify({
              name: (draft.name + "（復元）").slice(0, 100),
              config: draft.config,
            }),
          })
        : null;
      const latest = (await api("/api/analytics/views")).views.find(
        (view) => view.id === draft.id,
      );
      state.views = state.views.filter((view) => view.id !== draft.id);
      if (latest) state.views.push(latest);
      if (created) state.views.push(created);
      state.recovery.shift();
      state.dirty.delete(draft.id);
      saveDrafts();
      $("#conflict-dialog").close();
      if ($("#settings").open) $("#settings").close();
      selectView(created?.id || latest?.id || state.views[0]?.id);
      updateSaveState();
      openConflict();
    } catch (error) {
      $("#conflict-error").textContent = error.message;
    } finally {
      buttons.forEach((button) => (button.disabled = false));
    }
  }
  $("#recover-view").onclick = () => resolveConflict(true);
  $("#use-server-view").onclick = () => resolveConflict(false);
  function renderAccount() {
    if (DEMO) {
      $("#account").innerHTML =
        `<label><span class="sr-only">デモ利用者</span><select id="demo-user"><option value="demo_a">デモユーザー A</option><option value="demo_b">デモユーザー B</option></select></label>`;
      $("#demo-user").value = state.user.id;
      $("#demo-user").onchange = (event) => {
        const selected = event.target.value;
        event.target.value = state.user.id;
        if (state.savingAll || state.saving.size) {
          toast("保存が完了してから切り替えてください");
          return;
        }
        if (state.dirty.size || state.recovery.length) {
          toast("未保存の変更があります。保存してから切り替えてください");
          return;
        }
        store("xart_demo_user", selected);
        location.reload();
      };
      return;
    }
    $("#account").innerHTML =
      `<label><span class="sr-only">利用者</span><select id="profile-user">${state.profiles.map((profile) => `<option value="${esc(profile.id)}">${esc(profile.name)}</option>`).join("")}<option value="__new__">＋ 利用者を追加</option></select></label><button id="rename-profile" class="quiet-button">名前を変更</button>`;
    $("#profile-user").value = state.user.id;
    $("#profile-user").onchange = async (event) => {
      const selected = event.target.value;
      event.target.value = state.user.id;
      if (state.savingAll || state.saving.size) {
        toast("保存が完了してから切り替えてください");
        return;
      }
      if (state.dirty.size || state.recovery.length) {
        toast("未保存の変更があります。保存してから切り替えてください");
        return;
      }
      try {
        let profileId = selected;
        if (selected === "__new__") {
          const name = prompt("利用者の名前を入力してください");
          if (!name?.trim()) return;
          profileId = (
            await api("/api/profiles", {
              method: "POST",
              body: JSON.stringify({ name: name.trim() }),
            })
          ).id;
        }
        store("xart_profile_id", profileId);
        location.reload();
      } catch (error) {
        setError(error.message);
      }
    };
    $("#rename-profile").onclick = async () => {
      const name = prompt("利用者の新しい名前", state.user.name);
      if (!name?.trim() || name.trim() === state.user.name) return;
      try {
        const profile = await api(
          `/api/profiles/${encodeURIComponent(state.user.id)}`,
          { method: "PATCH", body: JSON.stringify({ name: name.trim() }) },
        );
        state.user = profile;
        state.profiles = state.profiles.map((item) =>
          item.id === profile.id ? profile : item,
        );
        renderAccount();
        toast("利用者の名前を変更しました");
      } catch (error) {
        setError(error.message);
      }
    };
  }
  function normalizeView(view) {
    if (view) view.locked = Boolean(view.locked);
    return view;
  }
  function renderViewList() {
    $("#view-list").innerHTML = state.views
      .map((view) => {
        const locked = view.locked
            ? `<span class="view-lock-mark" title="ロック中" aria-hidden="true">${icon("lock")}</span><span class="sr-only">ロック中</span>`
            : "",
          dirty = state.dirty.has(view.id)
            ? '<span class="view-dirty" aria-hidden="true"></span><span class="sr-only">未保存</span>'
            : "";
        return `<button data-view="${esc(view.id)}" ${state.view?.id === view.id ? 'aria-current="page"' : ""} ${state.dirty.has(view.id) ? 'title="未保存の変更があります"' : ""}>${icon(view.config.layout === "dashboard" ? "dashboard" : view.config.panels[0]?.chart)}<span>${esc(view.name)}</span>${locked}${dirty}</button>`;
      })
      .join("");
    $("#view-list")
      .querySelectorAll("[data-view]")
      .forEach(
        (button) => (button.onclick = () => selectView(button.dataset.view)),
      );
  }
  function selectView(viewId) {
    state.view = state.views.find((v) => v.id === viewId) || state.views[0];
    state.panel = 0;
    state.generation++;
    state.history = [];
    state.historyGroup = { key: null, at: 0 };
    updateUndoButton();
    setError("");
    store(storageKey("active"), state.view?.id);
    renderWorkspace();
    updateSaveState();
  }
  function renderWorkspace() {
    const has = !!state.view;
    $("#analysis-content").hidden = !has;
    $("#empty-views").hidden = has;
    renderViewList();
    if (!has) return;
    const locked = Boolean(state.view.locked);
    $("#view-name").value = state.view.name;
    $("#view-name").readOnly = locked;
    $("#layout").value = state.view.config.layout;
    $("#layout").disabled = locked;
    $("#layout-label").textContent =
      state.view.config.layout === "dashboard"
        ? "ダッシュボード"
        : "単独ビュー";
    $("#view-lock-state").hidden = !locked;
    const lockButton = $("#toggle-lock");
    lockButton.innerHTML = icon(locked ? "unlock" : "lock");
    lockButton.classList.toggle("is-locked", locked);
    lockButton.setAttribute("aria-pressed", String(locked));
    lockButton.setAttribute(
      "aria-label",
      locked ? "ビューのロックを解除" : "ビューをロック",
    );
    lockButton.title = locked ? "ビューのロックを解除" : "ビューをロック";
    $("#add-panel").disabled = locked;
    $("#add-panel").title = locked
      ? "ロック中は表・グラフを追加できません"
      : "";
    $("#delete-view").disabled = locked;
    $("#delete-view").title = locked ? "ロック中はビューを削除できません" : "";
    $("#analysis-content").classList.toggle("view-locked", locked);
    renderPanels();
  }
  async function createView(index) {
    const template = templates()[index];
    let view;
    if (DEMO) {
      view = {
        id: id("view"),
        name: template.name,
        config: template.config,
        revision: 1,
        locked: false,
      };
      state.views.push(view);
      store(storageKey("views"), state.views);
    } else {
      view = await api("/api/analytics/views", {
        method: "POST",
        body: JSON.stringify({ name: template.name, config: template.config }),
      });
      state.views.push(view);
    }
    $("#create-dialog").close();
    selectView(view.id);
    updateSaveState();
  }
  function renderTemplates() {
    ["#starter-templates", "#create-templates"].forEach((selector) => {
      $(selector).innerHTML = templates()
        .map(
          (template, i) =>
            `<button class="template-button" data-template="${i}">${icon(template.icon)}<strong>${esc(template.name)}</strong><small>${esc(template.description)}</small></button>`,
        )
        .join("");
      $(selector)
        .querySelectorAll("[data-template]")
        .forEach(
          (button) =>
            (button.onclick = () =>
              createView(Number(button.dataset.template)).catch((error) =>
                setError(error.message),
              )),
        );
    });
  }
  function renderPanelTypes() {
    const host = $("#panel-types");
    if (!host) return;
    host.innerHTML = panelTypeTemplates()
      .map(
        (template, index) =>
          `<button class="template-button panel-type-button" type="button" data-panel-type="${index}">${icon(template.icon)}<strong>${esc(template.name)}</strong><small>${esc(template.description)}</small></button>`,
      )
      .join("");
    host.querySelectorAll("[data-panel-type]").forEach(
      (button) =>
        (button.onclick = () => addPanelFromType(Number(button.dataset.panelType))),
    );
  }
  function addPanelFromType(index) {
    if (!state.view) return;
    if (state.view.locked) {
      toast("ロック中のビューはパネルを追加できません");
      return;
    }
    if (state.view.config.panels.length >= 12) {
      toast("1ビューには12パネルまで追加できます");
      return;
    }
    const template = panelTypeTemplates()[index];
    if (!template) return;
    rememberChange("panels");
    state.view.config.panels.push(panelDefaults(template.defaults));
    state.panel = state.view.config.panels.length - 1;
    $("#panel-type-dialog").close();
    changed();
    openSettings(state.panel);
  }
  function renderTabs() {
    const panels = state.view.config.panels,
      single = state.view.config.layout === "single";
    $("#single-tabs").hidden = !single || panels.length < 2;
    $("#single-tabs").innerHTML = panels
      .map(
        (p, i) =>
          `<button role="tab" aria-selected="${i === state.panel}" data-panel-tab="${i}">${esc(p.title)}</button>`,
      )
      .join("");
    $("#single-tabs")
      .querySelectorAll("button")
      .forEach(
        (button) =>
          (button.onclick = () => {
            state.panel = Number(button.dataset.panelTab);
            renderPanels();
          }),
      );
  }
  function panelFilterCount(panel) {
    return (panel.filters || []).reduce(
      (total, group) => total + group.rules.length,
      0,
    );
  }
  function panelMetaText(panel) {
    const parts = [sourceNames[panel.source]];
    if (panel.source === "artworks") parts.push(`${stageLabel(panel.stage)}時点`);
    if (panel.source === "snapshots") parts.push("全ステージ");
    parts.push(
      ["table", "scatter"].includes(panel.chart)
        ? "元データ"
        : ["box", "histogram"].includes(panel.chart)
          ? "分布"
          : (aggregates[panel.aggregate] || panel.aggregate || "").split(" (")[0],
    );
    parts.push(periodLabel(panel));
    return parts.join(" · ");
  }
  function panelMetaChips(panel) {
    const chips = [];
    const filters = panelFilterCount(panel);
    if (filters) chips.push(`絞り込み ${filters}`);
    if (panel.formulas?.length) chips.push(`計算 ${panel.formulas.length}`);
    if (panel.table_group)
      chips.push(`グループ: ${fieldLabel(panel, panel.table_group)}`);
    if (panel.series && panel.chart !== "table")
      chips.push(`色分け: ${fieldLabel(panel, panel.series)}`);
    return chips
      .map((chip) => `<span class="panel-chip">${esc(chip)}</span>`)
      .join("");
  }
  function panelFootnote(panel, data) {
    return `対象 ${fmt(data.artwork_count)}${panel.source === "followers" ? "計測" : "作品"} · 未計測 ${fmt(data.missing_stage_count)}作品 · 除外 ${fmt(data.excluded_count)}件${data.warnings.length ? " / " + data.warnings.join(" ") : ""}`;
  }
  function emptyPanelHtml(panel) {
    const message =
      panel.source === "artworks"
        ? "条件に合う作品がありません。期間を広げるか、ステージ・絞り込みを見直してください。"
        : panel.source === "snapshots"
          ? "条件に合う計測ログがありません。期間を広げるか、ステージの絞り込みを見直してください。"
          : "この期間のフォロワー計測がありません。期間を広げてください。";
    const filters = panelFilterCount(panel);
    const hasPeriod = panel.period_days || panel.from_date || panel.to_date;
    const locked = Boolean(state.view?.locked);
    return `<div class="panel-empty">
      <span class="panel-empty-icon">${icon(panel.chart)}</span>
      <strong>条件に合うデータがありません</strong>
      <p>${esc(message)}</p>
      ${
        locked
          ? '<p class="panel-empty-locked">ロック中のため設定は変更できません</p>'
          : `<div class="panel-empty-actions">
        <button class="quiet-button" type="button" data-empty-settings>設定を見直す</button>
        ${hasPeriod ? '<button class="quiet-button" type="button" data-empty-period>全期間にする</button>' : ""}
        ${filters ? '<button class="quiet-button" type="button" data-empty-filters>絞り込みを解除</button>' : ""}
      </div>`
      }
      <small>${panel.source === "artworks" ? `現在のステージ: ${esc(stageLabel(panel.stage))}` : esc(sourceNames[panel.source])}</small>
    </div>`;
  }
  function renderPanels() {
    if (!state.view) return;
    const generation = ++state.generation,
      locked = Boolean(state.view.locked);
    renderTabs();
    $("#panels").classList.toggle(
      "single",
      state.view.config.layout === "single",
    );
    const all = state.view.config.panels,
      visible =
        state.view.config.layout === "single"
          ? [all[state.panel] || all[0]]
          : all;
    $("#panels").innerHTML = visible
      .map(
        (panel) =>
          `<article class="panel ${panel.chart === "table" ? "is-table" : ""} ${locked ? "is-locked" : ""}" data-panel="${esc(panel.id)}"><div class="panel-head"><div class="panel-title">${icon(panel.chart)}<h2 title="${esc(panel.title)}">${esc(panel.title)}</h2></div><div class="panel-controls"><button class="icon-button" data-move="-1" title="前へ移動" aria-label="このパネルを前へ">${icon("up")}</button><button class="icon-button" data-move="1" title="後ろへ移動" aria-label="このパネルを後ろへ">${icon("down")}</button><button class="icon-button panel-settings-button" data-settings title="表示・絞り込み・見た目を設定" aria-label="${esc(panel.title)}の設定">${icon("settings")}<span class="panel-action-label">設定</span></button><button class="icon-button danger" data-remove title="このパネルを削除" aria-label="${esc(panel.title)}を削除">${icon("close")}</button></div></div><div class="panel-meta"><span>${esc(panelMetaText(panel))}</span><span class="panel-chips">${panelMetaChips(panel)}</span></div><div class="chart-container"><div class="loading">集計中…</div></div><div class="panel-footnote"></div></article>`,
      )
      .join("");
    $("#panels")
      .querySelectorAll("[data-panel]")
      .forEach((article) => {
        const index = all.findIndex(
            (panel) => panel.id === article.dataset.panel,
          ),
          panel = all[index];
        article.querySelector("[data-settings]").onclick = () => {
          if (state.view.locked) {
            toast("ロック中のビューは設定を変更できません");
            return;
          }
          openSettings(index);
        };
        article.querySelectorAll("[data-move]").forEach(
          (button) =>
            (button.onclick = () => {
              if (state.view.locked) {
                toast("ロック中のビューは並べ替えできません");
                return;
              }
              const next = index + Number(button.dataset.move);
              if (next < 0 || next >= all.length) return;
              rememberChange("panels");
              [all[index], all[next]] = [all[next], all[index]];
              state.panel = next;
              changed();
            }),
        );
        article.querySelector("[data-settings]").disabled = locked;
        article.querySelector('[data-move="-1"]').disabled =
          locked || index === 0;
        article.querySelector('[data-move="1"]').disabled =
          locked || index === all.length - 1;
        article.querySelector("[data-remove]").onclick = () => {
          if (state.view.locked) {
            toast("ロック中のビューはパネルを削除できません");
            return;
          }
          if (all.length === 1) {
            toast("ビューには1つ以上の表・グラフが必要です");
            return;
          }
          if (!confirm("このパネルを削除しますか？")) return;
          rememberChange("panels");
          all.splice(index, 1);
          state.panel = Math.min(state.panel, all.length - 1);
          changed();
        };
        article.querySelector("[data-remove]").disabled = locked;
        loadPanel(article, panel, generation);
      });
  }
  async function loadPanel(article, panel, generation) {
    try {
      const data = await api(
        DEMO ? "/demo-api/query" : "/api/analytics/query",
        {
          method: "POST",
          body: JSON.stringify(
            DEMO
              ? { panel, characters: getStored("xart_demo_characters", {}) }
              : panel,
          ),
        },
      );
      if (generation !== state.generation || !article.isConnected) return;
      state.results.set(panel.id, { panel: clone(panel), data });
      const host = article.querySelector(".chart-container");
      const hasData =
        panel.chart === "table"
          ? (data.rows?.length || 0) > 0
          : (data.points?.length || 0) > 0;
      if (!hasData) {
        host.innerHTML = emptyPanelHtml(panel);
        host.querySelector("[data-empty-settings]")?.addEventListener(
          "click",
          () => openSettings(state.view.config.panels.indexOf(panel)),
        );
        host.querySelector("[data-empty-period]")?.addEventListener(
          "click",
          () => {
            rememberChange("period");
            panel.period_days = 0;
            panel.from_date = "";
            panel.to_date = "";
            changed();
            if ($("#settings").open) renderSettings();
          },
        );
        host.querySelector("[data-empty-filters]")?.addEventListener(
          "click",
          () => {
            rememberChange("filters");
            panel.filters = [];
            changed();
            if ($("#settings").open) renderSettings();
          },
        );
      } else if (panel.chart === "table")
        renderTable(host, panel, data);
      else AnalysisCharts.render(host, panel, data);
      article.querySelector(".panel-footnote").textContent = panelFootnote(
        panel,
        data,
      );
      if ($("#settings").open && currentPanel()?.id === panel.id)
        updateSettingsHeader(panel);
      if (article === document.querySelector("[data-panel]"))
        renderInsights(data, panel);
    } catch (error) {
      if (generation !== state.generation || !article.isConnected) return;
      article.querySelector(".chart-container").innerHTML = state.view.locked
        ? `<div class="panel-error">${esc(error.message)}<span>ロック中のため設定は変更できません</span></div>`
        : `<div class="panel-error">${esc(error.message)}<button class="quiet-button">設定を変更する</button></div>`;
      const settingsButton = article.querySelector(".panel-error button");
      if (settingsButton)
        settingsButton.onclick = () =>
          openSettings(state.view.config.panels.indexOf(panel));
    }
  }
  function renderInsights(data, panel) {
    const values = [
      [
        fmt(data.artwork_count),
        panel.source === "followers" ? "計測" : "作品",
        "対象データ",
        "選択した期間・条件に一致",
      ],
      [
        panel.source === "artworks" ? panel.stage : "全時点",
        "",
        "計測タイミング",
        panel.source === "followers"
          ? "アカウント全体の履歴"
          : "同じ条件で比較",
      ],
      [
        fmt(data.excluded_count),
        "件",
        "集計から除外",
        "未計測・計算不能はゼロにしません",
      ],
    ];
    $("#insights").innerHTML = values
      .map(
        ([value, unit, label, note]) =>
          `<div class="insight-item"><span class="insight-label">${label}</span><strong class="insight-value">${value}<small>${unit}</small></strong><span class="insight-note">${note}</span></div>`,
      )
      .join("");
  }
  function renderTable(host, panel, data, page = 0) {
    const locked = Boolean(state.view?.locked);
    const kinds = Object.fromEntries(
      state.metadata.sources[panel.source].map((field) => [
        field.key,
        field.type,
      ]),
    );
    const rows = AnalysisTable.sortRows(data.rows, panel, kinds);
    const sorts = AnalysisTable.sortsFor(panel);
    const groups = AnalysisTable.groupRows(rows, panel, kinds);
    const grouped = !!panel.table_group;
    const totalPages = Math.max(
      1,
      Math.ceil((grouped ? groups.length : rows.length) / (grouped ? 10 : 50)),
    );
    page = Math.max(0, Math.min(page, totalPages - 1));
    const columns =
      panel.source !== "followers" && panel.show_images !== false
        ? ["image", ...panel.columns]
        : panel.columns;
    host.groupPages ??= new Map();
    const cell = (row, key) => {
      if (key === "image") {
        const images = row.image_urls || [];
        let src;
        try {
          const url = new URL(images[0], location.origin);
          if (images.length && ["https:", "http:"].includes(url.protocol)) {
            if (url.hostname.endsWith(".twimg.com"))
              url.searchParams.set("name", "small");
            src = url.href;
          }
        } catch {
          /* Missing or unsupported image URLs get the placeholder. */
        }
        if (!src) return '<span class="artwork-image-empty">写真なし</span>';
        const picture = `<img src="${esc(src)}" width="88" height="88" loading="lazy" decoding="async" referrerpolicy="no-referrer" alt="${esc(row.title)}の投稿写真"><span class="artwork-image-empty" hidden>読み込めません</span>${images.length > 1 ? `<span class="artwork-image-count">${images.length}枚</span>` : ""}`;
        return DEMO
          ? `<span class="artwork-thumbnail">${picture}</span>`
          : `<a class="artwork-thumbnail" href="/artworks/${encodeURIComponent(row.artwork_id)}" aria-label="${esc(row.title)}の写真・作品詳細を見る">${picture}</a>`;
      }
      if (key === "character" && row.artwork_id)
        return `<button class="character-cell" data-artwork="${esc(row.artwork_id)}" aria-label="${esc(row.title)}のキャラクターを編集">${row.characters.length ? row.characters.map((name) => `<span class="character-chip">${esc(name)}</span>`).join("") : '<span class="missing-value">キャラを設定</span>'}</button>`;
      if (row[key] == null) return '<span class="missing-value">未計測</span>';
      if (key === "title" && row.url && !DEMO)
        return `<a href="/artworks/${encodeURIComponent(row.artwork_id)}">${esc(row[key])}</a>`;
      if (Array.isArray(row[key])) return esc(row[key].join(" / "));
      return esc(typeof row[key] === "number" ? fmt(row[key]) : row[key]);
    };
    const table = (items, rowPage = 0) =>
      `<div class="table-scroll"><table><thead><tr>${columns
        .map((key) => {
          if (key === "image") return '<th scope="col">投稿写真</th>';
          const rank = sorts.findIndex((sort) => sort.field === key),
            sort = sorts[rank];
          return `<th aria-sort="${rank === 0 ? (sort.desc ? "descending" : "ascending") : "none"}"><button data-sort="${esc(key)}" ${locked ? 'disabled title="ロック中は並べ替えを変更できません"' : ""}>${esc(data.fields[key] || key)} ${sort ? (sort.desc ? "↓" : "↑") + (sorts.length > 1 ? String(rank + 1) : "") : ""}</button></th>`;
        })
        .join("")}</tr></thead><tbody>${items
        .slice(rowPage * 50, (rowPage + 1) * 50)
        .map(
          (row) =>
            `<tr>${columns.map((key) => `<td>${cell(row, key)}</td>`).join("")}</tr>`,
        )
        .join(
          "",
        )}</tbody></table>${!items.length ? '<p class="panel-empty">条件に一致する作品がありません</p>' : ""}</div>`;
    const collapsed = new Set(panel.table_collapsed_groups || []);
    const shownGroups = groups.slice(page * 10, (page + 1) * 10);
    host.innerHTML =
      (grouped
        ? shownGroups
            .map((group) => {
              const rowPage = Math.min(
                host.groupPages.get(group.key) || 0,
                Math.max(0, Math.ceil(group.rows.length / 50) - 1),
              );
              host.groupPages.set(group.key, rowPage);
              return `<details class="table-group" data-group-key="${esc(group.key)}" ${collapsed.has(group.key) ? "" : "open"}><summary><span>${esc(group.label)}</span><span class="table-group-count">${fmt(group.rows.length)}行</span></summary>${table(group.rows, rowPage)}${group.rows.length > 50 ? `<div class="table-pagination"><span>${rowPage * 50 + 1}〜${Math.min((rowPage + 1) * 50, group.rows.length)} / ${fmt(group.rows.length)}行</span><div><button class="quiet-button" data-group-page="-1" ${rowPage === 0 ? "disabled" : ""}>前へ</button><button class="quiet-button" data-group-page="1" ${(rowPage + 1) * 50 >= group.rows.length ? "disabled" : ""}>次へ</button></div></div>` : ""}</details>`;
            })
            .join("") ||
          '<p class="panel-empty">条件に一致する作品がありません</p>'
        : table(rows, page)) +
      `<div class="table-pagination"><span>${grouped ? `${fmt(groups.length)}グループ・元データ${fmt(rows.length)}行` : `${rows.length ? `${page * 50 + 1}〜${Math.min((page + 1) * 50, rows.length)} / ` : ""}${fmt(rows.length)}行`}</span><div><button class="quiet-button" data-page="-1" ${page === 0 ? "disabled" : ""}>前へ</button><span>${page + 1} / ${totalPages}</span><button class="quiet-button" data-page="1" ${page + 1 >= totalPages ? "disabled" : ""}>次へ</button></div></div>`;
    host.querySelectorAll(".table-group").forEach((details) => {
      details.ontoggle = () => {
        if (state.view.locked) return;
        const keys = new Set(panel.table_collapsed_groups || []),
          key = details.dataset.groupKey;
        if (keys.has(key) === !details.open) return;
        if (!details.open && keys.size >= 2000) {
          details.open = true;
          toast("折りたたみ状態の保存は2,000グループまでです");
          return;
        }
        details.open ? keys.delete(key) : keys.add(key);
        panel.table_collapsed_groups = [...keys];
        changed({ render: false });
      };
    });
    host.querySelectorAll("[data-group-page]").forEach(
      (button) =>
        (button.onclick = () => {
          const key = button.closest("[data-group-key]").dataset.groupKey;
          host.groupPages.set(
            key,
            (host.groupPages.get(key) || 0) + Number(button.dataset.groupPage),
          );
          renderTable(host, panel, data, page);
        }),
    );
    host.querySelectorAll(".artwork-thumbnail img").forEach((image) => {
      const failed = () => {
        image.hidden = true;
        image.nextElementSibling.hidden = false;
      };
      image.addEventListener("error", failed, { once: true });
      if (image.complete && !image.naturalWidth) failed();
    });
    host.querySelectorAll("[data-sort]").forEach(
      (button) =>
        (button.onclick = () => {
          if (state.view.locked) return;
          const field = button.dataset.sort;
          const existing = sorts.find((sort) => sort.field === field);
          const next = {
            field,
            desc: sorts[0]?.field === field ? !existing.desc : false,
          };
          panel.table_sorts = [
            next,
            ...sorts.filter((sort) => sort.field !== field),
          ].slice(0, 5);
          panel.table_sort = field;
          panel.table_desc = next.desc;
          host.groupPages.clear();
          changed({ render: false });
          renderTable(host, panel, data);
        }),
    );
    host
      .querySelectorAll("[data-page]")
      .forEach(
        (button) =>
          (button.onclick = () =>
            renderTable(host, panel, data, page + Number(button.dataset.page))),
      );
    host
      .querySelectorAll("[data-artwork]")
      .forEach(
        (button) =>
          (button.onclick = () =>
            openCharacters(
              rows.find((row) => row.artwork_id === button.dataset.artwork),
            )),
      );
  }
  function openSettings(index) {
    if (state.view?.locked) {
      toast("ロック中のビューは設定を変更できません");
      return;
    }
    state.panel = index;
    state.tab = "data";
    renderSettings();
    const panel = currentPanel();
    updateSettingsHeader(panel);
    updateSaveState();
    updateUndoButton();
    $("#settings").showModal();
  }
  const sectionTitle = (title, help = "") =>
    `<div class="settings-section"><h3 class="settings-section-title">${esc(title)}</h3>${help ? `<p class="settings-section-desc">${esc(help)}</p>` : ""}</div>`;
  const labelField = (label, content, help = "") =>
    `<div class="settings-field"><label>${esc(label)}</label>${content}${help ? `<p class="settings-help">${esc(help)}</p>` : ""}</div>`;
  const input = (path, value, type = "text", attrs = "") =>
    `<input data-field="${esc(path)}" aria-label="${esc(path)}" type="${type}" value="${esc(value ?? "")}" ${attrs}>`;
  const select = (path, value, options) =>
    `<select data-field="${esc(path)}" aria-label="${esc(path)}">${Object.entries(
      options,
    )
      .map(
        ([key, label]) =>
          `<option value="${esc(key)}" ${key === String(value) ? "selected" : ""}>${esc(label)}</option>`,
      )
      .join("")}</select>`;
  function fieldOptions(panel, { numeric = false, rowOnly = false } = {}) {
    const options = {};
    state.metadata.sources[panel.source]
      .filter((field) => !numeric || field.type === "number")
      .forEach((field) => (options[field.key] = field.label));
    panel.formulas
      .filter((f) => !rowOnly || f.scope === "row")
      .forEach((f) => (options[f.key] = f.label));
    return options;
  }
  function sourceCardsHtml(panel) {
    return `<fieldset class="choice-cards source-cards"><legend class="sr-only">何を分析する？</legend>${Object.entries(
      sourceCards,
    )
      .map(
        ([key, item]) => `<label class="source-card ${panel.source === key ? "is-selected" : ""}">
          <input type="radio" name="panel-source" value="${esc(key)}" data-source-card ${panel.source === key ? "checked" : ""}>
          ${panel.source === key ? `<span class="choice-check" aria-hidden="true">${icon("check")}</span>` : ""}
          <span class="choice-icon">${icon(item.icon)}</span>
          <span class="choice-body">
            <strong>${esc(item.name)}</strong>
            <span class="choice-row">${esc(item.row)}</span>
            <span class="choice-use">${esc(item.use)}</span>
            <span class="choice-example">${esc(item.example)}</span>
            <span class="choice-period">${esc(item.period)}</span>
          </span>
        </label>`,
      )
      .join("")}</fieldset>`;
  }
  function chartCardsHtml(panel) {
    return `<fieldset class="choice-cards chart-cards"><legend class="sr-only">どう見せる？</legend>${Object.entries(
      chartCards,
    )
      .map(
        ([key, item]) => `<label class="chart-card ${panel.chart === key ? "is-selected" : ""}">
          <input type="radio" name="panel-chart" value="${esc(key)}" data-chart-card ${panel.chart === key ? "checked" : ""}>
          ${panel.chart === key ? `<span class="choice-check" aria-hidden="true">${icon("check")}</span>` : ""}
          <span class="choice-icon">${icon(item.icon)}</span>
          <span class="choice-body"><strong>${esc(item.name)}</strong><span class="choice-use">${esc(item.use)}</span></span>
        </label>`,
      )
      .join("")}</fieldset>`;
  }
  function organizeSettingsHtml(p) {
    const fields = fieldOptions(p, { rowOnly: true });
    p.table_sorts = AnalysisTable.sortsFor(p).map((sort) => ({ ...sort }));
    let html = sectionTitle(
      "行のグループ化",
      "指定した項目ごとに表をグループ化して表示します",
    );
    html += labelField(
      "グループ化する項目",
      select("table_group", p.table_group || "", {
        "": "グループ化しない（フラット表示）",
        ...fields,
      }),
      "キャラクターや日付などで表をカテゴリごとに折りたためるようにします。",
    );
    if (p.table_group) {
      html += labelField(
        "グループの表示順",
        select("table_group_order", p.table_group_order || "asc", {
          asc: "昇順（A→Z / 小さい順）",
          desc: "降順（Z→A / 大きい順）",
        }),
      );
      const kind = state.metadata.sources[p.source].find(
        (field) => field.key === p.table_group,
      )?.type;
      if (kind === "date")
        html += labelField(
          "日付のまとめ方",
          select("table_group_dates", p.table_group_dates || "day", {
            day: "日ごと（日単位・JST）",
            week: "週ごと（月曜開始・JST）",
            month: "月ごと（月単位・JST）",
            year: "年ごと（年単位・JST）",
            exact: "完全一致（同一日時）",
          }),
        );
      if (["character", "tags"].includes(p.table_group))
        html += labelField(
          "複数の値がある行",
          select(
            "table_group_multivalue",
            p.table_group_multivalue || "individual",
            {
              individual: "それぞれのグループに重複表示",
              combination: "組み合わせでひとまとめ",
            },
          ),
          "複数グループへの表示では同じ作品がそれぞれのグループに表示されます。元データは変更されません。",
        );
      html +=
        '<p class="settings-help">グループ見出しをタップして開閉できます。行数・合計はグループごとに自動集計され、折りたたみ状態も保存されます。</p>';
    }
    html += sectionTitle("並べ替え条件", "優先度の高い条件から順に並べ替えます");
    html +=
      '<span class="field-label" style="display:none;">並べ替え（上の条件から優先）</span>';
    html += p.table_sorts
      .map((sort, index) => {
        const choices = Object.fromEntries(
          Object.entries(fields).filter(
            ([field]) =>
              field === sort.field ||
              !p.table_sorts.some((other) => other.field === field),
          ),
        );
        return `<div class="table-sort-rule"><div class="table-sort-heading"><span class="sort-priority-badge">優先度 ${index + 1}</span><div class="sort-controls"><button class="icon-button" data-sort-move="${index},-1" aria-label="並べ替え条件${index + 1}を上へ" ${index === 0 ? "disabled" : ""}>${icon("up")}</button><button class="icon-button" data-sort-move="${index},1" aria-label="並べ替え条件${index + 1}を下へ" ${index === p.table_sorts.length - 1 ? "disabled" : ""}>${icon("down")}</button><button class="icon-button danger" data-sort-remove="${index}" aria-label="並べ替え条件${index + 1}を削除">${icon("close")}</button></div></div>${labelField(`並べ替え項目 ${index + 1}`, select(`table_sorts.${index}.field`, sort.field, choices))}<label class="toggle-label"><input type="checkbox" data-field="table_sorts.${index}.desc" ${sort.desc ? "checked" : ""}><span class="toggle-switch"></span>降順（条件${index + 1}）</label></div>`;
      })
      .join("");
    html += `<button class="quiet-button add-btn" id="add-table-sort" ${p.table_sorts.length >= Math.min(5, Object.keys(fields).length) ? "disabled" : ""}>${icon("plus")}並べ替え条件を追加</button><p class="settings-help">最大5条件まで指定できます。未設定・未計測は昇順・降順とも最後に表示されます。</p>`;
    return html;
  }
  function formulaSettingsHtml(p) {
    let html = sectionTitle(
      "カスタム指標",
      "独自の計算式で新しい数値指標を作成します",
    );
    html +=
      '<p class="settings-help">列名・四則演算・条件式と組み込み関数を使えます。ゼロ除算や欠測を含む結果は未計測として安全に処理されます。</p>';
    html += p.formulas
      .map(
        (f, i) =>
          `<div class="formula-card">
            <div class="formula-card-head">
              <span class="formula-badge">指標 ${i + 1}</span>
              <span class="formula-key">列キー: <code>${esc(f.key)}</code></span>
              <button class="icon-button danger" data-remove-formula="${i}" aria-label="この指標を削除">${icon("close")}</button>
            </div>
            ${labelField("指標の名前", input(`formulas.${i}.label`, f.label, "text", 'placeholder="例: 反応率（%）"'))}
            ${labelField(
              "計算のタイミング",
              select(`formulas.${i}.scope`, f.scope, {
                row: "行ごと（1行ずつ計算してから集計）",
                group: "集計後（グループ集計値に対して計算）",
              }),
              "「行ごと」は各投稿で計算します。「集計後」は合計いいね/合計impなどの全体比率計算に適しています。",
            )}
            ${labelField(
              "計算式",
              `<textarea data-field="formulas.${i}.expression" aria-label="計算式" maxlength="500" spellcheck="false" placeholder="例: likes / impressions * 100">${esc(f.expression)}</textarea>`,
            )}
            <div class="formula-insert-row">
              <label class="field-label" style="margin-bottom:0;">式に列を挿入</label>
              <select data-insert-formula="${i}" aria-label="式に列を挿入">
                <option value="">列を選択して式に追記…</option>
                ${Object.entries(fieldOptions(p, { numeric: true }))
                  .filter(([key]) => key !== f.key)
                  .map(([key, label]) => `<option value="${esc(key)}">${esc(label)} (${esc(key)})</option>`)
                  .join("")}
              </select>
            </div>
          </div>`,
      )
      .join("");
    html +=
      '<button class="quiet-button add-btn" id="add-formula">' +
      icon("plus") +
      '計算指標を追加</button>' +
      sectionTitle(
        "よく使う計算式テンプレート",
        "ワンクリックで便利な計算指標を追加できます",
      ) +
      '<div class="formula-examples">' +
      '<button type="button" class="formula-preset-card" data-example="rate"><strong>反応率（%）</strong><code>likes / impressions * 100</code><small>各投稿のインプレッションに対するいいねの割合</small></button>' +
      '<button type="button" class="formula-preset-card" data-example="aggregate"><strong>合計から反応率</strong><code>sum(likes) / sum(impressions) * 100</code><small>集計全体の合計いいね／合計インプレッション割合</small></button>' +
      '<button type="button" class="formula-preset-card" data-example="speed"><strong>時間あたりいいね</strong><code>likes / elapsed_hours</code><small>投稿からの経過時間（h）で割った反応ペース</small></button>' +
      "</div>" +
      '<p class="settings-help">利用可能関数: <code>sum</code>, <code>mean</code>, <code>median</code>, <code>min</code>, <code>max</code>, <code>count</code>, <code>abs</code>, <code>round</code>, <code>sqrt</code>, <code>log</code>, <code>coalesce</code><br>条件分岐例: <code>likes / impressions * 100 if impressions &gt; 0 else 0</code></p>';
    return html;
  }
  function renderSettings() {
    const p = currentPanel();
    if (!p) return;
    $("#settings-title").textContent = p.title;
    const badge = $("#settings-type-badge");
    if (badge) {
      badge.innerHTML = `${icon(p.chart)}<span>${esc((chartNames[p.chart] || p.chart).split("（")[0])}</span>`;
    }
    updateSettingsHeader(p);
    $("#settings-error").hidden = true;
    document
      .querySelectorAll("[data-tab]")
      .forEach((button) =>
        button.setAttribute(
          "aria-pressed",
          String(button.dataset.tab === state.tab),
        ),
      );
    let html = "";
    if (state.tab === "data") {
      html =
        sectionTitle(
          "何を分析する？",
          "同じ「いいね」でも、データの種類によって1行の意味が変わります。",
        ) +
        sourceCardsHtml(p) +
        (p.source === "artworks"
          ? labelField(
              "投稿からどの時点？",
              select(
                "stage",
                p.stage,
                Object.fromEntries(
                  state.metadata.stages.map((s) => [
                    s.name,
                    stageLabel(s.name),
                  ]),
                ),
              ),
              "選んだ時点の計測がある作品だけを集計します。未計測は0ではなく除外されます。",
            )
          : `<p class="settings-help source-note">${
              p.source === "snapshots"
                ? "すべての計測ステージを対象にします。特定の時点だけ見る場合は「絞り込み」でステージを指定してください。"
                : "アカウント全体のフォロワー計測を対象にします。作品ごとの反応とは分けて表示されます。"
            }</p>`) +
        sectionTitle(
          "いつのデータ？",
          "作品データと計測ログは投稿日、フォロワーは計測日が基準です。",
        ) +
        labelField(
          "直近の日数（0＝全期間）",
          input("period_days", p.period_days, "number", 'min="0" max="3660"') +
            `<div class="period-pills">
              <button type="button" class="pill-btn" data-preset-days="0">全期間</button>
              <button type="button" class="pill-btn" data-preset-days="7">直近7日</button>
              <button type="button" class="pill-btn" data-preset-days="30">直近30日</button>
              <button type="button" class="pill-btn" data-preset-days="90">直近90日</button>
              <button type="button" class="pill-btn" data-preset-days="365">直近1年</button>
            </div>`,
          "直近の指定日数でデータを絞り込みます（0で全期間）。",
        ) +
        `<div class="field-grid">${labelField("開始日", input("from_date", p.from_date, "date"))}${labelField("終了日", input("to_date", p.to_date, "date"))}</div>` +
        `<p class="settings-help">開始日・終了日を指定した場合、日数指定より日付範囲が優先されます。</p>` +
        sectionTitle(
          "どう見せる？",
          "表示形式を選ぶと、「表示」タブで軸や集計を設定できます。",
        ) +
        chartCardsHtml(p) +
        (!["table", "pie", "scatter"].includes(p.chart)
          ? `<label class="toggle-label"><input type="checkbox" data-field="compare_previous" ${p.compare_previous ? "checked" : ""}><span class="toggle-switch"></span>前の同じ長さの期間と比較</label><p class="settings-help">直前の同じ長さの期間データを薄い線で重ねて比較します。</p>`
          : "") +
        sectionTitle("パネルの名前", "一覧やタブに表示される名前です") +
        labelField(
          "パネル名",
          input("title", p.title, "text", 'maxlength="120" placeholder="パネル名を入力"'),
        );
    } else if (state.tab === "axes") {
      const all = fieldOptions(p, { rowOnly: true }),
        numbers = fieldOptions(p, { numeric: true });
      if (p.chart === "table") {
        const selectedCols = p.columns || [];
        html =
          sectionTitle("表示列の選択", "表に表示するデータ項目を選択します") +
          `<div class="check-actions-bar">
            <span class="selection-count">${selectedCols.length}項目 選択中</span>
            <div class="check-actions-btns">
              <button type="button" class="mini-btn" id="check-all-cols">全選択</button>
              <button type="button" class="mini-btn" id="check-none-cols">全解除</button>
              <button type="button" class="mini-btn" id="check-default-cols">標準列</button>
            </div>
          </div>
          <span class="field-label" style="display:none;">表示する列</span>
          <div class="check-options">${Object.entries(all)
            .map(([key, label]) => {
              const checked = p.columns.includes(key);
              return `<label class="check-card ${checked ? "is-checked" : ""}"><input type="checkbox" data-column="${key}" ${checked ? "checked" : ""}><span>${esc(label)}</span></label>`;
            })
            .join("")}</div>
          <p class="settings-help">表の見出しをタップすると昇順・降順に並べ替えできます。キャラクター名は直接編集可能です。</p>`;
        if (p.source !== "followers") {
          html +=
            sectionTitle("表示オプション", "表の見た目と写真の表示") +
            `<label class="toggle-label"><input type="checkbox" data-field="show_images" ${p.show_images !== false ? "checked" : ""}><span class="toggle-switch"></span>投稿写真を表示</label><p class="settings-help">投稿画像のサムネイルを表示します。タップすると作品詳細を開きます。</p>`;
        }
        html += organizeSettingsHtml(p);
      } else {
        html = sectionTitle("軸の設定", "グラフの横軸・縦軸の項目を設定します");
        if (p.chart !== "histogram") {
          html += labelField(
            "横軸・分類",
            select(
              "x",
              p.x,
              p.chart === "scatter"
                ? Object.fromEntries(
                    Object.entries(all).filter(
                      ([key]) =>
                        state.metadata.sources[p.source].some(
                          (field) =>
                            field.key === key &&
                            ["number", "date"].includes(field.type),
                        ) ||
                        p.formulas.some(
                          (f) => f.key === key && f.scope === "row",
                        ),
                    ),
                  )
                : all,
            ),
            "横軸（X軸）に配置する項目を選択します（日付、キャラクター、経過時間など）。",
          );
        }
        const selectedY = p.y || [];
        const isHist = p.chart === "histogram";
        html += sectionTitle(
          isHist ? "集計対象の数値" : "集計指標の選択",
          isHist ? "度数分布を見る数値項目" : "縦軸に集計・プロットする数値指標",
        );
        html += `<div class="settings-field">
          <div class="check-actions-bar">
            <span class="field-label" style="margin-bottom:0;">${isHist ? "分布を見る数値" : "縦軸・数値"}</span>
            <div class="check-actions-btns">
              <span class="selection-count">${selectedY.length}項目 選択中</span>
              ${!["scatter", "pie", "histogram"].includes(p.chart) ? `
                <button type="button" class="mini-btn" id="check-all-y">全選択</button>
                <button type="button" class="mini-btn" id="check-none-y">解除</button>
              ` : ""}
            </div>
          </div>
          <div class="check-options">${Object.entries(
            p.chart === "scatter"
              ? fieldOptions(p, { numeric: true, rowOnly: true })
              : numbers,
          )
            .map(([key, label]) => {
              const checked = p.y.includes(key);
              return `<label class="check-card ${checked ? "is-checked" : ""}"><input type="checkbox" data-y="${key}" ${checked ? "checked" : ""}><span>${esc(label)}</span></label>`;
            })
            .join("")}</div></div>`;

        html += sectionTitle("系列と集計", "色分け・集計方法の指定");
        html += labelField(
          "系列・色分け",
          select("series", p.series, { "": "色分けなし（単一系列）", ...all }),
          "キャラクターやタグごとに色分けして凡例を表示します。",
        );
        if (!["box", "histogram", "scatter"].includes(p.chart)) {
          html += labelField(
            "集計方法",
            select("aggregate", p.aggregate, aggregates),
            "複数データが存在する場合の計算方法です。",
          );
        }
        if (p.aggregate === "sum" && p.source === "snapshots")
          html +=
            '<p class="settings-warning">計測ログの「合計」は同じ作品を複数回足すため、通常は使えません。平均値か中央値を使ってください。</p>';
        if (p.aggregate === "sum" && p.source === "followers")
          html +=
            '<p class="settings-warning">フォロワー数はその時点の人数です。合計せず、折れ線か増加数で確認してください。</p>';
        if (p.chart === "histogram") {
          html += labelField(
            "ビン数",
            input("bins", p.bins, "number", 'min="2" max="80"'),
            "分布を区切る区間（棒）の数です（2〜80）。",
          );
        }
        if (p.chart === "line") {
          html +=
            labelField(
              "集計後の計算",
              select("transform", p.transform, {
                none: "そのまま（累積値）",
                delta: "前の観測点からの増加数（差分）",
                rate: "前の観測点からの増加率（%）",
                moving_average: "移動平均（平滑化）",
              }),
              "折れ線グラフの変化量やトレンドを見やすく加工します。",
            ) +
            (p.transform === "moving_average"
              ? labelField(
                  "移動平均の観測点数",
                  input("window", p.window, "number", 'min="2" max="100"'),
                  "平滑化に用いる直近の観測点数（ウィンドウ幅）です。",
                )
              : "");
        }
      }
      if (p.chart === "scatter") {
        html +=
          '<p class="settings-help">※ 散布図は1行を1点としてプロットします。座標が未計測の点は除外されます。</p>';
      }
      if (p.chart === "scatter" && p.source !== "followers") {
        html += sectionTitle("複数キャラの扱い", "1作品に複数キャラがある場合の表示");
        html += labelField(
          "複数キャラの表示",
          select(
            "allocation",
            p.allocation === "combination" ? "combination" : "full",
            {
              full: "各キャラの系列に表示（重複プロット）",
              combination: "組み合わせで色分け（共演別）",
            },
          ),
          "座標は元の値を使用します。キャラ数による数値配分はしません。",
        );
      } else if (p.source !== "followers") {
        html += sectionTitle("複数キャラの扱い", "1作品に複数キャラが紐付いている場合の集計基準");
        html += labelField(
          "複数キャラの数え方",
          select("allocation", p.allocation, {
            full: "各キャラに全量計上（重複カウント）",
            split: "キャラ数で均等配分（合計値を分割）",
            combination: "組み合わせごとに集計（共演別）",
          }),
          "均等配分では件数や合計値をキャラ数で分割し、平均・中央値には同じ重みを使用します。",
        );
      }
    } else if (state.tab === "filters") {
      html = sectionTitle("条件の結合ルール", "複数グループがある場合の結合ルールを設定します");
      html += labelField(
        "グループ同士の条件",
        select("filter_join", p.filter_join, {
          and: "すべての条件グループを満たす（AND）",
          or: "いずれかの条件グループを満たす（OR）",
        }),
      );
      html += sectionTitle("フィルター条件グループ", "条件を指定してデータを絞り込みます");
      html += p.filters
        .map(
          (group, gi) =>
            `<div class="filter-group">
              <div class="filter-group-head">
                <span class="filter-group-label">グループ ${gi + 1}</span>
                <div class="filter-group-join-wrap">
                  ${select(`filters.${gi}.join`, group.join, { and: "すべて一致（AND）", or: "いずれか一致（OR）" })}
                </div>
                <button class="icon-button danger" data-remove-group="${gi}" aria-label="条件グループを削除">${icon("close")}</button>
              </div>
              <div class="filter-rules-list">
                ${group.rules.map((rule, ri) => `
                  <div class="filter-rule">
                    <div class="filter-rule-field">
                      ${select(`filters.${gi}.rules.${ri}.field`, rule.field, fieldOptions(p, { rowOnly: true }))}
                    </div>
                    <div class="filter-rule-op">
                      ${select(`filters.${gi}.rules.${ri}.op`, rule.op, {
                        eq: "= 等しい",
                        ne: "≠ 異なる",
                        contains: "含む",
                        gt: "> より大きい",
                        gte: "≥ 以上",
                        lt: "< より小さい",
                        lte: "≤ 以下",
                        empty: "未設定・空",
                      })}
                    </div>
                    <div class="filter-rule-val">
                      ${input(`filters.${gi}.rules.${ri}.value`, rule.value, "text", 'placeholder="値を入力…"')}
                    </div>
                    <button class="icon-button danger filter-rule-del" data-remove-rule="${gi},${ri}" aria-label="この条件を削除">${icon("close")}</button>
                  </div>
                `).join("")}
              </div>
              <button class="quiet-button add-btn" data-add-rule="${gi}">${icon("plus")}条件を追加</button>
            </div>`,
        )
        .join("");
      html +=
        '<button class="quiet-button add-btn" id="add-filter-group">' +
        icon("plus") +
        "条件グループを追加</button>";
    } else if (state.tab === "advanced") {
      html = formulaSettingsHtml(p);
    } else if (p.chart === "table") {
      html =
        sectionTitle(
          "テーブルの詳細設定",
          "列・グループ・絞り込み・計算式は各タブで設定します",
        ) +
        '<div class="style-shortcuts">' +
          '<button type="button" class="style-shortcut-card" data-switch-tab="axes"><span class="shortcut-icon">' + icon("table") + '</span><div><strong>表示列とグループ</strong><small>列の選択・グループ化・並べ替え</small></div></button>' +
          '<button type="button" class="style-shortcut-card" data-switch-tab="filters"><span class="shortcut-icon">' + icon("filter") + '</span><div><strong>絞り込みフィルター</strong><small>特定キャラや期間の絞り込み</small></div></button>' +
          '<button type="button" class="style-shortcut-card" data-switch-tab="advanced"><span class="shortcut-icon">' + icon("formula") + '</span><div><strong>カスタム計算式</strong><small>反応率などの独自指標</small></div></button>' +
        '</div>';
    } else {
      const palette = ["#447869", "#20221e", "#f2785d", "#3b82f6", "#8b5cf6", "#eab308", "#ec4899"];
      html =
        sectionTitle("カラーとラベル", "グラフの色調と軸見出しの設定") +
        labelField(
          "メインカラー",
          `<div class="color-picker-row">${input("style.color", p.style.color || "#447869", "color")}<div class="palette-swatches">${palette.map((c) => `<button type="button" class="swatch-btn ${p.style.color === c ? "is-selected" : ""}" data-color-swatch="${c}" style="background-color:${c};" aria-label="カラー ${c}"></button>`).join("")}</div></div>`,
          "グラフの主線や棒の色を設定します。パレットから素早く選べます。",
        ) +
        labelField("横軸ラベル", input("style.x_label", p.style.x_label, "text", 'placeholder="自動（未設定）"')) +
        labelField("縦軸ラベル", input("style.y_label", p.style.y_label, "text", 'placeholder="自動（未設定）"')) +
        sectionTitle("軸の範囲（スケール）", "数値軸の表示範囲を固定する場合に指定します") +
        (p.chart === "bar"
          ? '<p class="settings-help">棒グラフの横軸は分類軸のため、横軸の範囲固定は使用できません。カテゴリは「表示順」で並べ替えられます。</p>'
          : `<div class="field-grid">${labelField("横軸の最小値", input("style.x_min", p.style.x_min, "number", 'step="any" placeholder="自動"'))}${labelField("横軸の最大値", input("style.x_max", p.style.x_max, "number", 'step="any" placeholder="自動"'))}</div><p class="settings-help">横軸範囲は数値軸に適用されます。日付はデータの期間で絞り込めます。</p>`) +
        `<div class="field-grid">${labelField("縦軸の最小値", input("style.y_min", p.style.y_min, "number", 'step="any" placeholder="自動"'))}${labelField("縦軸の最大値", input("style.y_max", p.style.y_max, "number", 'step="any" placeholder="自動"'))}</div><p class="settings-help">空欄の場合はデータの最小値・最大値に合わせて自動調整されます。</p>` +
        sectionTitle("表示オプション", "グラフ要素の表示切り替えと並び順") +
        labelField(
          "表示順",
          select("style.sort", p.style.sort, {
            x_asc: "横軸の昇順（古い順 / A→Z）",
            x_desc: "横軸の降順（新しい順 / Z→A）",
            y_desc: "値の大きい順（降順）",
            y_asc: "値の小さい順（昇順）",
          }),
        ) +
        `<label class="toggle-label"><input type="checkbox" data-field="style.legend" ${p.style.legend ? "checked" : ""}><span class="toggle-switch"></span>凡例を表示</label>` +
        `<label class="toggle-label"><input type="checkbox" data-field="style.labels" ${p.style.labels ? "checked" : ""}><span class="toggle-switch"></span>数値ラベルを表示（折れ線・棒）</label>`;
    }
    if (state.tab === "style" && !["table", "pie"].includes(p.chart)) {
      const temporal = state.metadata.sources[p.source].some(
          (f) => f.key === p.x && f.type === "date",
        ),
        categorical =
          ["box", "bar"].includes(p.chart) ||
          state.metadata.sources[p.source].some(
            (f) => f.key === p.x && !["number", "date"].includes(f.type),
          );
      html += '<span class="field-label">目盛りラベルの間隔</span>';
      for (const [axis, label] of [
        ["x", "横軸"],
        ["y", "縦軸"],
      ]) {
        const interval = p.style[`${axis}_tick_interval`];
        html += labelField(
          `${label}の目盛り間隔`,
          `<select data-tick-mode="${axis}"><option value="auto" ${interval == null ? "selected" : ""}>Auto</option><option value="manual" ${interval != null ? "selected" : ""}>数値指定</option></select>`,
        );
        if (interval != null)
          html += labelField(
            `${label}の目盛り間隔の値`,
            input(
              `style.${axis}_tick_interval`,
              interval,
              "number",
              axis === "x" && categorical
                ? 'min="1" step="1"'
                : 'min="0" step="any"',
            ),
          );
        if (axis === "x" && temporal && !categorical && interval != null)
          html += labelField(
            "横軸の間隔の単位",
            select("style.x_tick_unit", p.style.x_tick_unit || "day", {
              day: "日",
              hour: "時間",
              minute: "分",
              second: "秒",
            }),
          );
      }
      html +=
        '<p class="settings-help">数値軸は値の差、分類軸は項目数で指定します。ズーム・移動に合わせて目盛りも更新します。極端に細かい間隔は描画時に一部を省略します。</p>';
    }
    $("#settings-body").innerHTML = html;
    // Associate each visible field label with its native input for touch and screen readers.
    $("#settings-body")
      .querySelectorAll(".settings-field")
      .forEach((field, i) => {
        const el = field.querySelector("input,select,textarea"),
          label = field.querySelector("label");
        if (el && label) {
          el.id = `setting-${state.tab}-${i}`;
          el.setAttribute("aria-label", label.textContent.trim());
          label.htmlFor = el.id;
        }
      });
    wireSettings();
    updateUndoButton();
  }
  let previewTimer;
  function settingsChanged(rerender = false) {
    changed({ render: false });
    updateSettingsHeader();
    updateUndoButton();
    clearTimeout(previewTimer);
    previewTimer = setTimeout(renderPanels, 550);
    if (rerender) renderSettings();
  }
  function wireSettings() {
    const p = currentPanel();
    $("#settings-body")
      .querySelectorAll("[data-tick-mode]")
      .forEach((el) => {
        el.onchange = () => {
          rememberChange("style.tick");
          p.style[`${el.dataset.tickMode}_tick_interval`] =
            el.value === "auto" ? null : 1;
          settingsChanged(true);
        };
      });
    $("#settings-body")
      .querySelectorAll("[data-field]")
      .forEach((el) => {
        const handler = () => {
          rememberChange(el.dataset.field);
          const path = el.dataset.field.split(".");
          let target = p;
          path.slice(0, -1).forEach((part) => (target = target[part]));
          const property = path.at(-1);
          const value =
            el.type === "checkbox"
              ? el.checked
              : el.type === "number"
                ? el.value === ""
                  ? [
                      "x_min",
                      "x_max",
                      "y_min",
                      "y_max",
                      "x_tick_interval",
                      "y_tick_interval",
                    ].includes(property)
                    ? null
                    : 0
                  : Number(el.value)
                : el.value;
          target[property] = value;
          let structural = false;
          if (el.dataset.field === "source") {
            applySource(p, value);
            structural = true;
          }
          if (el.dataset.field === "chart") {
            applyChart(p, value);
            structural = true;
          }
          if (el.dataset.field === "transform") structural = true;
          if (
            [
              "table_group",
              "table_group_dates",
              "table_group_multivalue",
            ].includes(el.dataset.field)
          ) {
            p.table_collapsed_groups = [];
            structural = true;
          }
          if (el.dataset.field.startsWith("table_sorts.")) {
            if (p.table_sorts[0]) {
              p.table_sort = p.table_sorts[0].field;
              p.table_desc = p.table_sorts[0].desc;
            }
            structural = el.tagName === "SELECT";
          }
          if (el.dataset.field === "title") {
            const i = state.view.config.panels.indexOf(p);
            if (i >= 0) $("#settings-title").textContent = p.title;
            updateSettingsHeader(p);
          }
          if (property === "scope") structural = true;
          settingsChanged(structural);
        };
        el.addEventListener(
          el.tagName === "SELECT" ||
            el.type === "checkbox" ||
            el.type === "color"
            ? "change"
            : "input",
          handler,
        );
      });
    $("#settings-body")
      .querySelectorAll("[data-source-card]")
      .forEach(
        (el) =>
          (el.onchange = () => {
            if (!el.checked || !confirmSourceChange(p)) {
              renderSettings();
              return;
            }
            rememberChange("source");
            applySource(p, el.value);
            settingsChanged(true);
          }),
      );
    $("#settings-body")
      .querySelectorAll("[data-chart-card]")
      .forEach(
        (el) =>
          (el.onchange = () => {
            if (!el.checked) return;
            rememberChange("chart");
            applyChart(p, el.value);
            settingsChanged(true);
          }),
      );
    $("#settings-body")
      .querySelectorAll("[data-y],[data-column]")
      .forEach(
        (el) =>
          (el.onchange = () => {
            rememberChange(el.dataset.y ? "y" : "columns");
            const key = el.dataset.y ? "y" : "columns",
              field = el.dataset.y || el.dataset.column;
            p[key] = el.checked
              ? [...p[key], field]
              : p[key].filter((v) => v !== field);
            const card = el.closest(".check-card");
            if (card) card.classList.toggle("is-checked", el.checked);
            settingsChanged();
          }),
      );
    $("#check-all-cols")?.addEventListener("click", () => {
      rememberChange("columns");
      p.columns = Object.keys(fieldOptions(p, { rowOnly: true }));
      settingsChanged(true);
    });
    $("#check-none-cols")?.addEventListener("click", () => {
      rememberChange("columns");
      p.columns = [];
      settingsChanged(true);
    });
    $("#check-default-cols")?.addEventListener("click", () => {
      rememberChange("columns");
      p.columns =
        p.source === "followers"
          ? ["date", "measured_at", "followers"]
          : ["title", "date", "character", "likes", "retweets", "impressions"];
      settingsChanged(true);
    });
    $("#check-all-y")?.addEventListener("click", () => {
      rememberChange("y");
      p.y = Object.keys(
        p.chart === "scatter"
          ? fieldOptions(p, { numeric: true, rowOnly: true })
          : fieldOptions(p, { numeric: true }),
      );
      settingsChanged(true);
    });
    $("#check-none-y")?.addEventListener("click", () => {
      rememberChange("y");
      p.y = [];
      settingsChanged(true);
    });
    $("#settings-body")
      .querySelectorAll("[data-preset-days]")
      .forEach((btn) => {
        btn.onclick = () => {
          rememberChange("period_days");
          const days = Number(btn.dataset.presetDays);
          p.period_days = days;
          const inputEl = $("#settings-body [data-field='period_days']");
          if (inputEl) inputEl.value = days;
          settingsChanged();
        };
      });
    $("#settings-body")
      .querySelectorAll("[data-color-swatch]")
      .forEach((btn) => {
        btn.onclick = () => {
          rememberChange("style.color");
          const color = btn.dataset.colorSwatch;
          p.style.color = color;
          const inputEl = $("#settings-body [data-field='style.color']");
          if (inputEl) inputEl.value = color;
          settingsChanged(true);
        };
      });
    $("#settings-body")
      .querySelectorAll("[data-switch-tab]")
      .forEach((btn) => {
        btn.onclick = () => {
          state.tab = btn.dataset.switchTab;
          renderSettings();
        };
      });
    $("#add-filter-group")?.addEventListener("click", () => {
      rememberChange("filters");
      p.filters.push({
        join: "and",
        rules: [
          {
            field: Object.keys(fieldOptions(p, { rowOnly: true }))[0],
            op: "contains",
            value: "",
          },
        ],
      });
      settingsChanged(true);
    });
    $("#add-table-sort")?.addEventListener("click", () => {
      rememberChange("table_sorts");
      const fields = fieldOptions(p, { rowOnly: true }),
        used = new Set(p.table_sorts.map((sort) => sort.field));
      const field = Object.keys(fields).find((field) => !used.has(field));
      if (!field || p.table_sorts.length >= 5) return;
      p.table_sorts.push({ field, desc: false });
      settingsChanged(true);
    });
    $("#settings-body")
      .querySelectorAll("[data-sort-remove]")
      .forEach(
        (button) =>
          (button.onclick = () => {
            rememberChange("table_sorts");
            p.table_sorts.splice(Number(button.dataset.sortRemove), 1);
            settingsChanged(true);
          }),
      );
    $("#settings-body")
      .querySelectorAll("[data-sort-move]")
      .forEach(
        (button) =>
          (button.onclick = () => {
            rememberChange("table_sorts");
            const [index, delta] = button.dataset.sortMove
                .split(",")
                .map(Number),
              next = index + delta;
            if (next < 0 || next >= p.table_sorts.length) return;
            [p.table_sorts[index], p.table_sorts[next]] = [
              p.table_sorts[next],
              p.table_sorts[index],
            ];
            settingsChanged(true);
          }),
      );
    $("#settings-body")
      .querySelectorAll("[data-add-rule]")
      .forEach(
        (el) =>
          (el.onclick = () => {
            rememberChange("filters");
            p.filters[Number(el.dataset.addRule)].rules.push({
              field: p.source === "followers" ? "followers" : "character",
              op: "contains",
              value: "",
            });
            settingsChanged(true);
          }),
      );
    $("#settings-body")
      .querySelectorAll("[data-remove-group]")
      .forEach(
        (el) =>
          (el.onclick = () => {
            rememberChange("filters");
            p.filters.splice(Number(el.dataset.removeGroup), 1);
            settingsChanged(true);
          }),
      );
    $("#settings-body")
      .querySelectorAll("[data-remove-rule]")
      .forEach(
        (el) =>
          (el.onclick = () => {
            rememberChange("filters");
            const [gi, ri] = el.dataset.removeRule.split(",").map(Number);
            p.filters[gi].rules.splice(ri, 1);
            settingsChanged(true);
          }),
      );
    const addFormula = (
      label = "新しい指標",
      expression = "likes / impressions * 100",
      scope = "row",
    ) => {
      if (p.formulas.length >= 10) {
        toast("計算指標は10個までです");
        return;
      }
      rememberChange("formulas");
      p.formulas.push({
        key: id("calc"),
        label,
        expression: p.source === "followers" ? "followers" : expression,
        scope,
      });
      settingsChanged(true);
    };
    $("#add-formula")?.addEventListener("click", () => addFormula());
    $("#settings-body")
      .querySelectorAll("[data-example]")
      .forEach(
        (el) =>
          (el.onclick = () => {
            if (el.dataset.example === "aggregate")
              addFormula(
                "合計反応率",
                "sum(likes) / sum(impressions) * 100",
                "group",
              );
            else if (el.dataset.example === "speed")
              addFormula("時間あたりのいいね", "likes / elapsed_hours");
            else addFormula("いいね率（%）");
          }),
      );
    $("#settings-body")
      .querySelectorAll("[data-remove-formula]")
      .forEach(
        (el) =>
          (el.onclick = () => {
            rememberChange("formulas");
            const index = Number(el.dataset.removeFormula),
              key = p.formulas[index].key;
            p.formulas.splice(index, 1);
            p.y = p.y.filter((v) => v !== key);
            if (!p.y.length)
              p.y = [p.source === "followers" ? "followers" : "likes"];
            p.columns = p.columns.filter((v) => v !== key);
            if (p.x === key) p.x = "date";
            if (p.series === key) p.series = "";
            if (p.table_group === key) {
              p.table_group = "";
              p.table_collapsed_groups = [];
            }
            if (p.table_sorts)
              p.table_sorts = p.table_sorts.filter(
                (sort) => sort.field !== key,
              );
            if (p.table_sort === key) p.table_sort = "date";
            settingsChanged(true);
          }),
      );
    $("#settings-body")
      .querySelectorAll("[data-insert-formula]")
      .forEach(
        (el) =>
          (el.onchange = () => {
            rememberChange("formulas");
            p.formulas[Number(el.dataset.insertFormula)].expression += el.value;
            settingsChanged(true);
          }),
      );
  }
  function characterNames() {
    return [
      ...new Set([
        ...state.metadata.characters,
        ...state.newCharacters,
        ...state.characterSelection,
      ]),
    ];
  }
  function suggestCharacters(query) {
    return AnalysisCharacters.suggest(characterNames(), {
      selected: state.characterSelection,
      counts: state.metadata.character_counts || {},
      query,
      max: characterSuggestionLimit,
    });
  }
  function hideCharacterSuggestions() {
    characterSuggestionNames = [];
    characterActiveSuggestion = -1;
    const list = $("#character-suggestions");
    list.innerHTML = "";
    list.hidden = true;
    $("#character-name").setAttribute("aria-expanded", "false");
    $("#character-name").removeAttribute("aria-activedescendant");
  }
  function renderCharacterSuggestions() {
    const input = $("#character-name");
    const list = $("#character-suggestions");
    characterSuggestionNames = suggestCharacters(input.value);
    if (!characterSuggestionNames.length) {
      hideCharacterSuggestions();
      return;
    }
    if (characterActiveSuggestion >= characterSuggestionNames.length)
      characterActiveSuggestion = -1;
    list.innerHTML = characterSuggestionNames
      .map((name, index) => {
        const count = Number(state.metadata.character_counts?.[name]) || 0;
        return `<li id="character-suggestion-${index}" role="option" aria-selected="${index === characterActiveSuggestion}" data-character-suggestion="${esc(name)}"><span>${esc(name)}</span>${count ? `<small>${count}作品</small>` : ""}</li>`;
      })
      .join("");
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
    if (characterActiveSuggestion >= 0) {
      input.setAttribute(
        "aria-activedescendant",
        `character-suggestion-${characterActiveSuggestion}`,
      );
    } else input.removeAttribute("aria-activedescendant");
  }
  function renderCharacterOptions() {
    const host = $("#character-options");
    host.innerHTML = state.characterSelection.length
      ? state.characterSelection
          .map(
            (name) =>
              `<span class="character-chip character-chip-selected"><span>${esc(name)}</span><button type="button" class="character-chip-remove" data-remove-character="${esc(name)}" aria-label="${esc(name)}を選択から外す">×</button></span>`,
          )
          .join("")
      : '<span class="character-empty">未選択</span>';
    host.querySelectorAll("[data-remove-character]").forEach((button) => {
      button.onclick = () => {
        state.characterSelection = state.characterSelection.filter(
          (name) => name !== button.dataset.removeCharacter,
        );
        renderCharacterOptions();
        renderCharacterSuggestions();
        $("#character-name").focus();
      };
    });
  }
  function addCharacter(value) {
    const name = String(value ?? "").trim();
    if (!name) return;
    const key = AnalysisCharacters.normalize(name);
    const existing = characterNames().find(
      (item) => AnalysisCharacters.normalize(item) === key,
    );
    const resolved = existing || name;
    if (!existing && !state.newCharacters.includes(resolved))
      state.newCharacters.push(resolved);
    if (!state.characterSelection.includes(resolved))
      state.characterSelection.push(resolved);
    $("#character-name").value = "";
    characterActiveSuggestion = -1;
    renderCharacterOptions();
    renderCharacterSuggestions();
    $("#character-name").focus();
  }
  function openCharacters(row) {
    state.characterRow = row;
    state.characterSelection = [...new Set(row.characters || [])];
    state.newCharacters = [];
    $("#character-status").textContent = "";
    $("#character-name").value = "";
    renderCharacterOptions();
    renderCharacterSuggestions();
    $("#character-dialog").showModal();
  }
  $("#add-character-form").onsubmit = (event) => {
    event.preventDefault();
    addCharacter($("#character-name").value);
  };
  $("#character-name").addEventListener("input", () => {
    characterActiveSuggestion = -1;
    renderCharacterSuggestions();
  });
  $("#character-name").addEventListener("focus", renderCharacterSuggestions);
  $("#character-name").addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!characterSuggestionNames.length) renderCharacterSuggestions();
      if (!characterSuggestionNames.length) return;
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      characterActiveSuggestion =
        characterActiveSuggestion < 0
          ? step > 0
            ? 0
            : characterSuggestionNames.length - 1
          : (characterActiveSuggestion +
              step +
              characterSuggestionNames.length) %
            characterSuggestionNames.length;
      renderCharacterSuggestions();
      document
        .getElementById(`character-suggestion-${characterActiveSuggestion}`)
        ?.scrollIntoView({ block: "nearest" });
    } else if (event.key === "Enter") {
      if (
        characterActiveSuggestion >= 0 &&
        characterSuggestionNames[characterActiveSuggestion]
      ) {
        event.preventDefault();
        addCharacter(characterSuggestionNames[characterActiveSuggestion]);
      }
    } else if (
      event.key === "Escape" &&
      !$("#character-suggestions").hidden
    ) {
      event.preventDefault();
      event.stopPropagation();
      hideCharacterSuggestions();
    }
  });
  $("#character-suggestions").addEventListener("mousedown", (event) =>
    event.preventDefault(),
  );
  $("#character-suggestions").addEventListener("click", (event) => {
    const option = event.target.closest("[data-character-suggestion]");
    if (option) addCharacter(option.dataset.characterSuggestion);
  });
  document.addEventListener("click", (event) => {
    const dialog = $("#character-dialog");
    if (!dialog.open || !event.composedPath().includes(dialog)) return;
    if (event.composedPath().includes($("#add-character-form"))) return;
    if (!$("#character-suggestions").hidden) hideCharacterSuggestions();
  });
  $("#character-dialog").addEventListener("close", hideCharacterSuggestions);
  $("#suggest-characters").onclick = async () => {
    try {
      const row = state.characterRow;
      const names = DEMO
        ? row.tags.filter((tag) => state.metadata.characters.includes(tag))
        : (
            await api(
              `/api/artworks/${encodeURIComponent(row.artwork_id)}/character/suggestion`,
            )
          ).characters;
      state.characterSelection = [...new Set(names)];
      renderCharacterOptions();
      renderCharacterSuggestions();
      $("#character-status").textContent = names.length
        ? "候補を入力しました。保存すると反映されます。"
        : "対応するタグがありません。";
    } catch (error) {
      $("#character-status").textContent = error.message;
    }
  };
  $("#save-characters").onclick = async () => {
    const button = $("#save-characters");
    button.disabled = true;
    try {
      const names = [...new Set(state.characterSelection)],
        row = state.characterRow;
      if (DEMO) {
        const overrides = getStored("xart_demo_characters", {});
        overrides[row.artwork_id] = names;
        store("xart_demo_characters", overrides);
      } else
        await api(`/api/artworks/${encodeURIComponent(row.artwork_id)}`, {
          method: "PATCH",
          body: JSON.stringify({ characters: names }),
        });
      state.metadata.characters = [
        ...new Set([...state.metadata.characters, ...names]),
      ];
      const previous = new Set(row.characters || []);
      const counts =
        state.metadata.character_counts ||
        (state.metadata.character_counts = {});
      previous.forEach((name) => {
        if (!names.includes(name))
          counts[name] = Math.max(0, (Number(counts[name]) || 0) - 1);
      });
      names.forEach((name) => {
        if (!previous.has(name))
          counts[name] = (Number(counts[name]) || 0) + 1;
      });
      $("#character-dialog").close();
      renderPanels();
      toast("キャラクターを保存しました");
    } catch (error) {
      $("#character-status").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
  $("#new-view").onclick = $("#sidebar-add").onclick = () => {
    if (!state.user) {
      toast("利用者一覧を読み込んでから操作してください");
      return;
    }
    $("#create-dialog").showModal();
  };
  $("#close-settings").onclick = () => $("#settings").close();
  $("#done-settings")?.addEventListener("click", () => $("#settings").close());
  $("#undo-settings")?.addEventListener("click", undoChange);
  $("#save-view")?.addEventListener("click", saveChanges);
  $("#save-settings")?.addEventListener("click", saveChanges);
  window.addEventListener("keydown", (event) => {
    if (
      (event.ctrlKey || event.metaKey) &&
      event.key.toLowerCase() === "s"
    ) {
      event.preventDefault();
      saveChanges();
    }
  });
  document
    .querySelectorAll("[data-close]")
    .forEach((el) => (el.onclick = () => $(`#${el.dataset.close}`).close()));
  document.querySelectorAll("[data-tab]").forEach(
    (el) =>
      (el.onclick = () => {
        state.tab = el.dataset.tab;
        renderSettings();
      }),
  );
  $("#view-name").oninput = () => {
    if (state.view.locked) return;
    state.view.name = $("#view-name").value;
    changed({ render: false });
  };
  $("#layout").onchange = () => {
    if (state.view.locked) return;
    state.view.config.layout = $("#layout").value;
    changed({ render: false });
    renderWorkspace();
  };
  $("#toggle-lock").onclick = toggleViewLock;
  $("#add-panel").onclick = () => {
    if (!state.view) return;
    if (state.view.locked) {
      toast("ロック中のビューはパネルを追加できません");
      return;
    }
    if (state.view.config.panels.length >= 12) {
      toast("1ビューには12パネルまで追加できます");
      return;
    }
    renderPanelTypes();
    $("#panel-type-dialog").showModal();
  };
  $("#duplicate-view").onclick = async () => {
    try {
      const source = state.view;
      const view = DEMO
        ? {
            id: id("view"),
            name: (source.name + " のコピー").slice(0, 100),
            config: clone(source.config),
            revision: 1,
            locked: false,
          }
        : await api("/api/analytics/views", {
            method: "POST",
            body: JSON.stringify({
              name: (source.name + " のコピー").slice(0, 100),
              config: source.config,
            }),
          });
      state.views.push(view);
      if (DEMO) store(storageKey("views"), state.views);
      selectView(view.id);
    } catch (error) {
      setError(error.message);
    }
  };
  $("#delete-view").onclick = async () => {
    if (state.view?.locked) {
      toast("ロック中のビューは削除できません。先にロックを解除してください");
      return;
    }
    if (state.savingAll || state.saving.has(state.view?.id)) {
      toast("設定を保存中です。完了後に削除してください");
      return;
    }
    const message = state.dirty.has(state.view.id)
      ? "このビューには未保存の変更があります。変更を破棄して削除しますか？ 元データは削除されません。"
      : "このビューを削除しますか？ 元データは削除されません。";
    if (!confirm(message)) return;
    const view = state.view;
    try {
      if (!DEMO)
        await api(`/api/analytics/views/${encodeURIComponent(view.id)}`, {
          method: "DELETE",
        });
      state.views = state.views.filter((v) => v.id !== view.id);
      state.dirty.delete(view.id);
      saveDrafts();
      if (DEMO) store(storageKey("views"), state.views);
      selectView(state.views[0]?.id);
    } catch (error) {
      setError(error.message);
    }
  };
  $("#refresh").onclick = async () => {
    if (!state.user) {
      await init();
      return;
    }
    if (state.recovery.length) {
      openConflict();
      return;
    }
    setError("");
    if (state.view) renderPanels();
  };
  window.addEventListener("online", () => setError(""));
  window.addEventListener("beforeunload", (event) => {
    saveDrafts();
    if (state.dirty.size) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      document.querySelectorAll("[data-panel]").forEach((article) => {
        const cached = state.results.get(article.dataset.panel);
        if (cached && cached.panel.chart !== "table")
          AnalysisCharts.render(
            article.querySelector(".chart-container"),
            cached.panel,
            cached.data,
          );
      });
    }, 150);
  });
  async function init() {
    renderTemplates();
    renderPanelTypes();
    try {
      if (DEMO) {
        $("#demo-banner").hidden = false;
        state.user = {
          id: getStored("xart_demo_user", "demo_a"),
          name: "デモユーザー",
        };
        state.metadata = await api("/demo-api/metadata");
        state.views = getStored(storageKey("views"), null);
        if (!state.views) {
          state.views = templates().map((template) => ({
            id: id("view"),
            name: template.name,
            config: template.config,
            revision: 1,
          }));
          store(storageKey("views"), state.views);
        }
        state.views.forEach(normalizeView);
        const overrides = getStored("xart_demo_characters", {});
        state.metadata.characters = [
          ...new Set([
            ...state.metadata.characters,
            ...Object.values(overrides).flat(),
          ]),
        ];
      } else {
        state.profiles = (await api("/api/profiles")).profiles;
        state.user =
          state.profiles.find(
            (profile) => profile.id === getStored("xart_profile_id", null),
          ) || state.profiles[0];
        store("xart_profile_id", state.user.id);
        const [metadata, views] = await Promise.all([
          api("/api/analytics/metadata"),
          api("/api/analytics/views"),
        ]);
        state.metadata = metadata;
        state.views = views.views.map(normalizeView);
        const drafts = getStored(storageKey("drafts"), []);
        drafts.forEach((draft) => {
          const saved = state.views.find((view) => view.id === draft.id);
          if (saved && saved.revision === draft.revision) {
            saved.name = draft.name;
            saved.config = draft.config;
            state.dirty.add(saved.id);
          } else {
            state.recovery.push(draft);
          }
        });
      }
      renderAccount();
      selectView(getStored(storageKey("active"), state.views.at(-1)?.id));
      updateSaveState();
      openConflict();
    } catch (error) {
      setError(error.message);
    }
  }
  init();
})();
