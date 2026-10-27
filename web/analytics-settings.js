/* Progressive, non-modal editor; saved configuration remains version 1. */
window.AnalyticsSettings = function (dependencies) {
  const { $, esc, icon, state, chartCards,
    stageLabel, currentPanel, rememberChange, changed, updateSettingsHeader, updateUndoButton,
    updateSaveState, renderPanels, confirmSourceChange, applySource, applyChart, resetPanel,
    duplicatePanel, toast, id, fieldLabel, periodLabel, panelFilterCount } = dependencies;
  const sourceLabels = { artworks: "作品", snapshots: "ログ", followers: "フォロワー" };
  const aggregateLabels = { mean:"平均", median:"中央値", sum:"合計", min:"最小", max:"最大", count:"件数" };
  const periodModes = new Map();
  let helpIndex = 0;
  const short = (text, max = 20) => [...String(text)].length > max ? [...String(text)].slice(0,max - 1).join("") + "…" : String(text);
  const input = (path, value, type = "text", attrs = "") => `<input data-field="${esc(path)}" type="${type}" value="${esc(value ?? "")}" ${attrs}>`;
  const select = (path, value, options) => `<select data-field="${esc(path)}">${value != null && !(String(value) in options) ? `<option value="${esc(value)}" selected disabled>${esc(value)}（変更）</option>` : ""}${Object.entries(options).map(([key,label]) => `<option value="${esc(key)}" ${String(value) === key ? "selected" : ""}>${esc(label)}</option>`).join("")}</select>`;
  function help(label, text, markup = false) {
    if (!text) return "";
    const key = `setting-help-${helpIndex++}`;
    return `<button type="button" class="setting-info" popovertarget="${key}" aria-label="${esc(label)}の説明">${icon("info")}</button><div id="${key}" class="setting-popover" popover>${markup ? text : esc(text)}</div>`;
  }
  function field(label, content, description = "", control = "") {
    const tag = content.startsWith("<fieldset") ? "span" : "label";
    return `<div class="settings-field" ${control ? `data-setting-control="${esc(control)}"` : ""}><div class="setting-label"><${tag}>${esc(label)}</${tag}></div><div class="setting-input">${content}${help(label,description)}</div></div>`;
  }
  const toggle = (path, value, label, description = "") => `<div class="settings-field" data-setting-control="${esc(path)}"><div class="setting-label"><span>${esc(label)}</span>${help(label,description)}</div><label class="toggle-label"><input type="checkbox" data-field="${esc(path)}" aria-label="${esc(label)}" ${value ? "checked" : ""}><span class="toggle-switch"></span><span class="sr-only">${esc(label)}</span></label></div>`;
  function fieldOptions(panel, { numeric = false, rowOnly = false } = {}) {
    const options = {};
    state.metadata.sources[panel.source].filter(field => !numeric || field.type === "number").forEach(field => options[field.key] = field.label);
    panel.formulas.filter(formula => !rowOnly || formula.scope === "row").forEach(formula => options[formula.key] = formula.label);
    return options;
  }
  function chartCardsHtml(panel) {
    return `<fieldset class="format-switch" aria-label="形式" data-setting-control="chart">${Object.entries(chartCards).map(([key,item]) => `<label class="chart-card ${panel.chart === key ? "is-selected" : ""}" title="${esc(item.name)}"><input type="radio" name="panel-chart" data-chart-card value="${key}" aria-label="${esc(item.name)}" ${panel.chart === key ? "checked" : ""}>${icon(key)}<span class="sr-only">${esc(item.name)}</span></label>`).join("")}</fieldset>`;
  }
  function sourceCardsHtml(panel) {
    return `<fieldset class="source-switch" aria-label="種類">${Object.entries(sourceLabels).map(([key,label]) => `<label class="source-card ${panel.source === key ? "is-selected" : ""}"><input type="radio" name="panel-source" data-source-card value="${key}" aria-label="${label}" ${panel.source === key ? "checked" : ""}><span>${label}</span></label>`).join("")}</fieldset>`;
  }
  function dataHtml(p) {
    const dates = p.from_date || p.to_date;
    const custom = Boolean(dates) || (periodModes.get(p.id) ?? false);
    let html = field("種類", sourceCardsHtml(p), "作品は指定時点の1作品、ログは1回の計測、フォロワーはアカウント全体の1計測です。期間は作品・ログが投稿日、フォロワーが計測日を基準にします。", "source");
    if (p.source === "artworks") html += field("時点", select("stage",p.stage,Object.fromEntries(state.metadata.stages.map(stage => [stage.name,stage.name]))), "未計測の作品は0にせず除外します。", "stage");
    html += field("期間", `<fieldset class="period-switch" aria-label="期間">${[[7,"7日"],[30,"30日"],[90,"90日"],[0,"全期間"]].map(([days,label]) => `<button type="button" data-preset-days="${days}" aria-pressed="${!custom && !dates && p.period_days === days}">${label}</button>`).join("")}<button type="button" data-custom-period aria-pressed="${custom}">指定</button></fieldset>`, "", "period");
    if (custom) html += `<div class="custom-period">${field("開始",input("from_date",p.from_date,"date"))}${field("終了",input("to_date",p.to_date,"date"))}</div>`;
    return html;
  }
  function metricHtml(p) {
    const single = ["pie","scatter","box","histogram"].includes(p.chart);
    const numbers = fieldOptions(p,{ numeric:true, rowOnly:["scatter","box","histogram"].includes(p.chart) });
    const label = ["pie","box","histogram"].includes(p.chart) ? "指標" : "縦軸";
    if (single) return field(label, `<select data-single-y aria-label="${label}">${!(p.y[0] in numbers) ? `<option value="${esc(p.y[0])}" selected disabled>${esc(p.y[0])}（変更）</option>` : ""}${Object.entries(numbers).map(([key,text]) => `<option value="${esc(key)}" ${key === p.y[0] ? "selected" : ""}>${esc(text)}</option>`).join("")}</select>`, "指標を変更すると、選んだ1指標を使用します。", "y");
    return field(label, `<div class="metric-picker"><div class="metric-chips">${p.y.map(key => `<button type="button" data-remove-y="${esc(key)}" aria-label="${esc(fieldLabel(p,key))}を削除" ${p.y.length <= 1 ? "disabled" : ""}>${esc(fieldLabel(p,key))} ×</button>`).join("")}</div><select data-add-y aria-label="指標を追加" ${p.y.length >= 6 ? "disabled" : ""}><option value="">＋ 追加</option>${Object.entries(numbers).filter(([key]) => !p.y.includes(key)).map(([key,text]) => `<option value="${esc(key)}">${esc(text)}</option>`).join("")}</select></div>`, "最大6指標です。", "y");
  }
  function axesHtml(p) {
    const rows = fieldOptions(p,{rowOnly:true});
    if (p.chart === "table") {
      const columns = `<div class="metric-chips">${p.columns.map(key => `<button type="button" data-remove-column="${esc(key)}" aria-label="${esc(rows[key] || key)}列を外す">${esc(rows[key] || key)} ×</button>`).join("")}</div><select data-add-column aria-label="表示列を追加"><option value="">＋ 追加</option>${Object.entries(rows).filter(([key]) => !p.columns.includes(key)).map(([key,label]) => `<option value="${esc(key)}">${esc(label)}</option>`).join("")}</select>`;
      return field("列",columns,"列の順番は保存した選択順です。","columns") + (p.source !== "followers" ? toggle("show_images",p.show_images !== false,"写真") : "");
    }
    let html = "";
    if (p.chart !== "histogram") {
      const options = p.chart === "scatter" ? Object.fromEntries(Object.entries(rows).filter(([key]) => state.metadata.sources[p.source].some(field => field.key === key && ["number","date"].includes(field.type)) || p.formulas.some(formula => formula.key === key && formula.scope === "row"))) : rows;
      html += field(["pie","box"].includes(p.chart) ? "分類" : "横軸",select("x",p.x,options),"", "x");
    }
    html += metricHtml(p);
    if (p.chart === "histogram") html += field("区間数",input("bins",p.bins,"number",'min="2" max="80"'),"分布を区切る区間数です。","bins");
    return html;
  }
  function styleHtml(p) {
    const palette = ["#447869","#20221e","#f2785d","#3b82f6","#8b5cf6","#eab308","#ec4899"];
    const colors = help("配色", '<div class="palette-swatches">' + palette.map(color => `<button type="button" data-color-swatch="${color}" style="background:${color}" aria-label="カラー ${color}"></button>`).join("") + '</div>', true);
    return (p.chart !== "box" ? field("色",input("style.color",p.style.color,"color")+colors) : "") + toggle("style.legend",p.style.legend,"凡例") + (["line","bar"].includes(p.chart) ? toggle("style.labels",p.style.labels,"数値") : "");
  }
  function tableDetailsHtml(p) {
    const rows = fieldOptions(p,{rowOnly:true}), sorts = AnalysisTable.sortsFor(p);
    let html = field("グループ",select("table_group",p.table_group || "",{"":"なし",...rows}),"複数値は個別または組み合わせでまとめます。");
    if (p.table_group) {
      html += field("グループ順",select("table_group_order",p.table_group_order,{asc:"昇順",desc:"降順"}));
      const kind = state.metadata.sources[p.source].find(field => field.key === p.table_group)?.type;
      if (kind === "date") html += field("日付単位",select("table_group_dates",p.table_group_dates,{day:"日",week:"週",month:"月",year:"年",exact:"日時"}),"日本時間で区切り、週は月曜に始まります。");
      if (["character","tags"].includes(p.table_group)) html += field("複数値",select("table_group_multivalue",p.table_group_multivalue,{individual:"個別",combination:"組み合わせ"}));
    }
    html += `<div class="table-sort-list" aria-label="並べ替え">${sorts.map((sort,index) => {
      const options = Object.fromEntries(Object.entries(rows).filter(([key]) => key === sort.field || !sorts.some(other => other.field === key)));
      return `<div class="table-sort-rule">${field(`項目${index+1}`,select(`table_sorts.${index}.field`,sort.field,options))}${toggle(`table_sorts.${index}.desc`,sort.desc,"降順")}<div class="sort-controls"><button type="button" data-sort-move="${index},-1" aria-label="並べ替え条件${index+1}を上へ" ${index === 0 ? "disabled" : ""}>${icon("up")}</button><button type="button" data-sort-move="${index},1" aria-label="並べ替え条件${index+1}を下へ" ${index === sorts.length-1 ? "disabled" : ""}>${icon("down")}</button><button type="button" data-sort-remove="${index}" aria-label="並べ替え条件${index+1}を削除">${icon("close")}</button></div></div>`;
    }).join("")}<button type="button" id="add-table-sort" class="quiet-button" aria-label="並べ替え条件を追加" ${sorts.length >= Math.min(5,Object.keys(rows).length) ? "disabled" : ""}>＋ 追加</button></div>`;
    html += help("列の操作", '<button type="button" id="check-all-cols">全選択</button><button type="button" id="check-none-cols">全解除</button><button type="button" id="check-default-cols">標準列</button>',true);
    return html;
  }
  function detailsHtml(p) {
    let html = field("名前",input("title",p.title,"text",'maxlength="120"')) + field("日数",input("period_days",p.period_days,"number",'min="0" max="3660"'),"0は全期間で、日付の指定がある場合は日付を優先します。");
    if (p.chart === "table") return html + tableDetailsHtml(p);
    const rows = fieldOptions(p,{rowOnly:true});
    if (p.chart !== "pie") html += field("系列",select("series",p.series,{"":"なし",...rows}),"項目ごとに色分けします。");
    if (["line","bar","pie"].includes(p.chart)) html += field("集計",select("aggregate",p.aggregate,aggregateLabels),"同じ分類のデータをまとめる方法です。");
    if (p.chart === "line") {
      html += field("変換",select("transform",p.transform,{none:"なし",delta:"増加数",rate:"増加率",moving_average:"移動平均"}));
      if (p.transform === "moving_average") html += field("点数",input("window",p.window,"number",'min="2" max="100"'),"移動平均に使用する観測点数です。");
    }
    if (["line","bar","scatter"].includes(p.chart) && p.source !== "followers") html += field("配分",select("allocation",p.allocation,p.chart === "scatter" ? {full:"全量",combination:"組み合わせ"} : {full:"全量",split:"均等",combination:"組み合わせ"}),"全量は各キャラに同じ値、均等はキャラ数で分割、組み合わせは共演ごとの集計です。");
    if (!["table","pie","scatter"].includes(p.chart)) html += toggle("compare_previous",p.compare_previous,"前期間比較","直前の同じ長さの期間と比較します。");
    if (p.chart === "scatter") html += toggle("show_images",p.show_images !== false,"作品カード");
    if (p.chart !== "pie") {
      html += field("横軸名",input("style.x_label",p.style.x_label,"text",'maxlength="100"')) + field("縦軸名",input("style.y_label",p.style.y_label,"text",'maxlength="100"'));
      if (p.chart !== "bar") html += field("横軸最小",input("style.x_min",p.style.x_min,"number",'step="any"')) + field("横軸最大",input("style.x_max",p.style.x_max,"number",'step="any"'));
      html += field("縦軸最小",input("style.y_min",p.style.y_min,"number",'step="any"')) + field("縦軸最大",input("style.y_max",p.style.y_max,"number",'step="any"'));
      for (const [axis,label] of [["x","横軸間隔"],["y","縦軸間隔"]]) {
        const interval = p.style[`${axis}_tick_interval`];
        html += field(label,`<select data-tick-mode="${axis}" aria-label="${label}"><option value="auto" ${interval == null ? "selected" : ""}>自動</option><option value="manual" ${interval != null ? "selected" : ""}>指定</option></select>`);
        if (interval != null) html += field(`${axis === "x" ? "横軸" : "縦軸"}間隔値`,input(`style.${axis}_tick_interval`,interval,"number",'min="0" step="any"'));
      }
      if (p.style.x_tick_interval != null && state.metadata.sources[p.source].some(field => field.key === p.x && field.type === "date")) html += field("単位",select("style.x_tick_unit",p.style.x_tick_unit || "day",{day:"日",hour:"時間",minute:"分",second:"秒"}));
    }
    return html + field("表示順",select("style.sort",p.style.sort,{x_asc:"横軸昇順",x_desc:"横軸降順",y_desc:"値の降順",y_asc:"値の昇順"}));
  }
  function ruleSummary(p, rule) {
    const operators = {eq:"=",ne:"≠",contains:"含む",gt:">",gte:"≥",lt:"<",lte:"≤",empty:"未設定"};
    return `${fieldLabel(p,rule.field)} ${operators[rule.op] || rule.op} ${rule.value ?? ""}`;
  }
  function filtersHtml(p) {
    if (!panelFilterCount(p)) return '<button type="button" id="add-filter-group" class="quiet-button">＋ 追加</button>';
    return (p.filters.length > 1 ? field("結合",select("filter_join",p.filter_join,{and:"AND",or:"OR"})) : "") + p.filters.map((group,gi) => `<div class="filter-group"><div class="filter-group-head">${group.rules.length > 1 ? select(`filters.${gi}.join`,group.join,{and:"AND",or:"OR"}) : ""}<button type="button" data-remove-group="${gi}" aria-label="条件グループを削除">${icon("close")}</button></div>${group.rules.map((rule,ri) => `<details class="filter-rule" data-rule="${gi},${ri}"><summary>${esc(short(ruleSummary(p,rule),32))}</summary><div class="filter-rule-editor">${field("項目",select(`filters.${gi}.rules.${ri}.field`,rule.field,fieldOptions(p,{rowOnly:true})))}${field("条件",select(`filters.${gi}.rules.${ri}.op`,rule.op,{eq:"=",ne:"≠",contains:"含む",gt:">",gte:"≥",lt:"<",lte:"≤",empty:"未設定"}))}${rule.op !== "empty" ? field("値",input(`filters.${gi}.rules.${ri}.value`,rule.value,"text",'maxlength="1000"')) : ""}<button type="button" data-remove-rule="${gi},${ri}" aria-label="この条件を削除">削除</button></div></details>`).join("")}<button type="button" class="quiet-button" data-add-rule="${gi}" ${group.rules.length >= 20 ? "disabled" : ""}>＋ 追加</button></div>`).join("") + `<button type="button" id="add-filter-group" class="quiet-button" ${p.filters.length >= 10 ? "disabled" : ""}>＋ 追加</button>`;
  }
  function formulasHtml(p) {
    const menu = `<button type="button" id="add-formula" class="quiet-button" popovertarget="formula-add-menu" ${p.formulas.length >= 10 ? "disabled" : ""}>＋ 追加</button><div id="formula-add-menu" class="setting-popover formula-add-menu" popover><button type="button" data-new-formula>新規</button><button type="button" data-example="rate">反応率</button><button type="button" data-example="aggregate">合計率</button><button type="button" data-example="speed">時間あたり</button></div>`;
    return p.formulas.map((formula,index) => `<div class="formula-card"><button type="button" data-remove-formula="${index}" aria-label="この指標を削除">${icon("close")}</button>${field("指標名",input(`formulas.${index}.label`,formula.label,"text",'maxlength="100"'))}${field("計算",select(`formulas.${index}.scope`,formula.scope,{row:"行ごと",group:"集計後"}))}${field("式",`<textarea data-field="formulas.${index}.expression" maxlength="500" spellcheck="false">${esc(formula.expression)}</textarea>`,"四則演算、条件式、sum・mean・median・min・max・count・abs・round・sqrt・log・coalesceを使えます。")}${field("列挿入",`<select data-insert-formula="${index}" aria-label="列挿入"><option value="">選択</option>${Object.entries(fieldOptions(p,{numeric:true})).filter(([key]) => key !== formula.key).map(([key,label]) => `<option value="${esc(key)}">${esc(label)}</option>`).join("")}</select>`)}</div>`).join("") + menu;
  }
  function compatibilityHtml(p) {
    const items = [];
    if (p.chart !== "line" && p.transform !== "none") items.push(["transform","変換を解除"]);
    if (["table","pie","scatter"].includes(p.chart) && p.compare_previous) items.push(["compare_previous","比較を解除"]);
    if (p.chart === "pie" && p.y.length > 1) items.push(["y","指標を1つに"]);
    return items.map(([key,label]) => `<button type="button" class="quiet-button" data-resolve-chart="${key}">${label}</button>${help(label,"保持した設定はこの形式で使えません。解除するか元の形式へ戻してください。")}`).join("");
  }
  function sectionDefinitions(p) {
    return [
      ["format","形式",chartCards[p.chart].name,true,() => chartCardsHtml(p)+compatibilityHtml(p)],
      ["data","データ",`${sourceLabels[p.source]}${p.source === "artworks" ? " · "+p.stage : ""} · ${periodLabel(p).replace("直近","")}`,true,() => dataHtml(p)],
      ["axes","軸",p.chart === "table" ? `${p.columns.length}列` : p.y.map(key => fieldLabel(p,key)).join(" · "),true,() => axesHtml(p)],
      ["filters","絞り込み",`${panelFilterCount(p)}件`,p.filters.length > 0,() => filtersHtml(p)],
      ...(p.chart === "table" ? [] : [["style","見た目",p.style.legend ? "凡例あり" : "凡例なし",false,() => styleHtml(p)]]),
      ["advanced","計算式",`${p.formulas.length}件`,false,() => formulasHtml(p)],
      ["details","詳細",p.chart === "table" ? `${AnalysisTable.sortsFor(p).length}条件${p.table_group ? " · "+fieldLabel(p,p.table_group) : ""}` : `${aggregateLabels[p.aggregate]}${p.series ? " · "+fieldLabel(p,p.series) : ""}${p.transform !== "none" ? " · 変換" : ""}`,false,() => detailsHtml(p)],
    ];
  }
  function closeSettings() {
    const wasOpen = !$("#settings").hidden;
    const pendingPreview = previewTimer != null;
    clearTimeout(previewTimer);
    previewTimer = null;
    $("#settings").querySelectorAll("[popover]:popover-open").forEach(popover => popover.hidePopover());
    $("#settings").hidden = true;
    $("#views-workspace").classList.remove("settings-open");
    document.body.classList.remove("has-settings");
    // Apply the last edit before returning to chart controls. A delayed rebuild
    // after closing could otherwise detach an open menu or active gesture.
    if (wasOpen && pendingPreview) renderPanels();
    if (wasOpen) document.querySelector("[data-panel='"+currentPanel()?.id+"'] [data-settings]")?.focus({preventScroll:true});
    window.dispatchEvent(new Event("resize"));
  }
  function openSettings(index) {
    state.panel = index;
    state.sections = {};
    $("#settings-body").innerHTML = "";
    $("#settings-body").scrollTop = 0;
    $("#settings").hidden = false;
    $("#views-workspace").classList.add("settings-open");
    document.body.classList.add("has-settings");
    renderSettings(); updatePreviewPosition(); updateSaveState(); updateUndoButton();
    if (innerWidth >= 1024) document.querySelector("[data-panel='"+currentPanel()?.id+"']")?.scrollIntoView({block:"start",behavior:"instant"});
    window.dispatchEvent(new Event("resize"));
  }
  function renderSettings() {
    const p = currentPanel();
    if (!p || $("#settings").hidden) return;
    const host = $("#settings-body"), scroll = host.scrollTop, activeField = document.activeElement?.dataset.field;
    host.querySelectorAll("details[data-section]").forEach(section => state.sections[section.dataset.section] = section.open);
    const openRules = new Set([...host.querySelectorAll("details[data-rule][open]")].map(details => details.dataset.rule));
    helpIndex = 0;
    updateSettingsHeader(p); selectPreview();
    $("#settings-lock-message").hidden = !state.view.locked;
    host.innerHTML = sectionDefinitions(p).map(([key,title,summary,opened,html]) => `<details data-section="${key}" ${state.sections[key] ?? opened ? "open" : ""}><summary><strong>${title}</strong><span>${esc(short(summary))}</span></summary><div class="settings-section-content">${html()}</div></details>`).join("") + '<div class="settings-panel-actions"><button type="button" id="reset-panel">リセット</button><button type="button" id="duplicate-panel">複製</button><button type="button" id="delete-panel" class="danger">削除</button></div>';
    host.querySelectorAll(".settings-field").forEach((container,index) => {
      const label = container.querySelector(".setting-label > label"), el = container.querySelector("input,select,textarea");
      if (label && el && el.type !== "radio") { el.id = `setting-${index}`; el.setAttribute("aria-label",label.textContent); label.htmlFor = el.id; }
    });
    host.querySelectorAll("details[data-rule]").forEach(details => { if (openRules.has(details.dataset.rule)) details.open = true; });
    host.querySelectorAll("details").forEach(details => {
      const sync = () => details.querySelector(":scope > summary")?.setAttribute("aria-expanded",String(details.open));
      details.addEventListener("toggle",sync); sync();
    });
    wireSettings();
    $("#reset-panel").onclick = () => resetPanel(state.panel);
    $("#duplicate-panel").onclick = () => duplicatePanel(state.panel);
    $("#duplicate-panel").disabled = state.view.config.panels.length >= 12;
    $("#delete-panel").disabled = state.view.config.panels.length <= 1;
    $("#delete-panel").onclick = () => $("#panels [data-panel='"+p.id+"'] [data-remove]")?.click();
    if (state.view.locked) host.querySelectorAll("input,select,textarea,button").forEach(el => { if (!el.classList.contains("setting-info")) el.disabled = true; });
    host.scrollTop = scroll;
    if (activeField) [...host.querySelectorAll("[data-field]")].find(el => el.dataset.field === activeField)?.focus({preventScroll:true});
    updateUndoButton();
  }
  let previewTimer;
  function settingsChanged(rerender = false) {
    changed({ render: false });
    updateSettingsHeader();
    updateUndoButton();
    clearTimeout(previewTimer);
    previewTimer = setTimeout(() => {
      previewTimer = null;
      renderPanels();
    }, 350);
    if (rerender) renderSettings();
    else updateSectionSummaries();
  }
  function wireSettings() {
    const p = currentPanel();
    $("#settings-body [data-custom-period]")?.addEventListener("click", () => { periodModes.set(p.id,true); renderSettings(); });
    $("#settings-body").querySelectorAll("[data-resolve-chart]").forEach(button => button.onclick = () => {
      if (state.view.locked) return;
      rememberChange("chart-compatibility");
      const field = button.dataset.resolveChart;
      if (field === "y") p.y = p.y.slice(0,1);
      else p[field] = field === "transform" ? "none" : false;
      settingsChanged(true);
    });
    $("#settings-body [data-add-column]")?.addEventListener("change", event => { if (!event.target.value || p.columns.length >= 25) return; rememberChange("columns"); p.columns.push(event.target.value); settingsChanged(true); });
    $("#settings-body").querySelectorAll("[data-remove-column]").forEach(button => button.onclick = () => { rememberChange("columns"); p.columns = p.columns.filter(key => key !== button.dataset.removeColumn); settingsChanged(true); });
    $("#settings-body [data-add-y]")?.addEventListener("change", (event) => { if (!event.target.value || p.y.length >= 6) return; rememberChange("y"); p.y.push(event.target.value); settingsChanged(true); });
    $("#settings-body [data-single-y]")?.addEventListener("change", (event) => { rememberChange("y"); p.y = [event.target.value]; settingsChanged(true); });
    $("#settings-body").querySelectorAll("[data-remove-y]").forEach(button => button.onclick = () => { rememberChange("y"); if (p.y.length <= 1) return; p.y = p.y.filter(key => key !== button.dataset.removeY); settingsChanged(true); });
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
          if (state.view.locked) return;
          rememberChange(el.dataset.field);
          const path = el.dataset.field.split(".");
          if (path[0] === "table_sorts" && !p.table_sorts) p.table_sorts = AnalysisTable.sortsFor(p).map(sort => ({ ...sort }));
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
          if (property === "scope" || property === "op" || el.dataset.field === "x") structural = true;
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
    $("#settings-body")
      .querySelectorAll("[data-preset-days]")
      .forEach((btn) => {
        btn.onclick = () => {
          rememberChange("period_days");
          const days = Number(btn.dataset.presetDays);
          periodModes.set(p.id,false);
          p.period_days = days;
          p.from_date = ""; p.to_date = "";
          const inputEl = $("#settings-body [data-field='period_days']");
          if (inputEl) inputEl.value = days;
          settingsChanged(true);
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
    $("#add-filter-group")?.addEventListener("click", () => {
      rememberChange("filters");
      if (!panelFilterCount(p)) p.filters = [];
      if (p.filters.length >= 10) return;
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
      state.sections.filters = true;
      settingsChanged(true);
      $("#settings-body .filter-group:last-of-type .filter-rule")?.setAttribute("open", "");
    });
    $("#add-table-sort")?.addEventListener("click", () => {
      rememberChange("table_sorts");
      if (!p.table_sorts) p.table_sorts = AnalysisTable.sortsFor(p).map(sort => ({ ...sort }));
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
            if (!p.table_sorts) p.table_sorts = AnalysisTable.sortsFor(p).map(sort => ({ ...sort }));
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
            if (!p.table_sorts) p.table_sorts = AnalysisTable.sortsFor(p).map(sort => ({ ...sort }));
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
            if (p.filters[Number(el.dataset.addRule)].rules.length >= 20) return;
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
            if (!p.filters[gi].rules.length) p.filters.splice(gi, 1);
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
    $("#settings-body [data-new-formula]")?.addEventListener("click", () => addFormula());
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

  function updatePreviewPosition() {
    document.body.style.setProperty("--editor-preview-top", `${Math.ceil($(".workspace-topbar").getBoundingClientRect().height) + 8}px`);
  }
  if (typeof ResizeObserver !== "undefined") new ResizeObserver(updatePreviewPosition).observe($(".workspace-topbar"));
  let handleStart;
  let handleDragged = false;
  $("#sheet-handle").onclick = () => {
    if (handleDragged) { handleDragged = false; return; }
    const expanded = document.body.classList.toggle("sheet-expanded");
    $("#sheet-handle").setAttribute("aria-expanded", String(expanded));
    window.dispatchEvent(new Event("resize"));
  };
  $("#sheet-handle").onpointerdown = event => { handleDragged = false; handleStart = event.clientY; event.currentTarget.setPointerCapture(event.pointerId); };
  $("#sheet-handle").onpointerup = event => {
    if (handleStart == null) return;
    const delta = event.clientY - handleStart; handleStart = null; handleDragged = Math.abs(delta) > 20;
    if (delta > 100) { closeSettings(); event.preventDefault(); }
    else if (Math.abs(delta) > 20) { document.body.classList.toggle("sheet-expanded", delta < 0); $("#sheet-handle").setAttribute("aria-expanded", String(delta < 0)); window.dispatchEvent(new Event("resize")); event.preventDefault(); }
  };
  function selectPreview() {
    document.querySelectorAll("[data-panel]").forEach(article => article.classList.toggle("is-selected", article.dataset.panel === currentPanel()?.id));
  }
  function updateSectionSummaries() {
    const p = currentPanel();
    if (!p) return;
    sectionDefinitions(p).forEach(([key,,summary]) => { const el = $("#settings-body [data-section='"+key+"'] > summary span"); if (el) el.textContent = short(summary); });
    $("#settings-body").querySelectorAll("[data-rule]").forEach(details => {
      const [group,index] = details.dataset.rule.split(",").map(Number), rule = p.filters[group]?.rules[index];
      if (rule) details.querySelector("summary").textContent = short(ruleSummary(p,rule),32);
    });
  }
  function clearSettingsErrors() {
    $("#settings-body").querySelectorAll(".field-error").forEach(el => el.remove());
    $("#settings-body").querySelectorAll("[aria-invalid]").forEach(el => { el.removeAttribute("aria-invalid"); el.removeAttribute("aria-describedby"); });
  }
  function showSettingsErrors(error) {
    clearSettingsErrors();
    const details = Array.isArray(error.detail) ? error.detail : [{msg:error.message,loc:[]}];
    const seen = new Set();
    details.forEach((detail,index) => {
      let path = (detail.loc || []).filter(key => key !== "body");
      const panelIndex = path.indexOf("panels");
      if (panelIndex >= 0) { if (Number(path[panelIndex+1]) !== state.panel) return; path = path.slice(panelIndex+2); }
      if (path[0] === "panel") path.shift();
      let el = [...$("#settings-body").querySelectorAll("[data-field]")].find(input => input.dataset.field === path.join("."));
      if (!el) {
        const key = /横軸の最小値/.test(detail.msg) ? "style.x_min" : /縦軸の最小値/.test(detail.msg) ? "style.y_min" : /前期間比較/.test(detail.msg) ? "compare_previous" : /ステージ/.test(detail.msg) ? "stage" : /開始|終了|日付/.test(detail.msg) ? "from_date" : /変換|移動平均|増加/.test(detail.msg) ? "transform" : /円グラフ|縦軸|数値/.test(detail.msg) ? "y" : /横軸|系列/.test(detail.msg) ? "x" : /計算/.test(detail.msg) ? "formulas.0.expression" : /表示列/.test(detail.msg) ? "columns" : "";
        el = key === "y" ? $("#settings-body [data-single-y],#settings-body [data-add-y]") : key === "columns" ? $("#settings-body [data-add-column]") : [...$("#settings-body").querySelectorAll("[data-field]")].find(input => input.dataset.field === key);
      }
      el ||= $("#settings-body [data-resolve-chart],#settings-body [data-chart-card]");
      if (!el || seen.has(el)) return;
      seen.add(el);
      for (let at = el.parentElement; at && at.id !== "settings-body"; at = at.parentElement) if (at.tagName === "DETAILS") at.open = true;
      const message = document.createElement("p"); message.className = "field-error error-message"; message.id = `setting-error-${index}`;
      message.textContent = String(detail.msg).replace(/^Value error, /, "").split(/[\n。]/)[0] + "。";
      el.setAttribute("aria-invalid","true"); el.setAttribute("aria-describedby",message.id);
      const container = el.closest(".settings-field") || el.closest("fieldset");
      if (container) container.append(message); else el.after(message);
    });
  }
  return { openSettings, closeSettings, renderSettings, clearSettingsErrors, showSettingsErrors };
};
