const id = location.pathname.split('/').filter(Boolean).pop();
const number = value => value == null ? '—' : new Intl.NumberFormat('ja-JP').format(value);
const state = { metric: 'likes', mode: 'absolute', imageIndex: 0 };
let points = [];
let images = [];

async function load() {
  const [artworkResponse, metricsResponse] = await Promise.all([fetch(`/api/artworks/${id}`), fetch(`/api/artworks/${id}/metrics`)]);
  if (!artworkResponse.ok) throw new Error('not found');
  const artwork = await artworkResponse.json();
  points = (await metricsResponse.json()).points || [];
  images = [...(artwork.images || [])].sort((a, b) => a.image_order - b.image_order);
  document.title = `${artwork.title} | X Art Analytics`;
  document.querySelector('#detail').innerHTML = `<header class="detail-header"><div><p class="kicker">ARTWORK DETAIL</p><h1>${artwork.title}</h1><p>${new Date(artwork.posted_at).toLocaleString('ja-JP')} 投稿</p></div><a class="x-link" href="${artwork.url}" target="_blank" rel="noreferrer">Xで開く ↗</a></header><div class="detail-grid"><div class="detail-image" id="image-viewer"></div><div><div class="kpis"><div><span>LIKES</span><strong>${number(artwork.latest?.likes)}</strong></div><div><span>REPOSTS</span><strong>${number(artwork.latest?.retweets)}</strong></div><div><span>IMPRESSIONS</span><strong>${number(artwork.latest?.impressions)}</strong></div></div><div class="chart-panel"><div class="chart-toolbar"><div class="metric-tabs">${['likes','retweets','impressions'].map(metric => `<button class="${metric === state.metric ? 'active' : ''}" data-metric="${metric}">${metric === 'likes' ? 'Likes' : metric === 'retweets' ? 'RT' : 'Impressions'}</button>`).join('')}</div><div class="mode-tabs"><button class="active" data-mode="absolute">累積値</button><button data-mode="delta">増加量</button></div></div><div id="chart"></div></div></div></div><section class="log-section"><h2>計測ログ</h2><div class="log-table"><div class="log-row log-head"><span>経過時間</span><span>計測日時</span><span>Likes</span><span>RT</span><span>Imp</span></div>${points.map(point => `<div class="log-row"><span>${point.stage}</span><span>${new Date(point.measured_at).toLocaleString('ja-JP')}</span><span>${number(point.likes)}</span><span>${number(point.retweets)}</span><span>${number(point.impressions)}</span></div>`).join('')}</div></section>`;
  renderCarousel();
  document.querySelectorAll('[data-metric]').forEach(button => button.onclick = () => { state.metric = button.dataset.metric; updateTabs(); drawChart(); });
  document.querySelectorAll('[data-mode]').forEach(button => button.onclick = () => { state.mode = button.dataset.mode; updateTabs(); drawChart(); });
  document.addEventListener('keydown', handleKeydown);
  drawChart();
}

function renderCarousel() {
  const viewer = document.querySelector('#image-viewer');
  if (!images.length) {
    viewer.innerHTML = '<span>NO IMAGE</span>';
    return;
  }
  const image = images[state.imageIndex];
  const controls = images.length > 1 ? `<button class="carousel-button previous" aria-label="前の画像">←</button><button class="carousel-button next" aria-label="次の画像">→</button><div class="carousel-indicators">${images.map((_, index) => `<button class="carousel-dot ${index === state.imageIndex ? 'active' : ''}" data-image-index="${index}" aria-label="${index + 1}枚目"></button>`).join('')}</div><span class="carousel-position">${state.imageIndex + 1} / ${images.length}</span>` : '';
  viewer.innerHTML = `<img src="${image.source_url}" alt="" class="carousel-image">${controls}`;
  if (images.length > 1) {
    viewer.querySelector('.previous').onclick = () => changeImage(state.imageIndex - 1);
    viewer.querySelector('.next').onclick = () => changeImage(state.imageIndex + 1);
    viewer.querySelectorAll('[data-image-index]').forEach(dot => dot.onclick = () => changeImage(Number(dot.dataset.imageIndex)));
    let startX = 0;
    viewer.ontouchstart = event => { startX = event.changedTouches[0].clientX; };
    viewer.ontouchend = event => {
      const distance = event.changedTouches[0].clientX - startX;
      if (Math.abs(distance) >= 50) changeImage(state.imageIndex + (distance < 0 ? 1 : -1));
    };
  }
}

