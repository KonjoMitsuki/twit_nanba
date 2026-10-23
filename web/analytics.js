/* Personal view designer. Real data uses authenticated APIs; demo is synthetic. */
(() => {
  const $ = (selector) => document.querySelector(selector);
  const esc = AnalysisCharts.escape,
    fmt = AnalysisCharts.format;
  const DEMO = new URLSearchParams(location.search).get("demo") === "1";
  const icons = {
    chart: '<path d="M4 18V6m0 12h16M7 14l4-5 4 3 5-7"/>',
    calendar:
      '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
    refresh: '<path d="M20 11a8 8 0 1 0-2 7M20 4v7h-7"/>',
    copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
    dashboard:
      '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    table:
      '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M3 14h18M9 4v16"/>',
    line: '<path d="M3 3v18h18M6 15l5-7 4 3 5-6"/>',
    pie: '<path d="M12 3v9h9A9 9 0 1 1 12 3Z"/><path d="M15 2v7h7a9 9 0 0 0-7-7Z"/>',
    box: '<path d="M3 12h18M5 8v8m14-8v8M8 7h8v10H8Zm4 0v10"/>',
    histogram:
      '<path d="M3 21h18M5 21V12h4v9m0 0V5h4v16m0 0V9h4v12m0 0V15h4v6"/>',
    settings:
      '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2" fill="white"/><circle cx="16" cy="12" r="2" fill="white"/><circle cx="10" cy="18" r="2" fill="white"/>',
    up: '<path d="m6 14 6-6 6 6"/>',
    down: '<path d="m6 10 6 6 6-6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v1"/>',
    check: '<path d="m5 12 4 4L20 5"/>',
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
    csrf: "",
    metadata: null,
    views: [],
    view: null,
    panel: 0,
    tab: "data",
    results: new Map(),
    generation: 0,
    dirty: new Set(),
    saving: new Set(),
    timers: new Map(),
    recovery: [],
    characterRow: null,
    characterSelection: [],
    newCharacters: [],
  };
  const chartNames = {
    table: "テーブル",
    line: "折れ線グラフ",
    pie: "円グラフ",
    box: "箱ひげ図",
    histogram: "ヒストグラム",
  };
  const sourceNames = {
    artworks: "作品ごと（指定時点）",
    snapshots: "計測ログ（時系列）",
    followers: "フォロワー履歴",
  };
  const aggregates = {
    mean: "平均",
    median: "中央値",
    sum: "合計",
    min: "最小値",
    max: "最大値",
    count: "件数",
  };
  const id = (prefix) =>
    `${prefix}_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;
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
      style: {
        color: "#447869",
        legend: true,
        labels: false,
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
  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(state.csrf ? { "X-CSRF-Token": state.csrf } : {}),
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
  }
  function currentPanel() {
    return state.view?.config.panels[state.panel];
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
    state.dirty.add(state.view.id);
    saveDrafts();
    saveStatus("保存待ち…");
    clearTimeout(state.timers.get(state.view.id));
    const view = state.view;
    state.timers.set(
      view.id,
      setTimeout(() => saveView(view), 650),
    );
    if (render) renderPanels();
  }
  async function saveView(view) {
    if (!view) return;
    if (state.saving.has(view.id) || !state.dirty.has(view.id)) return;
    if (!view.name.trim()) {
      saveStatus("ビュー名を入力してください", true);
      return;
    }
    state.saving.add(view.id);
    state.dirty.delete(view.id);
    saveStatus("保存中…");
    try {
      if (DEMO) {
        store(storageKey("views"), state.views);
        view.revision++;
      } else {
        const saved = await api(
          `/api/analytics/views/${encodeURIComponent(view.id)}`,
          {
            method: "PATCH",
            body: JSON.stringify({
              name: view.name,
              config: clone(view.config),
              revision: view.revision,
            }),
          },
        );
        view.revision = saved.revision;
        view.updated_at = saved.updated_at;
      }
      saveDrafts();
      if (!state.dirty.size) saveStatus("すべて保存済み");
      renderViewList();
    } catch (error) {
      if (error.status === 409) {
        state.recovery = state.recovery.filter((v) => v.id !== view.id);
        state.recovery.push(clone(view));
        openConflict();
      } else state.dirty.add(view.id);
      saveDrafts();
      saveStatus("未保存 · 更新で再試行", true);
      setError(error.message);
      if ($("#settings").open) {
        $("#settings-error").hidden = false;
        $("#settings-error").textContent = error.message;
      }
    } finally {
      state.saving.delete(view.id);
    }
    if (state.dirty.has(view.id) && !$("#page-error").textContent)
      state.timers.set(
        view.id,
        setTimeout(() => saveView(view), 650),
      );
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
      saveStatus("すべて保存済み");
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
        `<span class="avatar">${state.user.id === "demo_a" ? "A" : "B"}</span><label><span class="sr-only">デモ利用者</span><select id="demo-user"><option value="demo_a">デモユーザー A</option><option value="demo_b">デモユーザー B</option></select></label>`;
      $("#demo-user").value = state.user.id;
      $("#demo-user").onchange = async (event) => {
        await saveView(state.view);
        store("xart_demo_user", event.target.value);
        location.reload();
      };
    } else {
      $("#account").innerHTML =
        `<span class="avatar">${esc(state.user.name.slice(0, 1))}</span>${esc(state.user.name)}<br><button id="logout" class="quiet-button">ログアウト</button>`;
      $("#logout").onclick = async () => {
        if (state.saving.size) {
          toast("設定を保存中です。完了後にログアウトしてください");
          return;
        }
        if (state.view) await saveView(state.view);
        if (state.dirty.size) {
          toast("未保存の変更があります。更新して保存を再試行してください");
          return;
        }
        await api("/auth/logout", { method: "POST" });
        location.reload();
      };
    }
  }
  function renderViewList() {
    $("#view-list").innerHTML = state.views
      .map(
        (view) =>
          `<button data-view="${esc(view.id)}" ${state.view?.id === view.id ? 'aria-current="page"' : ""}>${icon(view.config.layout === "dashboard" ? "dashboard" : view.config.panels[0]?.chart)}<span>${esc(view.name)}</span></button>`,
      )
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
    setError("");
    store(storageKey("active"), state.view?.id);
    renderWorkspace();
  }
  function renderWorkspace() {
    const has = !!state.view;
    $("#analysis-content").hidden = !has;
    $("#empty-views").hidden = has;
    renderViewList();
    if (!has) return;
    $("#view-name").value = state.view.name;
    $("#layout").value = state.view.config.layout;
    $("#layout-label").textContent =
      state.view.config.layout === "dashboard"
        ? "ダッシュボード"
        : "単独ビュー";
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
    saveStatus("すべて保存済み");
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
  function renderPanels() {
    if (!state.view) return;
    const generation = ++state.generation;
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
          `<article class="panel ${panel.chart === "table" ? "is-table" : ""}" data-panel="${esc(panel.id)}"><div class="panel-head"><div class="panel-title">${icon(panel.chart)}<h2>${esc(panel.title)}</h2></div><div class="panel-controls"><button class="icon-button" data-move="-1" aria-label="このパネルを前へ">${icon("up")}</button><button class="icon-button" data-move="1" aria-label="このパネルを後ろへ">${icon("down")}</button><button class="icon-button" data-settings aria-label="${esc(panel.title)}の設定">${icon("settings")}</button><button class="icon-button" data-remove aria-label="${esc(panel.title)}を削除">${icon("close")}</button></div></div><div class="panel-meta">${esc(sourceNames[panel.source])} · ${panel.source === "artworks" ? esc(panel.stage) + "時点 · " : ""}${panel.chart === "table" ? "元データ" : ["box", "histogram"].includes(panel.chart) ? "分布" : esc(aggregates[panel.aggregate])} · ${panel.period_days ? "直近" + panel.period_days + "日" : panel.from_date || panel.to_date ? "指定期間" : "全期間"}</div><div class="chart-container"><div class="loading">集計中…</div></div><div class="panel-footnote"></div></article>`,
      )
      .join("");
    $("#panels")
      .querySelectorAll("[data-panel]")
      .forEach((article) => {
        const index = all.findIndex(
            (panel) => panel.id === article.dataset.panel,
          ),
          panel = all[index];
        article.querySelector("[data-settings]").onclick = () =>
          openSettings(index);
        article.querySelectorAll("[data-move]").forEach(
          (button) =>
            (button.onclick = () => {
              const next = index + Number(button.dataset.move);
              if (next < 0 || next >= all.length) return;
              [all[index], all[next]] = [all[next], all[index]];
              state.panel = next;
              changed();
            }),
        );
        article.querySelector('[data-move="-1"]').disabled = index === 0;
        article.querySelector('[data-move="1"]').disabled =
          index === all.length - 1;
        article.querySelector("[data-remove]").onclick = () => {
          if (all.length === 1) {
            toast("ビューには1つ以上の表・グラフが必要です");
            return;
          }
          if (!confirm("このパネルを削除しますか？")) return;
          all.splice(index, 1);
          state.panel = Math.min(state.panel, all.length - 1);
          changed();
        };
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
      if (panel.chart === "table")
        renderTable(article.querySelector(".chart-container"), panel, data);
      else
        AnalysisCharts.render(
          article.querySelector(".chart-container"),
          panel,
          data,
        );
      article.querySelector(".panel-footnote").textContent =
        `対象 ${fmt(data.artwork_count)}${panel.source === "followers" ? "計測" : "作品"} · 未計測 ${fmt(data.missing_stage_count)}作品 · 除外 ${fmt(data.excluded_count)}件${data.warnings.length ? " / " + data.warnings.join(" ") : ""}`;
      if (article === document.querySelector("[data-panel]"))
        renderInsights(data, panel);
    } catch (error) {
      if (generation !== state.generation || !article.isConnected) return;
      article.querySelector(".chart-container").innerHTML =
        `<div class="panel-error">${esc(error.message)}<button class="quiet-button">設定を変更する</button></div>`;
      article.querySelector(".panel-error button").onclick = () =>
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
    let rows = [...data.rows];
    const sort = panel.table_sort || "date",
      direction = panel.table_desc ? -1 : 1;
    rows.sort((a, b) => {
      const av = a[sort],
        bv = b[sort];
      if (av == null) return 1;
      if (bv == null) return -1;
      return (
        direction *
        (typeof av === "number" && typeof bv === "number"
          ? av - bv
          : String(av).localeCompare(String(bv), "ja"))
      );
    });
    const shown = rows.slice(page * 50, (page + 1) * 50),
      columns = panel.columns;
    const cell = (row, key) => {
      if (key === "character" && row.artwork_id)
        return `<button class="character-cell" data-artwork="${esc(row.artwork_id)}" aria-label="${esc(row.title)}のキャラクターを編集">${row.characters.length ? row.characters.map((name) => `<span class="character-chip">${esc(name)}</span>`).join("") : '<span class="missing-value">キャラを設定</span>'}</button>`;
      if (row[key] == null) return '<span class="missing-value">未計測</span>';
      if (key === "title" && row.url && !DEMO)
        return `<a href="/artworks/${encodeURIComponent(row.artwork_id)}">${esc(row[key])}</a>`;
      if (Array.isArray(row[key])) return esc(row[key].join(" / "));
      return esc(typeof row[key] === "number" ? fmt(row[key]) : row[key]);
    };
    host.innerHTML = `<div class="table-scroll"><table><thead><tr>${columns.map((key) => `<th aria-sort="${sort === key ? (panel.table_desc ? "descending" : "ascending") : "none"}"><button data-sort="${esc(key)}">${esc(data.fields[key] || key)} ${sort === key ? (panel.table_desc ? "↓" : "↑") : ""}</button></th>`).join("")}</tr></thead><tbody>${shown.map((row) => `<tr>${columns.map((key) => `<td>${cell(row, key)}</td>`).join("")}</tr>`).join("")}</tbody></table>${!shown.length ? '<p class="panel-empty">条件に一致する作品がありません</p>' : ""}</div><div class="table-pagination"><span>${rows.length ? `${page * 50 + 1}〜${Math.min((page + 1) * 50, rows.length)} / ` : ""}${fmt(rows.length)}行</span><div><button class="quiet-button" data-page="-1" ${page === 0 ? "disabled" : ""}>前へ</button><button class="quiet-button" data-page="1" ${(page + 1) * 50 >= rows.length ? "disabled" : ""}>次へ</button></div></div>`;
    host.querySelectorAll("[data-sort]").forEach(
      (button) =>
        (button.onclick = () => {
          panel.table_desc =
            panel.table_sort === button.dataset.sort
              ? !panel.table_desc
              : false;
          panel.table_sort = button.dataset.sort;
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
    state.panel = index;
    state.tab = "data";
    renderSettings();
    $("#settings").showModal();
  }
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
  function renderSettings() {
    const p = currentPanel();
    if (!p) return;
    $("#settings-title").textContent = p.title;
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
        labelField(
          "パネル名",
          input("title", p.title, "text", 'maxlength="120"'),
        ) +
        labelField("表示形式", select("chart", p.chart, chartNames)) +
        labelField(
          "データの種類",
          select("source", p.source, sourceNames),
          "作品・計測ログ・アカウントの履歴を区別して集計します。",
        );
      if (p.source === "artworks")
        html += labelField(
          "比較する計測時点",
          select(
            "stage",
            p.stage,
            Object.fromEntries(
              state.metadata.stages.map((s) => [s.name, s.name]),
            ),
          ),
          "指定した計測がない作品は未計測とし、集計から除外します。",
        );
      html +=
        labelField(
          "直近の日数（0＝全期間）",
          input("period_days", p.period_days, "number", 'min="0" max="3660"'),
        ) +
        `<div class="field-grid">${labelField("開始日", input("from_date", p.from_date, "date"))}${labelField("終了日", input("to_date", p.to_date, "date"))}</div>`;
      if (!["table", "pie"].includes(p.chart))
        html += `<label class="toggle-label"><input type="checkbox" data-field="compare_previous" ${p.compare_previous ? "checked" : ""}>前の同じ長さの期間と比較</label><p class="settings-help">日付軸では前期間を現在の期間に揃えて重ねます。日数または開始・終了日を指定してください。</p>`;
    } else if (state.tab === "axes") {
      const all = fieldOptions(p, { rowOnly: true }),
        numbers = fieldOptions(p, { numeric: true });
      if (p.chart === "table") {
        html += `<span class="field-label">表示する列</span><div class="check-options">${Object.entries(
          all,
        )
          .map(
            ([key, label]) =>
              `<label><input type="checkbox" data-column="${key}" ${p.columns.includes(key) ? "checked" : ""}>${esc(label)}</label>`,
          )
          .join(
            "",
          )}</div><p class="settings-help">列見出しをタップすると並べ替えできます。元データはキャラクターだけ編集できます。</p>`;
      } else {
        if (p.chart !== "histogram")
          html += labelField("横軸・分類", select("x", p.x, all));
        html += `<div class="settings-field"><span class="field-label">${p.chart === "histogram" ? "分布を見る数値" : "縦軸・数値"}</span><div class="check-options">${Object.entries(
          numbers,
        )
          .map(
            ([key, label]) =>
              `<label><input type="checkbox" data-y="${key}" ${p.y.includes(key) ? "checked" : ""}>${esc(label)}</label>`,
          )
          .join("")}</div></div>`;
        html += labelField(
          "系列・色分け",
          select("series", p.series, { "": "色分けなし", ...all }),
        );
        if (!["box", "histogram"].includes(p.chart))
          html += labelField(
            "集計方法",
            select("aggregate", p.aggregate, aggregates),
          );
        if (p.chart === "histogram")
          html += labelField(
            "ビン数",
            input("bins", p.bins, "number", 'min="2" max="80"'),
          );
        if (p.chart === "line")
          html +=
            labelField(
              "集計後の計算",
              select("transform", p.transform, {
                none: "そのまま",
                delta: "前の観測点からの増加数",
                rate: "前の観測点からの増加率（%）",
                moving_average: "移動平均",
              }),
            ) +
            (p.transform === "moving_average"
              ? labelField(
                  "移動平均の観測点数",
                  input("window", p.window, "number", 'min="2" max="100"'),
                )
              : "");
      }
      if (p.source !== "followers")
        html += labelField(
          "複数キャラの数え方",
          select("allocation", p.allocation, {
            full: "各キャラに全量計上",
            split: "キャラ数で均等配分",
            combination: "組み合わせを1分類にする",
          }),
          "均等配分では件数と合計を配分し、平均・分位数には同じ重みを使います。",
        );
    } else if (state.tab === "filters") {
      html = labelField(
        "グループ同士の条件",
        select("filter_join", p.filter_join, {
          and: "すべて一致（AND）",
          or: "いずれか一致（OR）",
        }),
      );
      html += p.filters
        .map(
          (group, gi) =>
            `<div class="filter-group"><div class="filter-group-head">${select(`filters.${gi}.join`, group.join, { and: "すべて一致", or: "いずれか一致" })}<button class="icon-button" data-remove-group="${gi}" aria-label="条件グループを削除">${icon("close")}</button></div>${group.rules.map((rule, ri) => `<div class="filter-rule">${select(`filters.${gi}.rules.${ri}.field`, rule.field, fieldOptions(p, { rowOnly: true }))}${select(`filters.${gi}.rules.${ri}.op`, rule.op, { eq: "等しい", ne: "異なる", contains: "含む", gt: ">", gte: "≥", lt: "<", lte: "≤", empty: "未設定" })}${input(`filters.${gi}.rules.${ri}.value`, rule.value)}<button data-remove-rule="${gi},${ri}" aria-label="この条件を削除">削除</button></div>`).join("")}<button class="quiet-button" data-add-rule="${gi}">${icon("plus")}条件を追加</button></div>`,
        )
        .join("");
      html +=
        '<button class="quiet-button" id="add-filter-group">' +
        icon("plus") +
        "条件グループを追加</button>";
    } else if (state.tab === "formulas") {
      html =
        '<p class="settings-help">列名・四則演算・条件式と関数を使えます。ゼロ除算や欠測を含む計算結果は未計測として扱います。</p>';
      html += p.formulas
        .map(
          (f, i) =>
            `<div class="formula-card">${labelField("指標の名前", input(`formulas.${i}.label`, f.label))}<p class="settings-help">列キー：<code>${esc(f.key)}</code></p>${labelField("計算のタイミング", select(`formulas.${i}.scope`, f.scope, { row: "1行ごとに計算してから集計", group: "分類ごとに集計して計算" }))}${labelField("計算式", `<textarea data-field="formulas.${i}.expression" aria-label="計算式" maxlength="500" spellcheck="false">${esc(f.expression)}</textarea>`)}<label class="field-label">式に列を挿入</label><select data-insert-formula="${i}" aria-label="式に列を挿入"><option value="">列を選択…</option>${Object.entries(
              fieldOptions(p, { numeric: true }),
            )
              .filter(([key]) => key !== f.key)
              .map(
                ([key, label]) =>
                  `<option value="${esc(key)}">${esc(label)} (${esc(key)})</option>`,
              )
              .join(
                "",
              )}</select><button class="quiet-button danger" data-remove-formula="${i}">この指標を削除</button></div>`,
        )
        .join("");
      html +=
        '<button class="quiet-button" id="add-formula">' +
        icon("plus") +
        '計算指標を追加</button><p class="settings-help">関数：sum / mean / median / min / max / count / abs / round / sqrt / log / log10 / coalesce<br>条件式：likes / impressions * 100 if impressions &gt; 0 else 0</p><span class="field-label">よく使う計算式から追加</span><div class="formula-examples"><button data-example="rate">反応率：likes / impressions * 100</button><button data-example="aggregate">合計から反応率：sum(likes) / sum(impressions) * 100</button><button data-example="speed">時間あたり：likes / elapsed_hours</button></div>';
    } else {
      html =
        labelField(
          "メインカラー",
          input("style.color", p.style.color, "color"),
        ) +
        labelField("横軸ラベル", input("style.x_label", p.style.x_label)) +
        labelField("縦軸ラベル", input("style.y_label", p.style.y_label)) +
        `<div class="field-grid">${labelField("横軸の最小値", input("style.x_min", p.style.x_min, "number", 'step="any" placeholder="自動"'))}${labelField("横軸の最大値", input("style.x_max", p.style.x_max, "number", 'step="any" placeholder="自動"'))}</div><p class="settings-help">横軸範囲は数値軸に適用します。日付はデータの期間で絞り込めます。</p>` +
        `<div class="field-grid">${labelField("縦軸の最小値", input("style.y_min", p.style.y_min, "number", 'step="any" placeholder="自動"'))}${labelField("縦軸の最大値", input("style.y_max", p.style.y_max, "number", 'step="any" placeholder="自動"'))}</div>` +
        labelField(
          "表示順",
          select("style.sort", p.style.sort, {
            x_asc: "横軸の昇順",
            x_desc: "横軸の降順",
            y_desc: "値の大きい順",
            y_asc: "値の小さい順",
          }),
        ) +
        `<label class="toggle-label"><input type="checkbox" data-field="style.legend" ${p.style.legend ? "checked" : ""}>凡例を表示</label><label class="toggle-label"><input type="checkbox" data-field="style.labels" ${p.style.labels ? "checked" : ""}>数値ラベルを表示（折れ線）</label>`;
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
          el.setAttribute("aria-label", label.textContent);
          label.htmlFor = el.id;
        }
      });
    wireSettings();
  }
  let previewTimer;
  function settingsChanged(rerender = false) {
    changed({ render: false });
    clearTimeout(previewTimer);
    previewTimer = setTimeout(renderPanels, 550);
    if (rerender) renderSettings();
  }
  function wireSettings() {
    const p = currentPanel();
    $("#settings-body")
      .querySelectorAll("[data-field]")
      .forEach((el) => {
        const handler = () => {
          const path = el.dataset.field.split(".");
          let target = p;
          path.slice(0, -1).forEach((part) => (target = target[part]));
          const property = path.at(-1);
          const value =
            el.type === "checkbox"
              ? el.checked
              : el.type === "number"
                ? el.value === ""
                  ? ["x_min", "x_max", "y_min", "y_max"].includes(property)
                    ? null
                    : 0
                  : Number(el.value)
                : el.value;
          target[property] = value;
          let structural = false;
          if (el.dataset.field === "source") {
            p.x = p.source === "followers" ? "date" : "character";
            p.y = [p.source === "followers" ? "followers" : "likes"];
            p.series = "";
            p.filters = [];
            p.formulas = [];
            p.columns =
              p.source === "followers"
                ? ["date", "measured_at", "followers"]
                : [
                    "title",
                    "date",
                    "character",
                    "likes",
                    "retweets",
                    "impressions",
                  ];
            p.table_sort = "date";
            structural = true;
          }
          if (el.dataset.field === "chart") {
            p.transform = "none";
            if (["pie", "table"].includes(p.chart)) p.compare_previous = false;
            if (p.chart === "pie") p.y = p.y.slice(0, 1);
            if (p.chart === "histogram") {
              p.x = p.y[0];
              p.series = "";
            }
            structural = true;
          }
          if (el.dataset.field === "transform") structural = true;
          if (el.dataset.field === "title") {
            const i = state.view.config.panels.indexOf(p);
            if (i >= 0) $("#settings-title").textContent = p.title;
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
      .querySelectorAll("[data-y],[data-column]")
      .forEach(
        (el) =>
          (el.onchange = () => {
            const key = el.dataset.y ? "y" : "columns",
              field = el.dataset.y || el.dataset.column;
            p[key] = el.checked
              ? [...p[key], field]
              : p[key].filter((v) => v !== field);
            settingsChanged();
          }),
      );
    $("#add-filter-group")?.addEventListener("click", () => {
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
    $("#settings-body")
      .querySelectorAll("[data-add-rule]")
      .forEach(
        (el) =>
          (el.onclick = () => {
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
            p.filters.splice(Number(el.dataset.removeGroup), 1);
            settingsChanged(true);
          }),
      );
    $("#settings-body")
      .querySelectorAll("[data-remove-rule]")
      .forEach(
        (el) =>
          (el.onclick = () => {
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
            const index = Number(el.dataset.removeFormula),
              key = p.formulas[index].key;
            p.formulas.splice(index, 1);
            p.y = p.y.filter((v) => v !== key);
            if (!p.y.length)
              p.y = [p.source === "followers" ? "followers" : "likes"];
            p.columns = p.columns.filter((v) => v !== key);
            settingsChanged(true);
          }),
      );
    $("#settings-body")
      .querySelectorAll("[data-insert-formula]")
      .forEach(
        (el) =>
          (el.onchange = () => {
            p.formulas[Number(el.dataset.insertFormula)].expression += el.value;
            settingsChanged(true);
          }),
      );
  }
  function renderCharacterOptions() {
    const names = [
      ...new Set([
        ...state.metadata.characters,
        ...state.newCharacters,
        ...state.characterSelection,
      ]),
    ].sort((a, b) => a.localeCompare(b, "ja"));
    $("#character-options").innerHTML = names
      .map(
        (name) =>
          `<label><input type="checkbox" value="${esc(name)}" ${state.characterSelection.includes(name) ? "checked" : ""}>${esc(name)}</label>`,
      )
      .join("");
    $("#character-options")
      .querySelectorAll("input")
      .forEach(
        (el) =>
          (el.onchange = () => {
            state.characterSelection = el.checked
              ? [...state.characterSelection, el.value]
              : state.characterSelection.filter((name) => name !== el.value);
          }),
      );
  }
  function openCharacters(row) {
    state.characterRow = row;
    state.characterSelection = [...row.characters];
    state.newCharacters = [];
    $("#character-status").textContent = "";
    $("#character-name").value = "";
    renderCharacterOptions();
    $("#character-dialog").showModal();
  }
  $("#add-character-form").onsubmit = (event) => {
    event.preventDefault();
    const name = $("#character-name").value.trim();
    if (!name) return;
    state.newCharacters.push(name);
    if (!state.characterSelection.includes(name))
      state.characterSelection.push(name);
    $("#character-name").value = "";
    renderCharacterOptions();
  };
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
      toast("ログインするか、サンプルデータでお試しください");
      return;
    }
    $("#create-dialog").showModal();
  };
  $("#close-settings").onclick = () => $("#settings").close();
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
    state.view.name = $("#view-name").value;
    changed({ render: false });
  };
  $("#layout").onchange = () => {
    state.view.config.layout = $("#layout").value;
    changed({ render: false });
    renderWorkspace();
  };
  $("#add-panel").onclick = () => {
    if (state.view.config.panels.length >= 12) {
      toast("1ビューには12パネルまで追加できます");
      return;
    }
    state.view.config.panels.push(
      panelDefaults({ chart: "table", title: "新しいテーブル" }),
    );
    state.panel = state.view.config.panels.length - 1;
    changed();
    openSettings(state.panel);
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
    if (state.saving.has(state.view?.id)) {
      toast("設定を保存中です。完了後に削除してください");
      return;
    }
    if (!confirm("このビューを削除しますか？ 元データは削除されません。"))
      return;
    const view = state.view;
    try {
      clearTimeout(state.timers.get(view.id));
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
    if (state.recovery.length) {
      openConflict();
      return;
    }
    setError("");
    for (const view of state.views)
      if (state.dirty.has(view.id)) await saveView(view);
    if (state.view) renderPanels();
  };
  window.addEventListener("online", () => {
    setError("");
    for (const view of state.views)
      if (state.dirty.has(view.id)) saveView(view);
  });
  window.addEventListener("beforeunload", (event) => {
    saveDrafts();
    if (state.dirty.size && !DEMO) {
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
        const overrides = getStored("xart_demo_characters", {});
        state.metadata.characters = [
          ...new Set([
            ...state.metadata.characters,
            ...Object.values(overrides).flat(),
          ]),
        ];
      } else {
        const auth = await api("/auth/me");
        state.user = auth.user;
        state.csrf = auth.csrf;
        const [metadata, views] = await Promise.all([
          api("/api/analytics/metadata"),
          api("/api/analytics/views"),
        ]);
        state.metadata = metadata;
        state.views = views.views;
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
      saveStatus(DEMO ? "ブラウザーに保存" : "すべて保存済み");
      for (const view of state.views)
        if (state.dirty.has(view.id)) saveView(view);
      openConflict();
    } catch (error) {
      if (!state.user) {
        $("#login-gate").hidden = false;
        $("#login-description").textContent =
          error.status === 503
            ? "Googleログインの接続設定が必要です。先にサンプルデータで操作を確認できます。"
            : "許可されたGoogleアカウントでログインしてください。";
      } else setError(error.message);
    }
  }
  init();
})();
