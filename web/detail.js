const id = location.pathname.split('/').filter(Boolean).pop();
const number = value => value == null ? '—' : new Intl.NumberFormat('ja-JP').format(value);
const state = { metric: 'likes', mode: 'absolute' };
let points = [];

async function load() {
  const [artworkResponse, metricsResponse] = await Promise.all([fetch(`/api/artworks/${id}`), fetch(`/api/artworks/${id}/metrics`)]);
  if (!artworkResponse.ok) throw new Error('not found');
  const artwork = await artworkResponse.json();
  points = (await metricsResponse.json()).points;
  document.title = `${artwork.title} | X Art Analytics`;
  document.querySelector('#detail').innerHTML = `<header class="detail-header"><div><p class="kicker">ARTWORK DETAIL</p><h1>${artwork.title}</h1><p>${new Date(artwork.posted_at).toLocaleString('ja-JP')} 投稿</p></div><a class="x-link" href="${artwork.url}" target="_blank" rel="noreferrer">Xで開く ↗</a></header><div class="detail-grid"><div class="detail-image">${artwork.images[0] ? `<img src="${artwork.images[0].source_url}" alt="${artwork.title}">` : '<span>NO IMAGE</span>'}</div><div><div class="kpis"><div><span>LIKES</span><strong>${number(artwork.latest?.likes)}</strong></div><div><span>REPOSTS</span><strong>${number(artwork.latest?.retweets)}</strong></div><div><span>IMPRESSIONS</span><strong>${number(artwork.latest?.impressions)}</strong></div></div><div class="chart-panel"><div class="chart-toolbar"><div class="metric-tabs">${['likes','retweets','impressions'].map(metric => `<button class="${metric === state.metric ? 'active' : ''}" data-metric="${metric}">${metric === 'likes' ? 'Likes' : metric === 'retweets' ? 'RT' : 'Impressions'}</button>`).join('')}</div><div class="mode-tabs"><button class="active" data-mode="absolute">累積値</button><button data-mode="delta">増加量</button></div></div><div id="chart"></div></div></div></div><section class="log-section"><h2>計測ログ</h2><div class="log-table"><div class="log-row log-head"><span>経過時間</span><span>計測日時</span><span>Likes</span><span>RT</span><span>Imp</span></div>${points.map(point => `<div class="log-row"><span>${point.stage}</span><span>${new Date(point.measured_at).toLocaleString('ja-JP')}</span><span>${number(point.likes)}</span><span>${number(point.retweets)}</span><span>${number(point.impressions)}</span></div>`).join('')}</div></section>`;
  document.querySelectorAll('[data-metric]').forEach(button => button.onclick = () => { state.metric = button.dataset.metric; updateTabs(); drawChart(); });
  document.querySelectorAll('[data-mode]').forEach(button => button.onclick = () => { state.mode = button.dataset.mode; updateTabs(); drawChart(); });
  drawChart();
}
function updateTabs() { document.querySelectorAll('[data-metric]').forEach(button => button.classList.toggle('active', button.dataset.metric === state.metric)); document.querySelectorAll('[data-mode]').forEach(button => button.classList.toggle('active', button.dataset.mode === state.mode)); }
function drawChart() { const values = points.map((point, index) => state.mode === 'absolute' || index === 0 ? point[state.metric] : point[state.metric] - points[index - 1][state.metric]); const max = Math.max(...values, 1); document.querySelector('#chart').innerHTML = `<div class="bar-chart">${values.map((value, index) => `<div class="bar-wrap" title="${points[index].stage}: ${number(value)}"><div class="bar" style="height:${Math.max(4, value / max * 100)}%"></div><small>${points[index].stage}</small></div>`).join('')}</div><div class="chart-value">${number(values.at(-1))} <small>${state.mode === 'absolute' ? state.metric : 'since previous'}</small></div>`; }
load().catch(() => { document.querySelector('#detail').innerHTML = '<p class="error">作品が見つかりませんでした。</p>'; });
