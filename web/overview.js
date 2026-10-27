/* Monthly overview. All durable measurements continue to come from existing APIs. */
(() => {
  const $ = (selector) => document.querySelector(selector);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const fmt = (value) => value == null ? "—" : new Intl.NumberFormat("ja-JP").format(value);
  const signed = (value) => value == null ? "—" : `${value >= 0 ? "+" : ""}${fmt(value)}`;
  const sumKnown = (values) => {
    const known = values.filter((value) => value != null && Number.isFinite(value));
    return known.length ? known.reduce((a, b) => a + b, 0) : null;
  };
  const keyFor = (year, month, day) => `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  const todayJST = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Tokyo" }).format(new Date());
  const validMonth = (value) => /^(20\d{2}|21\d{2}|2200)-(0[1-9]|1[0-2])$/.test(value);
  const queryMonth = new URLSearchParams(location.search).get("month");
  let month = validMonth(queryMonth || "") ? queryMonth : todayJST.slice(0, 7);
  let generation = 0;
  let currentData;
  const demo = new URLSearchParams(location.search).get("demo") === "1";
  const sections = [["summary", "月間サマリー"], ["likes", "いいね推移"], ["followers", "フォロワー推移"], ["calendar", "投稿カレンダー"], ["posts", "投稿一覧"]];
  const defaults = Object.fromEntries(sections.map(([key]) => [key, true]));
  const preferenceKey = () => `xart_hig_overview_${demo ? "demo" : localStorage.getItem("xart_profile_id") || "default"}`;
  function readPreferences() {
    try { return { ...defaults, ...JSON.parse(localStorage.getItem(preferenceKey()) || "null") }; }
    catch { return { ...defaults }; }
  }
  let preferences = readPreferences();
  const dialog = document.createElement("dialog");
  dialog.className = "hig-dialog day-dialog";
  dialog.setAttribute("aria-labelledby", "day-dialog-title");
  dialog.innerHTML = '<div class="hig-dialog-heading"><h2 id="day-dialog-title"></h2><button class="icon-button" aria-label="閉じる">×</button></div><div id="day-dialog-body"></div>';
  document.body.append(dialog);
  dialog.querySelector("button").onclick = () => dialog.close();
  function showDay(day) {
    $("#day-dialog-title").textContent = `${day.date.replaceAll("-", "/")} の投稿`;
    $("#day-dialog-body").innerHTML = day.artworks.length ? postRows(day.artworks) : '<p class="overview-empty">この日の投稿はありません</p>';
    dialog.showModal();
  }
  function artworkHref(artwork) {
    return demo ? "/analytics?demo=1#views" : `/artworks/${encodeURIComponent(artwork.id)}`;
  }
  function postRows(artworks) {
    return artworks.map((artwork) => `<a class="highlight-post" href="${artworkHref(artwork)}"><span class="highlight-image">${artwork.image_url && /^https?:\/\/|^\/(?!\/)/.test(artwork.image_url) ? `<img src="${esc(artwork.image_url)}" alt="${esc(artwork.title)}" loading="lazy">` : '<span class="no-artwork">画像なし</span>'}</span><span class="highlight-copy"><time>${esc(new Intl.DateTimeFormat("ja-JP", { timeZone: "Asia/Tokyo", month: "2-digit", day: "2-digit" }).format(new Date(artwork.posted_at)))}</time><strong>${esc(artwork.title || "無題の投稿")}</strong><span class="highlight-metrics"><span aria-label="いいね ${fmt(artwork.likes)}">♥ ${fmt(artwork.likes)}</span><span aria-label="リポスト ${fmt(artwork.retweets)}">↻ ${fmt(artwork.retweets)}</span></span></span></a>`).join("");
  }
  function renderCalendar(host, data) {
    const offset = (new Date(data.year, data.month - 1, 1).getDay() + 6) % 7;
    host.innerHTML = ["月", "火", "水", "木", "金", "土", "日"].map((day) => `<span class="compact-weekday">${day}</span>`).join("") + '<span class="compact-spacer" aria-hidden="true"></span>'.repeat(offset) + data.days.map((day) => {
      const likes = sumKnown(day.artworks.map((artwork) => artwork.likes));
      const posted = day.artworks.length > 0;
      const today = day.date === todayJST;
      return `<button class="compact-day${posted ? " has-posts" : ""}${today ? " is-today" : ""}" data-day="${esc(day.date)}" ${today ? 'aria-current="date"' : ""} aria-label="${esc(day.date)}、${day.artworks.length}投稿${posted ? `、いいね ${fmt(likes)}` : ""}"><span>${Number(day.date.slice(-2))}</span>${posted ? `<span class="compact-day-meta"><img src="/assets/apple-hig/${likes >= 3000 ? "highlight-dot" : "post-dot"}.svg" alt="" width="7" height="7"><span>♥ ${likes == null ? "—" : likes >= 1000 ? `${(likes / 1000).toFixed(1)}k` : fmt(likes)}</span></span>` : ""}</button>`;
    }).join("");
    host.querySelectorAll("[data-day]").forEach((button) => {
      button.onclick = () => showDay(data.days.find((day) => day.date === button.dataset.day));
    });
  }
  window.MonthOverview = { renderCalendar };
  if (document.body.dataset.page !== "analytics") return;

  const prefsDialog = document.createElement("dialog");
  prefsDialog.className = "hig-dialog overview-settings-dialog";
  prefsDialog.setAttribute("aria-labelledby", "overview-settings-title");
  prefsDialog.innerHTML = `<div class="hig-dialog-heading"><h2 id="overview-settings-title">パネル設定</h2><button class="icon-button" data-close-overview aria-label="設定を閉じる">×</button></div><p class="settings-context">現在のビュー：ダッシュボード</p><h3>表示パネル</h3><form id="overview-preferences">${sections.map(([key, label]) => `<label class="overview-toggle"><span>${label}</span><input type="checkbox" role="switch" name="${key}"><span class="switch-track" aria-hidden="true"></span></label>`).join("")}<div class="overview-settings-actions"><button type="button" id="overview-lock" class="quiet-button" aria-pressed="false">ロックする</button><button type="submit" class="primary-button">保存</button></div></form><p id="overview-settings-status" role="status">表示設定はこのブラウザーに保存されます</p>`;
  document.body.append(prefsDialog);
  const form = $("#overview-preferences");
  function applyPreferences() {
    sections.forEach(([key]) => { $(`#overview-${key}`).hidden = preferences[key] === false; });
    document.body.classList.toggle("overview-locked", Boolean(preferences.locked));
  }
  function syncPreferencesForm() {
    sections.forEach(([key]) => { form.elements[key].checked = preferences[key] !== false; form.elements[key].disabled = Boolean(preferences.locked); });
    $("#overview-lock").textContent = preferences.locked ? "ロックを解除" : "ロックする";
    $("#overview-lock").setAttribute("aria-pressed", String(Boolean(preferences.locked)));
  }
  $("#overview-settings").onclick = () => { preferences = readPreferences(); syncPreferencesForm(); prefsDialog.showModal(); };
  prefsDialog.querySelector("[data-close-overview]").onclick = () => prefsDialog.close();
  $("#overview-lock").onclick = () => {
    // Keep display selections while changing the draft lock state.
    sections.forEach(([key]) => { preferences[key] = form.elements[key].checked; });
    preferences.locked = !preferences.locked;
    syncPreferencesForm();
  };
  form.onsubmit = (event) => {
    event.preventDefault();
    const next = { locked: preferences.locked || false };
    sections.forEach(([key]) => { next[key] = form.elements[key].checked; });
    try {
      localStorage.setItem(preferenceKey(), JSON.stringify(next));
      preferences = next;
      applyPreferences();
      prefsDialog.close();
    } catch { $("#overview-settings-status").textContent = "表示設定を保存できませんでした。ブラウザーの保存容量を確認してください"; }
  };
  const titles = { dashboard: ["分析ダッシュボード", "投稿・反応・フォロワーをまとめて確認"], views: ["MY VIEWS", "目的別に分析レイアウトを保存・切り替え"], likes: ["いいね推移", "投稿日別に作品の反応を確認"], followers: ["フォロワー分析", "アカウント全体のフォロワーの増減"], posts: ["投稿一覧", "期間内の作品と反応を確認"] };
  function setSection() {
    const hash = location.hash.slice(1);
    if (hash === "workspace") return;
    const section = titles[hash] ? hash : hash === "create" ? "views" : "dashboard";
    document.body.dataset.section = section;
    $("#overview").hidden = section === "views";
    $("#views-workspace").hidden = section !== "views";
    $("#page-title").textContent = titles[section][0];
    $("#page-description").textContent = titles[section][1];
    document.title = `${titles[section][0]} | twit_nanba`;
    document.querySelectorAll("[data-section]").forEach((link) => {
      if (link === document.body) return;
      const active = link.dataset.section === section || (link.closest(".bottom-nav") && link.dataset.section === "detail" && section === "posts");
      if (active) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
    });
    if (currentData) renderHighlights(currentData);
    window.dispatchEvent(new Event("resize"));
  }
  window.addEventListener("hashchange", setSection);
  setSection();
  function totals(data) {
    const artworks = data.days.flatMap((day) => day.artworks);
    return { posts: artworks.length, likes: artworks.length ? sumKnown(artworks.map((a) => a.likes)) : 0, reposts: artworks.length ? sumKnown(artworks.map((a) => a.retweets)) : 0, followers: data.summary.followers_delta };
  }
  function comparison(value, previous) {
    if (value == null || previous == null || previous <= 0) return "前月の比較データなし";
    const percent = (value - previous) / previous * 100;
    return `前月比 ${percent >= 0 ? "+" : ""}${percent.toFixed(1)}%`;
  }
  function renderSummary(data, previous) {
    const values = totals(data), prior = previous ? totals(previous) : {};
    const labels = { posts: "投稿数", likes: "獲得いいね", reposts: "リポスト", followers: "フォロワー増減" };
    const symbols = { posts: "▣", likes: "♥", reposts: "↗", followers: "+" };
    $("#overview-summary").innerHTML = Object.entries(labels).map(([key, label]) => `<div class="overview-metric metric-${key}"><span class="overview-metric-label"><span class="metric-symbol"><img src="/assets/apple-hig/metric-${key}.svg" alt="" width="29" height="29"><span aria-hidden="true">${symbols[key]}</span></span>${label}</span><strong>${key === "followers" ? signed(values[key]) : fmt(values[key])}</strong><small>${key === "followers" ? values[key] == null ? "期間データなし" : `現在 ${fmt(data.summary.followers)} フォロワー` : comparison(values[key], prior[key])}</small></div>`).join("");
    $("#overview-follower-total").textContent = signed(values.followers);
    $("#overview-follower-note").textContent = data.summary.followers == null ? "アカウントの計測データがありません" : `現在 ${fmt(data.summary.followers)} フォロワー`;
  }
  function renderBars(host, data, field) {
    const values = data.days.map((day) => field === "likes" ? (day.artworks.length ? sumKnown(day.artworks.map((art) => art.likes)) : null) : day.followers_delta);
    const known = values.filter((value) => value != null);
    if (!known.length) { host.innerHTML = '<p class="overview-empty">この期間の計測データはありません</p>'; return; }
    const max = Math.max(1, ...known.map(Math.abs));
    host.innerHTML = `<div class="daily-bars${known.some((v) => v < 0) ? " has-negative" : ""}">${data.days.map((day, i) => `<button class="daily-bar${values[i] < 0 ? " is-negative" : ""}" style="--bar-height:${values[i] == null ? 0 : Math.abs(values[i]) / max * 100}%" aria-label="${day.date}、${field === "likes" ? "いいね" : "フォロワー増減"} ${values[i] == null ? "未計測" : fmt(values[i])}" title="${day.date} · ${values[i] == null ? "未計測" : fmt(values[i])}"><span class="daily-bar-fill"></span></button>`).join("")}</div><div class="overview-chart-axis"><span>${data.month}/01</span><span>${data.month}/${String(Math.ceil(data.days.length / 2)).padStart(2, "0")}</span><span>${data.month}/${data.days.length}</span></div>`;
    host.querySelectorAll(".daily-bar").forEach((button, index) => { button.onclick = () => {
      if (field === "likes") showDay(data.days[index]);
      else {
        $("#day-dialog-title").textContent = `${data.days[index].date} のフォロワー増減`;
        $("#day-dialog-body").innerHTML = `<p class="follower-total">${signed(values[index])}</p><p>アカウント全体の日別計測</p>`;
        dialog.showModal();
      }
    }; });
  }
  function renderHighlights(data) {
    const artworks = data.days.flatMap((day) => day.artworks).sort((a, b) => (b.likes ?? -1) - (a.likes ?? -1));
    const all = document.body.dataset.section === "posts";
    $("#overview-highlights").innerHTML = artworks.length ? postRows(all ? artworks : artworks.slice(0, 3)) : '<p class="overview-empty">この期間の投稿はありません</p>';
    $("#overview-posts h2").textContent = all ? "投稿一覧" : "反応の多かった投稿";
  }
  function sampleCalendar(year, monthNumber) {
    const days = Array.from({ length: new Date(year, monthNumber, 0).getDate() }, (_, i) => {
      const date = keyFor(year, monthNumber, i + 1);
      const posted = [2, 5, 7, 10, 11, 15, 17, 21, 22, 25, 27, 30, 31].includes(i + 1);
      return { date, followers_delta: (i % 7) + 1, artworks: posted ? [{ id: `sample-${i}`, title: ["新しいイラストを公開しました", "制作過程のまとめ", "作品の記録"][i % 3], posted_at: `${date}T09:00:00+09:00`, image_url: "/demo-artwork.svg", likes: 1200 + i * 123, retweets: 80 + i * 11 }] : [] };
    });
    return { year, month: monthNumber, days, summary: { followers: 12580, followers_delta: days.reduce((sum, day) => sum + day.followers_delta, 0) } };
  }
  async function fetchCalendar(value) {
    const [year, number] = value.split("-").map(Number);
    if (demo) return sampleCalendar(year, number);
    const response = await fetch(`/api/calendar?year=${year}&month=${number}`);
    if (!response.ok) throw new Error("データを読み込めませんでした。「更新」で再試行してください。");
    return response.json();
  }
  async function load() {
    const request = ++generation;
    $("#overview-refresh").disabled = true;
    $("#overview-refresh").textContent = "更新中…";
    $("#overview").setAttribute("aria-busy", "true");
    $("#overview-error").hidden = true;
    const [year, number] = month.split("-").map(Number);
    const previousMonth = keyFor(number === 1 ? year - 1 : year, number === 1 ? 12 : number - 1, 1).slice(0, 7);
    try {
      const [data, previous] = await Promise.allSettled([fetchCalendar(month), validMonth(previousMonth) ? fetchCalendar(previousMonth) : Promise.resolve(null)]);
      if (request !== generation) return;
      if (data.status !== "fulfilled") throw data.reason;
      currentData = data.value;
      renderSummary(currentData, previous.status === "fulfilled" ? previous.value : null);
      renderBars($("#overview-likes-chart"), currentData, "likes");
      renderBars($("#overview-followers-chart"), currentData, "followers");
      $("#overview-calendar-caption").textContent = `${year}年${number}月 · 投稿と反応の概要`;
      renderCalendar($("#overview-calendar-grid"), currentData);
      renderHighlights(currentData);
      applyPreferences();
      const url = new URL(location.href);
      url.searchParams.set("month", month);
      history.replaceState(null, "", url);
      document.querySelectorAll('[data-month-step="-1"]').forEach((b) => { b.disabled = month === "2000-01"; });
      document.querySelectorAll('[data-month-step="1"]').forEach((b) => { b.disabled = month === "2200-12"; });
    } catch (error) {
      if (request !== generation) return;
      // Clear the previous month so failed navigation cannot mislabel stale data.
      currentData = null;
      $("#overview-summary").innerHTML = "";
      ["likes-chart", "followers-chart", "calendar-grid", "highlights"].forEach((id) => { $(`#overview-${id}`).innerHTML = ""; });
      $("#overview-follower-total").textContent = "—";
      $("#overview-follower-note").textContent = "";
      $("#overview-error").textContent = error.message;
      $("#overview-error").hidden = false;
    } finally {
      if (request === generation) { $("#overview-refresh").disabled = false; $("#overview-refresh").textContent = "⟳ 更新"; $("#overview").setAttribute("aria-busy", "false"); }
    }
  }
  $("#overview-month").value = month;
  $("#overview-month").onchange = (event) => { if (validMonth(event.target.value)) { month = event.target.value; load(); } };
  $("#overview-refresh").onclick = load;
  document.querySelectorAll("[data-month-step]").forEach((button) => { button.onclick = () => {
    const [year, number] = month.split("-").map(Number);
    const date = new Date(year, number - 1 + Number(button.dataset.monthStep), 1);
    const next = keyFor(date.getFullYear(), date.getMonth() + 1, 1).slice(0, 7);
    if (!validMonth(next)) return;
    month = next; $("#overview-month").value = month; load();
  }; });
  load();
})();
