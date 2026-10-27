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
    saveError: "",
    saved: new Map(),
    sections: {},
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
  const chartCards = {
    table: {name:"テーブル"}, line: {name:"折れ線"}, bar: {name:"棒"},
    pie: {name:"円"}, scatter: {name:"散布図"}, box: {name:"箱ひげ図"},
    histogram: {name:"ヒストグラム"},
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
      return true;
    } catch {
      toast(
        "ブラウザーの保存容量が不足しています。設定を保存できない場合があります",
      );
      return false;
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
        "絞り込みと計算式を解除して種類を変えますか？",
      )
    );
  }
  function applyChart(panel, chart) { panel.chart = chart; }
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
      error.detail = detail;
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
    $("#page-error").textContent = String(message || "").replace(/^Value error, /, "").split("\n")[0];
    $("#page-error").hidden = !message;
  }
  function saveStatus(message, error = false) {
    $("#save-status").textContent = message;
    $("#save-status").toggleAttribute("data-error", error);
  }
  function updateSaveButtons() {
    $("#save-view").disabled = !state.view || !state.dirty.size || state.savingAll || state.saving.size > 0;
    $("#save-view").textContent = state.saveError ? "再試行" : "保存";
    $("#discard-changes").hidden = !state.view || !state.dirty.has(state.view.id);
    $("#discard-changes").disabled = state.savingAll || state.saving.size > 0;
  }
  function updateSaveState() {
    const saving = state.savingAll || state.saving.size > 0;
    saveStatus(!state.view ? "" : saving ? "保存中…" : state.saveError || (state.dirty.size ? "● 未保存" : "✓ 保存済み"), Boolean(state.saveError));
    updateSaveButtons();
  }
  function currentPanel() {
    return state.view?.config.panels[state.panel];
  }
  function rememberChange(key = "") {
    if (!state.view || state.view.locked) return;
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
    button.disabled = Boolean(state.view?.locked) || !state.history.some(
      (entry) => entry.viewId === state.view?.id,
    );
  }
  function undoChange() {
    if (state.view?.locked) return;
    const index = state.history.findLastIndex(entry => entry.viewId === state.view?.id);
    const entry = index < 0 ? null : state.history.splice(index, 1)[0];
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
    if (!$("#settings").hidden) renderSettings();
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
  function updateSettingsHeader(panel = currentPanel()) {
    if (panel) $("#settings-title").textContent = panel.title;
  }
  function persistDemoViews() {
    store(storageKey("views"), state.views.map(view => state.saved.get(view.id) || view));
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
    state.saveError = "";
    clearSettingsErrors();
    state.dirty.add(state.view.id);
    saveDrafts();
    updateSaveState();
    renderViewList();
    if (render) { renderPanels(); if (!$("#settings").hidden) renderSettings(); }
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
    state.saveError = "";
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
      state.saveError = "ビュー名を入力してください";
      updateSaveState();
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
        const latest = getStored(storageKey("views"), []).find(item => item.id === view.id);
        if (!latest || latest.revision !== snapshot.revision || latest.locked) {
          const conflict = new Error("別のタブで更新されています"); conflict.status = 409; throw conflict;
        }
        for (const panel of snapshot.config.panels) await api("/demo-api/query", { method: "POST", body: JSON.stringify({panel, characters:getStored("xart_demo_characters", {})}) });
        const nextRevision = view.revision + 1;
        const latestViews = getStored(storageKey("views"), []);
        const current = latestViews.find(item => item.id === view.id);
        if (!current || current.revision !== snapshot.revision || current.locked) {
          const conflict = new Error("別のタブで更新されています"); conflict.status = 409; throw conflict;
        }
        const persisted = latestViews.map(v => v.id === view.id ? { ...v, revision: nextRevision, name: snapshot.name, config: snapshot.config } : v);
        if (!store(storageKey("views"), persisted)) throw new Error("ブラウザーに保存できませんでした。空き容量を確認してください");
        view.revision = nextRevision;
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
      state.saved.set(view.id, { ...clone(view), name: snapshot.name, config: snapshot.config });
      if (
        view.name === snapshot.name &&
        JSON.stringify(view.config) === snapshotJson
      )
        state.dirty.delete(view.id);
      setError("");
      clearSettingsErrors();
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
      if (error.status === 422) showSettingsErrors(error);
    } finally {
      state.saving.delete(view.id);
      saveDrafts();
      updateSaveState();
      renderViewList();
    }
    if (saveError) {
      state.saveError = errorMessage ? String(errorMessage).replace(/^Value error, /, "").split(/[\n。]/)[0].slice(0,60) : "保存できませんでした。";
      updateSaveState();
      setError(errorMessage);

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
      state.saved.set(view.id, clone(view));
      if (DEMO) persistDemoViews();
      if (locked) {
        state.history = [];
        state.historyGroup = { key: null, at: 0 };
        updateUndoButton();

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
      const created = copy && DEMO ? { ...clone(draft), id: id("view"), name: (draft.name + "（復元）").slice(0,100), revision:1, locked:false } : copy
        ? await api("/api/analytics/views", {
            method: "POST",
            body: JSON.stringify({
              name: (draft.name + "（復元）").slice(0, 100),
              config: draft.config,
            }),
          })
        : null;
      const latest = (DEMO ? getStored(storageKey("views"), []) : (await api("/api/analytics/views")).views).find(
        (view) => view.id === draft.id,
      );
      state.views = state.views.filter((view) => view.id !== draft.id);
      state.saved.delete(draft.id);
      if (latest) { state.views.push(latest); state.saved.set(latest.id, clone(latest)); }
      if (created) { state.views.push(created); state.saved.set(created.id, clone(created)); }
      if (DEMO) persistDemoViews();
      state.recovery.shift();
      state.dirty.delete(draft.id);
      saveDrafts();
      $("#conflict-dialog").close();
      if (!$("#settings").hidden) closeSettings();
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
    $("#view-select").innerHTML = state.views.map(view => `<option value="${esc(view.id)}" ${view.id === state.view?.id ? "selected" : ""}>${esc(view.name)}${state.dirty.has(view.id) ? " ● 未保存" : ""}${view.locked ? " · ロック" : ""}</option>`).join("");
    $("#view-list").innerHTML = state.views
      .map((view) => {
        const locked = view.locked
            ? `<span class="view-lock-mark" title="ロック中" aria-hidden="true">${icon("lock")}</span><span class="sr-only">ロック中</span>`
            : "",
          dirty = state.dirty.has(view.id)
            ? '<span class="view-dirty" aria-hidden="true"></span><span class="sr-only">未保存</span>'
            : "";
        return `<button aria-label="${esc(view.name)}${view.locked ? " · ロック中" : ""}${state.dirty.has(view.id) ? " · 未保存" : ""}" data-view="${esc(view.id)}" ${state.view?.id === view.id ? 'aria-current="page"' : ""} title="${esc(view.name)}${state.dirty.has(view.id) ? " · 未保存の変更があります" : ""}">${icon(view.config.layout === "dashboard" ? "dashboard" : view.config.panels[0]?.chart)}<span>${esc(view.name)}</span>${locked}${dirty}</button>`;
      })
      .join("");
    $("#view-list")
      .querySelectorAll("[data-view]")
      .forEach(
        (button) => (button.onclick = () => selectView(button.dataset.view)),
      );
  }
  function selectView(viewId, activate = true) {
    $("#view-menu").open = false;
    if (activate && location.hash !== "#views") location.hash = "views";
    state.view = state.views.find((v) => v.id === viewId) || state.views[0];
    state.panel = 0;
    state.sections = {};
    state.generation++;
    state.saveError = "";
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
    if (!has) { closeSettings(); return; }
    const locked = Boolean(state.view.locked);
    $(".view-edit-state").textContent = locked ? "ロック中" : "編集可能";
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
    lockButton.innerHTML = icon(locked ? "unlock" : "lock") + (locked ? "ロック中" : "編集できます");
    lockButton.classList.toggle("is-locked", locked);
    lockButton.setAttribute("aria-pressed", String(locked));
    lockButton.setAttribute(
      "aria-label",
      locked ? "ビューのロックを解除" : "ビューをロック",
    );
    lockButton.title = locked ? "ビューのロックを解除" : "ビューをロック";
    $("#add-panel").disabled = locked || state.view.config.panels.length >= 12;
    $("#rebuild-view").disabled = locked;
    $("#rename-view").disabled = locked;
    $("#add-panel").title = locked
      ? "ロック中は表・グラフを追加できません"
      : state.view.config.panels.length >= 12 ? "1ビューには12パネルまで追加できます" : "";
    $("#delete-view").disabled = locked;
    $("#delete-view").title = locked ? "ロック中はビューを削除できません" : "";
    $("#analysis-content").classList.toggle("view-locked", locked);
    renderPanels();
    if (!$("#settings").hidden) renderSettings();
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
      state.saved.set(view.id, clone(view));
      persistDemoViews();
    } else {
      view = await api("/api/analytics/views", {
        method: "POST",
        body: JSON.stringify({ name: template.name, config: template.config }),
      });
      state.views.push(view);
    }
    state.saved.set(view.id, clone(view));
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
          `<button class="template-button panel-type-button" type="button" data-panel-type="${index}">${icon(template.icon)}<strong>${esc(template.name)}</strong></button>`,
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
  function resetPanel(index) {
    if (state.view?.locked || !confirm("このパネルを初期値に戻しますか？")) return;
    const old = state.view.config.panels[index];
    const template = panelTypeTemplates().find(item => item.defaults.chart === old.chart);
    rememberChange("reset-panel");
    state.view.config.panels[index] = panelDefaults({ ...template.defaults, id: old.id });
    changed(); renderSettings();
  }
  function duplicatePanel(index) {
    if (state.view?.locked || state.view.config.panels.length >= 12) return;
    rememberChange("panels");
    const panel = clone(state.view.config.panels[index]); panel.id = id("panel");
    state.view.config.panels.splice(index + 1, 0, panel); state.panel = index + 1;
    changed(); renderWorkspace(); renderSettings();
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
            if (!$("#settings").hidden) renderSettings();
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
    if (panel.chart === "table" && panel.table_group)
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
  function quickControls(panel, locked) {
    const options = (values, selected) => Object.entries(values).map(([key,label]) => `<option value="${esc(key)}" ${String(selected) === key ? "selected" : ""}>${esc(label)}</option>`).join("");
    const periods = {7:"7日",30:"30日",90:"90日",0:"全期間",custom:"期間指定"};
    const selected = panel.from_date || panel.to_date || ![0,7,30,90].includes(panel.period_days) ? "custom" : panel.period_days;
    return `<div class="panel-quick-controls"><label><span class="sr-only">表示形式</span><select data-quick="chart" ${locked ? "disabled" : ""}>${options(Object.fromEntries(Object.entries(chartCards).map(([key,item]) => [key,item.name])), panel.chart)}</select></label><label><span class="sr-only">期間</span><select data-quick="period" ${locked ? "disabled" : ""}>${options(periods,selected)}</select></label>${panel.source === "artworks" ? `<label><span class="sr-only">ステージ</span><select data-quick="stage" ${locked ? "disabled" : ""}>${options(Object.fromEntries(state.metadata.stages.map(stage => [stage.name,stageLabel(stage.name)])),panel.stage)}</select></label>` : ""}</div>`;
  }
  function renderPanels() {
    if (!state.view) return;
    if (document.body.dataset.section !== "views") return;
    const generation = ++state.generation,
      locked = Boolean(state.view.locked);
    // Viewport gestures are transient: preserve them when refreshing/rebuilding
    // this workspace, without adding them to saved View Settings.
    const chartContext = `${state.user?.id}:${state.view.id}`;
    const chartStates = new Map([...$("#panels").querySelectorAll("[data-panel]")].map(article => {
      const host = article.querySelector(".chart-container");
      return [article.dataset.panel, host?.chartContext === chartContext ? Object.fromEntries(
        ["chartViewport", "chartSignature", "chartYMode", "chartYSettings", "chartTouchMode", "hiddenSeries"].map(key => [key, host[key]])) : {}];
    }));
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
          `<article class="panel ${currentPanel()?.id === panel.id ? "is-selected" : ""} ${panel.chart === "table" ? "is-table" : ""} ${locked ? "is-locked" : ""}" data-panel="${esc(panel.id)}"><div class="panel-head"><div class="panel-title">${icon(panel.chart)}<h2 title="${esc(panel.title)}">${esc(panel.title)}</h2></div><div class="panel-controls"><button class="icon-button" data-move="-1" title="前へ移動" aria-label="このパネルを前へ">${icon("up")}</button><button class="icon-button" data-move="1" title="後ろへ移動" aria-label="このパネルを後ろへ">${icon("down")}</button><button class="icon-button panel-settings-button" data-settings title="表示・絞り込み・見た目を設定" aria-label="${esc(panel.title)}の設定">${icon("settings")}<span class="panel-action-label">設定</span></button><details class="action-menu"><summary aria-label="${esc(panel.title)}のその他の操作">…</summary><div><button class="quiet-button" data-reset-panel>リセット</button><button class="quiet-button" data-copy-panel>複製</button><button class="quiet-button danger" data-remove aria-label="${esc(panel.title)}を削除">削除</button></div></details></div></div>${quickControls(panel, locked)}<div class="panel-meta"><span>${esc(panelMetaText(panel))}</span><span class="panel-chips">${panelMetaChips(panel)}</span></div><div class="chart-container"><div class="loading">集計中…</div></div><div class="panel-footnote"></div></article>`,
      )
      .join("");
    $("#panels")
      .querySelectorAll("[data-panel]")
      .forEach((article) => {
        const index = all.findIndex(
            (panel) => panel.id === article.dataset.panel,
          ),
          panel = all[index];
        Object.assign(article.querySelector(".chart-container"), chartStates.get(panel.id), {chartContext});
        article.querySelector(".panel-title").onclick = () => openSettings(index);
        article.querySelectorAll("[data-quick]").forEach(select => select.onchange = () => {
          if (state.view.locked) return;
          if (select.dataset.quick === "period" && select.value === "custom") { openSettings(index); $("#settings [data-section='data']").open = true; return; }
          rememberChange(`quick-${panel.id}-${select.dataset.quick}`);
          if (select.dataset.quick === "chart") applyChart(panel, select.value);
          else if (select.dataset.quick === "stage") panel.stage = select.value;
          else { panel.period_days = Number(select.value); panel.from_date = ""; panel.to_date = ""; }
          state.panel = index; changed(); renderWorkspace();
        });
        article.querySelector("[data-settings]").onclick = () => {
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

        article.querySelector('[data-move="-1"]').disabled =
          locked || index === 0;
        article.querySelector('[data-move="1"]').disabled =
          locked || index === all.length - 1;
        article.querySelector("[data-reset-panel]").onclick = () => resetPanel(index);
        article.querySelector("[data-copy-panel]").onclick = () => duplicatePanel(index);
        article.querySelector("[data-reset-panel]").disabled = locked;
        article.querySelector("[data-copy-panel]").disabled = locked || all.length >= 12;
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
        article.querySelector("[data-remove]").disabled = locked || all.length === 1;
        const cached = state.results.get(panel.id);
        if (cached && cached.panel.chart === panel.chart) {
          const host = article.querySelector(".chart-container");
          if (panel.chart === "table" && cached.data.rows?.length) renderTable(host, panel, cached.data);
          else if (panel.chart !== "table" && cached.data.points?.length) AnalysisCharts.render(host, cached.panel, cached.data);
          article.classList.add("is-refreshing");
        }
        if (cached && (panel.chart === "table" ? cached.data.rows?.length : cached.data.points?.length) && JSON.stringify(cached.panel) === JSON.stringify(panel)) { article.classList.remove("is-refreshing"); article.querySelector(".panel-footnote").textContent = panelFootnote(panel, cached.data); return; }
        loadPanel(article, panel, generation);
      });
  }
  async function loadPanel(article, panel, generation) {
    const requestedPanel = clone(panel);
    try {
      const data = await api(
        DEMO ? "/demo-api/query" : "/api/analytics/query",
        {
          method: "POST",
          body: JSON.stringify(
            DEMO
              ? { panel: requestedPanel, characters: getStored("xart_demo_characters", {}) }
              : requestedPanel,
          ),
        },
      );
      if (generation !== state.generation || !article.isConnected || JSON.stringify(panel) !== JSON.stringify(requestedPanel)) return;
      article.classList.remove("is-refreshing");
      state.results.set(panel.id, { panel: clone(panel), data });
      const host = article.querySelector(".chart-container");
      const hasData =
        panel.chart === "table"
          ? (data.rows?.length || 0) > 0
          : (data.points?.length || 0) > 0;
      if (!hasData) {
        // Disable pointer handling while this panel has no usable points.
        host.chartInfo = { plot: null, direct() {}, hide() {} };
        host.chartPrepared = null;
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
            if (!$("#settings").hidden) renderSettings();
          },
        );
        host.querySelector("[data-empty-filters]")?.addEventListener(
          "click",
          () => {
            rememberChange("filters");
            panel.filters = [];
            changed();
            if (!$("#settings").hidden) renderSettings();
          },
        );
      } else if (panel.chart === "table")
        renderTable(host, panel, data);
      else AnalysisCharts.render(host, panel, data);
      article.querySelector(".panel-footnote").textContent = panelFootnote(
        panel,
        data,
      );
      if (!$("#settings").hidden && currentPanel()?.id === panel.id)
        updateSettingsHeader(panel);
      if (article === document.querySelector("[data-panel]"))
        renderInsights(data, panel);
    } catch (error) {
      if (generation !== state.generation || !article.isConnected || JSON.stringify(panel) !== JSON.stringify(requestedPanel)) return;
      article.classList.remove("is-refreshing");
      if (error.status === 422 && currentPanel()?.id === panel.id) showSettingsErrors(error);
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
  const { openSettings, closeSettings, renderSettings, clearSettingsErrors, showSettingsErrors } = AnalyticsSettings({
    $, esc, icon, state, chartCards,
    stageLabel, currentPanel, rememberChange, changed, updateSettingsHeader, updateUndoButton,
    updateSaveState, renderPanels, confirmSourceChange, applySource, applyChart, resetPanel,
    duplicatePanel, toast, id, fieldLabel, periodLabel, panelFilterCount,
  });
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
    if (event.isComposing) return;
    if (
      event.key === "Tab" &&
      !event.shiftKey &&
      !event.ctrlKey &&
      !event.altKey &&
      !event.metaKey &&
      event.target.value.trim() &&
      !$("#character-suggestions").hidden &&
      characterSuggestionNames.length
    ) {
      event.preventDefault();
      addCharacter(
        characterSuggestionNames[Math.max(0, characterActiveSuggestion)],
      );
      return;
    }
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
  $("#close-settings").onclick = () => closeSettings();
  $("#undo-settings")?.addEventListener("click", undoChange);
  $("#save-view")?.addEventListener("click", saveChanges);
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("#settings").hidden && !document.querySelector("dialog[open],[popover]:popover-open")) closeSettings();
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && !event.shiftKey && !/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) { event.preventDefault(); undoChange(); }
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
  $("#view-name").oninput = () => {
    if (state.view.locked) return;
    rememberChange("view-name");
    state.view.name = $("#view-name").value;
    changed({ render: false });
  };
  $("#layout").onchange = () => {
    if (state.view.locked) return;
    rememberChange("layout");
    state.view.config.layout = $("#layout").value;
    changed({ render: false });
    renderWorkspace();
  };
  const resetViewsButton = document.createElement("button");
  resetViewsButton.type = "button";
  resetViewsButton.className = "sidebar-create danger";
  resetViewsButton.textContent = "すべてのビューをリセット…";
  $("#sidebar-add").after(resetViewsButton);
  let backupDownloaded = false;
  function updateResetConfirmation() {
    $("#confirm-reset-views").disabled = !backupDownloaded || $("#reset-views-count").value.trim() !== String(state.views.length);
  }
  resetViewsButton.onclick = () => {
    if (!state.user || state.savingAll || state.saving.size) return;
    backupDownloaded = false; $("#reset-views-count").value = "";
    $("#reset-views-description").textContent = `${state.views.length}件のビューが対象です。ロックされていない ${state.views.filter(view => !view.locked).length} 件を削除します。`;
    $("#reset-views-error").textContent = ""; updateResetConfirmation();
    $("#reset-views-dialog").showModal();
  };
  $("#reset-views-count").oninput = updateResetConfirmation;
  $("#download-views").onclick = () => {
    const blob = new Blob([JSON.stringify({ version: 1, exported_at: new Date().toISOString(), profile: state.user, views: state.views, saved_views: [...state.saved.values()], recovery: state.recovery }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob), link = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "");
    link.href = url; link.download = `analytics-views-backup-${state.user.name.replace(/[\\/:*?"<>|]/g, "_")}-${stamp}.json`;
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    backupDownloaded = true; updateResetConfirmation();
  };
  $("#confirm-reset-views").onclick = async () => {
    if (!backupDownloaded || $("#reset-views-count").value.trim() !== String(state.views.length)) return;
    const button = $("#confirm-reset-views"); button.disabled = true;
    let skipped = 0, failed = 0, deleted = 0;
    for (const view of [...state.views]) {
      if (view.locked) { skipped++; continue; }
      try {
        if (!DEMO) await api(`/api/analytics/views/${encodeURIComponent(view.id)}`, { method: "DELETE" });
        deleted++;
        state.views = state.views.filter(item => item.id !== view.id);
        state.saved.delete(view.id); state.dirty.delete(view.id);
        state.recovery = state.recovery.filter(item => item.id !== view.id);
      } catch (error) { if (error.status === 409) skipped++; else failed++; }
    }
    if (DEMO) store(storageKey("views"), state.views.map(view => state.saved.get(view.id) || view));
    saveDrafts(); closeSettings(); $("#reset-views-dialog").close();
    state.view = null; state.panel = 0; state.generation++;
    store(storageKey("active"), null); renderWorkspace(); updateSaveState();
    toast(`${deleted} 件を削除し、ロック中のため ${skipped} 件を残しました${failed ? `（削除失敗 ${failed} 件）` : ""}。`);
  };
  document.addEventListener("click", event => {
    document.querySelectorAll(".action-menu[open]").forEach(menu => {
      if (!menu.contains(event.target) || event.target.closest("button")) menu.open = false;
    });
  });
  document.addEventListener("keydown", event => {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".action-menu[open]").forEach(menu => { menu.open = false; menu.querySelector("summary").focus(); });
  });
  $("#mobile-views-menu").onclick = event => {
    event.stopPropagation();
    $(".mobile-menu-button").click();
  };
  $("#view-select").onchange = event => selectView(event.target.value);
  $("#rename-view").onclick = () => { $("#view-menu").open = false; $("#view-name").focus(); $("#view-name").select(); };
  document.querySelectorAll(".sidebar a").forEach(link => { link.title = link.textContent.trim(); link.setAttribute("aria-label", link.title); });
  $("#collapse-views").onclick = () => {
    const collapsed = document.body.classList.toggle("views-collapsed");
    $("#collapse-views").setAttribute("aria-expanded", String(!collapsed));
    store("xart_analytics_views_collapsed", collapsed);
  };
  if (getStored("xart_analytics_views_collapsed", false)) { document.body.classList.add("views-collapsed"); $("#collapse-views").setAttribute("aria-expanded", "false"); }
  $("#toggle-lock").onclick = toggleViewLock;
  $("#discard-changes").onclick = () => {
    const view = state.view, saved = state.saved.get(view?.id);
    if (!saved || !confirm("最後に保存した状態へ戻しますか？")) return;
    Object.assign(view, clone(saved)); state.dirty.delete(view.id); state.history = state.history.filter(entry => entry.viewId !== view.id); state.panel = 0; state.saveError = "";
    saveDrafts(); updateSaveState(); renderWorkspace(); updateUndoButton();
  };
  $("#rebuild-view").onclick = () => {
    $("#rebuild-templates").innerHTML = templates().map((t,i) => `<button type="button" class="template-button" data-rebuild="${i}">${icon(t.icon)}<strong>${esc(t.name)}</strong><small>${esc(t.description)}</small></button>`).join("");
    $("#rebuild-templates").querySelectorAll("[data-rebuild]").forEach(button => button.onclick = () => {
      if (state.view.locked || !confirm("このビューのパネルをテンプレートに置き換えます。保存するまでは確定しません。")) return;
      rememberChange("rebuild"); state.view.config = templates()[Number(button.dataset.rebuild)].config; state.panel = 0;
      $("#rebuild-dialog").close(); changed({render:false}); renderWorkspace();
    });
    $("#rebuild-dialog").showModal();
  };
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
      state.saved.set(view.id, clone(view));
      if (DEMO) store(storageKey("views"), state.views.map(v => state.saved.get(v.id) || v));
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
      state.saved.delete(view.id);
      saveDrafts();
      if (DEMO) store(storageKey("views"), state.views.map(v => state.saved.get(v.id) || v));
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
    if (state.view) { state.results.clear(); renderPanels(); }
  };
  window.addEventListener("online", () => setError(""));
  window.addEventListener("beforeunload", (event) => {
    saveDrafts();
    if (state.dirty.size || state.recovery.length) {
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
        const live = state.view?.config.panels.find(panel => panel.id === article.dataset.panel);
        if (cached && cached.panel.chart !== "table" && JSON.stringify(cached.panel) === JSON.stringify(live))
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
        state.views.forEach(view => state.saved.set(view.id, clone(view)));
        getStored(storageKey("drafts"), []).forEach(draft => { const saved = state.views.find(view => view.id === draft.id); if (saved && saved.revision === draft.revision) { saved.name = draft.name; saved.config = draft.config; state.dirty.add(saved.id); } else state.recovery.push(draft); });
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
        state.views.forEach(view => state.saved.set(view.id, clone(view)));
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
      state.views.forEach(view => { if (!state.saved.has(view.id)) state.saved.set(view.id, clone(view)); });
      renderAccount();
      selectView(getStored(storageKey("active"), state.views.at(-1)?.id), false);
      updateSaveState();
      openConflict();
      if (location.hash === "#create") $("#create-dialog").showModal();
    } catch (error) {
      setError(error.message);
    }
  }
  window.addEventListener("hashchange", () => {
    if (document.body.dataset.section === "views") renderWorkspace();
  });
  init();
})();
