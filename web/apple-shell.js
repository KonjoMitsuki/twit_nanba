/* Shared navigation for the vanilla dashboard, calendar and artwork pages. */
(() => {
  const page = document.body.dataset.page;
  const demo = new URLSearchParams(location.search).get("demo") === "1";
  const analytics = `/analytics${demo ? "?demo=1" : ""}`;
  const paths = {
    dashboard: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18"/>',
    chart: '<path d="M4 20V4m0 16h16M8 16V11m5 5V6m5 10V9"/>',
    followers: '<path d="m3 16 5-5 4 3 8-9m-6 0h6v6"/>',
    views: '<rect x="5" y="5" width="14" height="14" rx="2" transform="rotate(45 12 12)"/><rect x="9" y="9" width="6" height="6" rx="1"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  };
  const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.chart}</svg>`;
  const current = page === "calendar" ? "calendar" : page === "detail" ? "detail" : (location.hash.slice(1) || "dashboard");
  const nav = [
    ["dashboard", analytics, "ダッシュボード"],
    ["calendar", "/", "投稿カレンダー"],
    ["likes", `${analytics}#likes`, "いいね推移"],
    ["followers", `${analytics}#followers`, "フォロワー分析"],
    ["views", `${analytics}#views`, "MY VIEWS"],
  ];
  const sidebar = document.querySelector(".sidebar");
  sidebar.innerHTML = `
    <a class="workspace-brand" href="${analytics}"><span class="brand-mark"><img src="/assets/apple-hig/brand.svg" alt="" width="34" height="34"><span>n</span></span><span>twit_nanba</span></a>
    <p class="nav-heading">ANALYTICS</p>
    <nav class="primary-nav" aria-label="ページ">${nav.map(([key, href, label]) => `<a href="${href}" data-section="${key}" ${key === current ? 'aria-current="page"' : ""}>${icon(key === "likes" ? "chart" : key)}<span>${label}</span></a>`).join("")}</nav>
    <div class="sidebar-heading">MY VIEWS</div>
    <nav id="view-list" class="view-list" aria-label="保存したビュー">${page !== "analytics" ? `<a class="saved-views-link" href="${analytics}#views">${icon("views")}保存したビューを開く</a>` : ""}</nav>
    <button id="sidebar-add" class="sidebar-create" type="button">${icon("plus")}ビューを作成</button>
    <div class="sidebar-bottom"><div class="profile-card"><span class="profile-avatar"><img src="/assets/apple-hig/profile.svg" alt="" width="35" height="35"><span>N</span></span><div><strong>個人アナリティクス</strong><div id="account"></div></div></div></div>`;
  if (page !== "analytics") document.querySelector("#sidebar-add").onclick = () => { location.href = `${analytics}#create`; };
  const mobile = document.createElement("header");
  mobile.className = "mobile-topbar";
  mobile.innerHTML = `<a href="${analytics}">twit_nanba</a><button class="icon-button mobile-menu-button" aria-label="メニューを開く" aria-expanded="false">${icon("more")}</button>`;
  document.querySelector(".main-shell").prepend(mobile);
  const bottom = document.createElement("nav");
  bottom.className = "bottom-nav";
  bottom.setAttribute("aria-label", "モバイルナビゲーション");
  const detailHref = page === "detail" ? location.pathname : `${analytics}#posts`;
  bottom.innerHTML = [["dashboard", analytics, "分析", "dashboard"], ["calendar", "/", "カレンダー", "calendar"], ["detail", detailHref, "詳細", "followers"], ["views", `${analytics}#views`, "設定", "views"]].map(([key, href, label, symbol]) => `<a href="${href}" data-section="${key}" ${key === current ? 'aria-current="page"' : ""}>${icon(symbol)}<span>${label}</span></a>`).join("");
  document.body.append(bottom);
  const menu = mobile.querySelector("button");
  const closeMenu = () => { document.body.classList.remove("navigation-open"); menu.setAttribute("aria-expanded", "false"); };
  menu.onclick = () => {
    const open = document.body.classList.toggle("navigation-open");
    menu.setAttribute("aria-expanded", String(open));
    if (open) sidebar.querySelector("a").focus();
  };
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && document.body.classList.contains("navigation-open")) { closeMenu(); menu.focus(); } });
  document.addEventListener("click", (event) => {
    if (!sidebar.contains(event.target) && !mobile.contains(event.target)) closeMenu();
    if (event.target.closest(".sidebar a, .sidebar button")) closeMenu();
  });
  window.addEventListener("hashchange", closeMenu);
  window.AppleShell = { icon, analytics };
})();