function changeImage(index) {
  state.imageIndex = Math.max(0, Math.min(index, images.length - 1));
  renderCarousel();
}

function handleKeydown(event) {
  if (event.key === 'ArrowLeft') changeImage(state.imageIndex - 1);
  if (event.key === 'ArrowRight') changeImage(state.imageIndex + 1);
}

function updateTabs() {
  document.querySelectorAll('[data-metric]').forEach(button => button.classList.toggle('active', button.dataset.metric === state.metric));
  document.querySelectorAll('[data-mode]').forEach(button => button.classList.toggle('active', button.dataset.mode === state.mode));
}

function drawChart() {
  const values = points.map((point, index) => state.mode === 'absolute' || index === 0 ? point[state.metric] : point[state.metric] - points[index - 1][state.metric]);
  if (state.mode === 'delta') {
    drawDeltaBarChart(values);
    return;
  }
  const validValues = values.filter(value => value != null);
  const max = Math.max(...validValues, 1);
  const width = 800;
  const height = 280;
  const left = 42;
  const right = 16;
  const top = 18;
  const bottom = 42;
  const chartWidth = width - left - right;
  const chartHeight = height - top - bottom;
  const x = index => points.length === 1 ? left + chartWidth / 2 : left + (index / (points.length - 1)) * chartWidth;
  const y = value => top + chartHeight - (value / max) * chartHeight;
  const linePoints = values.map((value, index) => value == null ? null : `${x(index)},${y(value)}`).filter(Boolean).join(' ');
  const dots = values.map((value, index) => value == null ? '' : `<circle cx="${x(index)}" cy="${y(value)}" r="4" class="chart-point"><title>${points[index].stage}: ${number(value)}</title></circle>`).join('');
  const tickCount = 4;
  const grid = Array.from({ length: tickCount + 1 }, (_, index) => {
    const value = max * index / tickCount;
    const yPosition = y(value);
    return `<line x1="${left}" y1="${yPosition}" x2="${width - right}" y2="${yPosition}" class="chart-grid"/><text x="${left - 8}" y="${yPosition + 4}" class="chart-y-label" text-anchor="end">${number(Math.round(value))}</text>`;
  }).join('');
  const labelStep = points.length > 8 ? Math.ceil((points.length - 1) / 7) : 1;
  const labels = points.map((point, index) => index % labelStep === 0 || index === points.length - 1 ? `<text x="${x(index)}" y="${height - 14}" class="chart-label" text-anchor="middle">${point.stage}</text>` : '').join('');
  const latest = values.at(-1);
  document.querySelector('#chart').innerHTML = `<svg class="line-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${state.metric}の推移">${grid}<line x1="${left}" y1="${top + chartHeight}" x2="${width - right}" y2="${top + chartHeight}" class="chart-axis"/><polyline points="${linePoints}" class="chart-line"/>${dots}${labels}</svg><div class="chart-value">${number(latest)} <small>${state.mode === 'absolute' ? state.metric : 'since previous'}</small></div>`;
}

function drawDeltaBarChart(values) {
  const validValues = values.filter(value => value != null);
  const max = Math.max(...validValues, 1);
  const labelStep = points.length > 8 ? Math.ceil((points.length - 1) / 7) : 1;
  const bars = values.map((value, index) => {
    const label = index % labelStep === 0 || index === points.length - 1 ? `<small>${points[index].stage}</small>` : '<small></small>';
    const height = value == null ? 0 : Math.max(4, value / max * 100);
    return `<div class="bar-wrap" title="${points[index].stage}: ${number(value)}"><div class="bar" style="height:${height}%"></div>${label}</div>`;
  }).join('');
  document.querySelector('#chart').innerHTML = `<div class="bar-chart delta-chart">${bars}</div><div class="chart-value">${number(values.at(-1))} <small>since previous</small></div>`;
}

load().catch(() => { document.querySelector('#detail').innerHTML = '<p class="error">作品が見つかりませんでした。</p>'; });