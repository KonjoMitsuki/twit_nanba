const id = location.pathname.split('/').filter(Boolean).pop();
const number = value => value == null ? '—' : new Intl.NumberFormat('ja-JP').format(value);
const state = { metric: 'likes', mode: 'absolute', xAxisMode: 'stage', imageIndex: 0 };
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
  document.querySelector('#chart').onclick = event => {
    if (!event.target.closest('[data-x-axis-label]')) return;
    state.xAxisMode = state.xAxisMode === 'stage' ? 'measuredAt' : 'stage';
    drawChart();
  };
  window.addEventListener('resize', drawChart);
  document.addEventListener('keydown', handleKeydown);
  const detailHeader = document.querySelector('.detail-header');
  const detailActions = document.createElement('div');
  detailActions.className = 'detail-actions';
  const postLink = detailHeader.querySelector('.x-link');
  detailActions.append(postLink);
  if (artwork.tracked_profile_url) {
    const profileLink = document.createElement('a');
    profileLink.className = 'x-link';
    profileLink.href = artwork.tracked_profile_url;
    profileLink.target = '_blank';
    profileLink.rel = 'noreferrer';
    profileLink.textContent = '𝕏プロフィール ↗';
    detailActions.append(profileLink);
  }
  detailHeader.append(detailActions);
  setupCharacterEditor(artwork);
  setupTagList(artwork);
  drawChart();
}

function setupCharacterEditor(artwork) {
  const editor = document.createElement('section');
  editor.className = 'character-editor';
  editor.innerHTML = '<div class="character-editor-heading"><span class="kicker">CHARACTER</span><strong class="character-value-display"></strong><input class="character-value" type="text" maxlength="100" aria-label="キャラクター名" hidden></div><div class="character-editor-actions"><button type="button" class="character-edit-button">編集</button></div><div class="character-edit-form" hidden><button type="button" class="character-auto-button">タグから自動入力</button><button type="button" class="character-save-button">保存</button><button type="button" class="character-cancel-button">キャンセル</button></div><p class="character-editor-status" role="status"></p>';
  document.querySelector('#detail .detail-header').insertAdjacentElement('afterend', editor);

  const display = editor.querySelector('.character-value-display');
  const value = editor.querySelector('.character-value');
  const form = editor.querySelector('.character-edit-form');
  const editButton = editor.querySelector('.character-edit-button');
  const status = editor.querySelector('.character-editor-status');
  const setValue = character => {
    display.textContent = character || '';
    value.value = character || '';
  };
  const setStatus = message => { status.textContent = message; };
  const applyArtwork = updated => {
    artwork.character = updated.character;
    setValue(artwork.character);
  };
  const request = async (url, options) => {
    const response = await fetch(url, options);
    if (!response.ok) throw new Error((await response.json()).detail || '保存に失敗しました');
    return response.json();
  };

  setValue(artwork.character);
  const enterEditMode = () => {
    display.hidden = true;
    value.hidden = false;
    form.hidden = false;
    editButton.hidden = true;
    value.focus();
    setStatus('');
  };
  const leaveEditMode = () => {
    display.hidden = false;
    value.hidden = true;
    form.hidden = true;
    editButton.hidden = false;
    setValue(artwork.character);
  };
  editButton.onclick = enterEditMode;
  editor.querySelector('.character-cancel-button').onclick = () => {
    leaveEditMode();
    setStatus('');
  };
  editor.querySelector('.character-save-button').onclick = async () => {
    try {
      const updated = await request(`/api/artworks/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ character: value.value.trim() || null }),
      });
      applyArtwork(updated);
      leaveEditMode();
      setStatus('保存しました');
    } catch (error) {
      setStatus(error.message);
    }
  };
  editor.querySelector('.character-auto-button').onclick = async () => {
    try {
      const suggestion = await request(`/api/artworks/${id}/character/suggestion`);
      if (suggestion.character) {
        value.value = suggestion.character;
        setStatus('タグから入力しました。保存すると反映されます');
      } else {
        setStatus('対応するタグがありません');
      }
    } catch (error) {
      setStatus(error.message);
    }
  };
}
function setupTagList(artwork) {
  const tags = Array.isArray(artwork.tags) ? artwork.tags.filter(Boolean) : [];
  const section = document.createElement('section');
  section.className = 'tag-list-section';
  const heading = document.createElement('span');
  heading.className = 'kicker';
  heading.textContent = 'TAGS';
  section.append(heading);
  const list = document.createElement('div');
  list.className = 'tag-list';
  if (tags.length) {
    tags.forEach(tag => {
      const item = document.createElement('span');
      item.className = 'detail-tag';
      item.textContent = tag;
      list.append(item);
    });
  } else {
    const empty = document.createElement('span');
    empty.className = 'tag-list-empty';
    empty.textContent = '\u30bf\u30b0\u306a\u3057';
    list.append(empty);
  }
  section.append(list);
  document.querySelector('.character-editor').insertAdjacentElement('afterend', section);
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

function getVisibleLabelIndexes(values, candidates, thresholdIndexes, xPosition, yPosition, scale = 1) {
  const latestIndex = values.findLastIndex(value => value != null);
  const fontSize = window.matchMedia('(max-width: 700px)').matches ? 10 : 12;
  const ranked = [...candidates].sort((a, b) => {
    const priorityA = a === latestIndex ? 3 : thresholdIndexes.has(a) ? 2 : 1;
    const priorityB = b === latestIndex ? 3 : thresholdIndexes.has(b) ? 2 : 1;
    return priorityB - priorityA || a - b;
  });
  const visible = [];
  ranked.forEach(index => {
    const labelWidth = Math.max(20, String(number(values[index])).length * fontSize * 0.6 + 8);
    const centerX = xPosition(index) * scale;
    const centerY = yPosition(index) * scale;
    const box = { index, left: centerX - labelWidth / 2, right: centerX + labelWidth / 2, top: centerY - fontSize - 4, bottom: centerY + 3 };
    if (!visible.some(other => box.left < other.right + 5 && box.right > other.left - 5 && box.top < other.bottom + 3 && box.bottom > other.top - 3)) visible.push(box);
  });
  return new Set(visible.map(box => box.index).filter(index => index != null));
}

function getVisibleXAxisIndexes(labels, xPositionPx) {
  const lastIndex = labels.length - 1;
  if (lastIndex <= 0) return new Set([0]);
  const fontSize = window.matchMedia('(max-width: 700px)').matches ? 10 : 12;
  const charWidth = fontSize * 0.6;
  const gap = 10;
  const widthOf = index => Math.max(16, String(labels[index]).length * charWidth) + gap;
  const order = [lastIndex, 0, ...Array.from({ length: Math.max(0, lastIndex - 1) }, (_, index) => index + 1)];
  const chosen = [];
  order.forEach(index => {
    const center = xPositionPx(index);
    const half = widthOf(index) / 2;
    const box = { index, left: center - half, right: center + half };
    if (!chosen.some(other => box.left < other.right && box.right > other.left)) chosen.push(box);
  });
  return new Set(chosen.map(item => item.index));
}

function getXAxisLabels() {
  if (state.xAxisMode === 'stage') return points.map(point => point.stage);
  let previousDate = '';
  return points.map(point => {
    const measuredAt = new Date(point.measured_at);
    const date = `${measuredAt.getFullYear()}-${measuredAt.getMonth()}-${measuredAt.getDate()}`;
    const time = measuredAt.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
    const monthDay = `${String(measuredAt.getMonth() + 1).padStart(2, '0')}/${String(measuredAt.getDate()).padStart(2, '0')}`;
    const label = date === previousDate ? time : `${time}\n${monthDay}`;
    previousDate = date;
    return label;
  });
}

function getXAxisModeLabel() {
  return state.xAxisMode === 'stage' ? '経過時間' : '計測時間';
}

function getMetricLabel() {
  return {
    likes: 'Likes',
    retweets: 'RT',
    impressions: 'Impressions'
  }[state.metric] || '計測値';
}

function getChartPointValue(index) {
  const point = points[index];
  if (!point) return null;
  if (state.mode === 'absolute' || index === 0) return point[state.metric];
  const previous = points[index - 1];
  return previous == null || previous[state.metric] == null || point[state.metric] == null ? point[state.metric] : point[state.metric] - previous[state.metric];
}

function createChartTooltipMarkup(index) {
  const point = points[index];
  const value = getChartPointValue(index);
  if (!point) return '';
  const measuredAt = new Date(point.measured_at);
  return `
    <div class="chart-tooltip-header">${getMetricLabel()}</div>
    <div class="chart-tooltip-row"><span>計測値</span><strong>${number(value)}</strong></div>
    <div class="chart-tooltip-row"><span>経過時間</span><strong>${point.stage || '—'}</strong></div>
    <div class="chart-tooltip-row"><span>計測日時</span><strong>${measuredAt.toLocaleString('ja-JP')}</strong></div>
  `;
}

function bindChartInteractions() {
  const chart = document.querySelector('#chart');
  if (!chart) return;

  const tooltip = chart.querySelector('.chart-tooltip') || document.createElement('div');
  tooltip.className = 'chart-tooltip';
  tooltip.hidden = true;
  if (!chart.querySelector('.chart-tooltip')) {
    chart.append(tooltip);
  }

  const setActivePoint = (element, active) => {
    if (element.classList && element.classList.contains('chart-point')) {
      element.classList.toggle('active', active);
    }
  };

  const showTooltip = (element, clientX, clientY) => {
    const pointIndex = Number(element.dataset.chartPointIndex ?? element.dataset.index);
    if (!Number.isInteger(pointIndex) || !points[pointIndex]) return;
    setActivePoint(element, true);
    tooltip.innerHTML = createChartTooltipMarkup(pointIndex);
    const chartRect = chart.getBoundingClientRect();
    const left = clientX != null ? clientX - chartRect.left : element.getBoundingClientRect().left - chartRect.left + element.getBoundingClientRect().width / 2;
    const top = clientY != null ? clientY - chartRect.top : element.getBoundingClientRect().top - chartRect.top;
    tooltip.style.left = `${Math.min(Math.max(left, 76), chartRect.width - 76)}px`;
    tooltip.style.top = `${Math.max(top - 12, 18)}px`;
    tooltip.hidden = false;
  };

  const hideTooltip = () => {
    tooltip.hidden = true;
    chart.querySelectorAll('.chart-point').forEach(point => point.classList.remove('active'));
  };

  chart.querySelectorAll('.chart-point, .bar-wrap').forEach(element => {
    const showOnPointer = event => showTooltip(element, event.clientX, event.clientY);
    const showOnTouch = event => {
      const touch = event.touches && event.touches[0] ? event.touches[0] : event.changedTouches && event.changedTouches[0];
      if (!touch) return;
      event.preventDefault();
      showTooltip(element, touch.clientX, touch.clientY);
    };

    element.addEventListener('pointerenter', event => {
      showOnPointer(event);
      setActivePoint(element, true);
    });
    element.addEventListener('pointermove', showOnPointer);
    element.addEventListener('pointerleave', () => {
      hideTooltip();
      setActivePoint(element, false);
    });
    element.addEventListener('pointerdown', event => {
      showOnPointer(event);
      setActivePoint(element, true);
    });
    element.addEventListener('touchstart', event => {
      showOnTouch(event);
      setActivePoint(element, true);
    }, { passive: false });
    element.addEventListener('touchmove', showOnTouch, { passive: false });
    element.addEventListener('touchend', () => {
      hideTooltip();
      setActivePoint(element, false);
    });
    element.addEventListener('touchcancel', () => {
      hideTooltip();
      setActivePoint(element, false);
    });
  });

  chart.addEventListener('pointerleave', hideTooltip);
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
  const validPoints = values.map((value, index) => value == null ? null : `${x(index)},${y(value)}`).filter(Boolean);
  const areaPoints = validPoints.length ? `${validPoints[0].split(',')[0]},${top + chartHeight} ${validPoints.join(' ')} ${validPoints.at(-1).split(',')[0]},${top + chartHeight}` : '';
  const labelIndexes = new Set();
  const thresholdIndexes = new Set();
  const chartWidthPx = document.querySelector('#chart').clientWidth || width;
  const xScale = chartWidthPx / width;
  let nextThreshold = 50;
  values.forEach((value, index) => {
    if (value == null || value === 0 || (index > 0 && value === values[index - 1])) return;
    if (value >= nextThreshold) {
      thresholdIndexes.add(index);
      nextThreshold += 50;
    }
    labelIndexes.add(index);
  });
  const latestIndex = values.findLastIndex(value => value != null);
  const visibleLabelIndexes = getVisibleLabelIndexes(values, labelIndexes, thresholdIndexes, x, index => Math.max(12, y(values[index]) - 9), xScale);
  const valueLabels = values.map((value, index) => value == null || !visibleLabelIndexes.has(index) ? '' : `<text x="${x(index)}" y="${Math.max(12, y(value) - 9)}" class="chart-value-label${thresholdIndexes.has(index) ? ' chart-threshold-label' : ''}" text-anchor="middle">${number(value)}</text>`).join('');
  const tickCount = Math.min(4, Math.max(1, Math.floor(max)));
  const grid = Array.from({ length: tickCount + 1 }, (_, index) => {
    const value = max * index / tickCount;
    const yPosition = y(value);
    return `<line x1="${left}" y1="${yPosition}" x2="${width - right}" y2="${yPosition}" class="chart-grid"/><text x="${left - 8}" y="${yPosition + 4}" class="chart-y-label" text-anchor="end">${number(Math.round(value))}</text>`;
  }).join('');
  const xAxisLabels = getXAxisLabels();
  const visibleXIndexes = getVisibleXAxisIndexes(xAxisLabels, index => x(index) * xScale);
  const labels = points.map((point, index) => {
    if (!visibleXIndexes.has(index)) return '';
    const labelText = xAxisLabels[index];
    const lines = String(labelText).split('\n');
    const baseY = height - 14;
    return lines.map((line, lineIndex) => `<text x="${x(index)}" y="${baseY + lineIndex * 12}" class="chart-label" text-anchor="middle">${line}</text>`).join('');
  }).join('');
  const xAxisHitArea = `<rect x="${left}" y="${height - bottom}" width="${chartWidth}" height="${bottom}" fill="transparent" data-x-axis-label="true" style="cursor:pointer"/>`;
  const plotMarkers = values.map((value, index) => value == null ? '' : `<circle class="chart-point" data-chart-point-index="${index}" cx="${x(index)}" cy="${y(value)}" r="6"></circle>`).join('');
  document.querySelector('#chart').innerHTML = `<svg class="line-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${state.metric}の推移">${grid}<line x1="${left}" y1="${top + chartHeight}" x2="${width - right}" y2="${top + chartHeight}" class="chart-axis"/><polygon points="${areaPoints}" class="chart-area"/><polyline points="${linePoints}" class="chart-line"/>${plotMarkers}${valueLabels}${labels}${xAxisHitArea}</svg><div class="chart-tooltip" hidden></div><div class="chart-legend"><span class="chart-legend-line"></span><span>${getXAxisModeLabel()}（タップで切替）</span></div>`;
  bindChartInteractions();
}

function drawDeltaBarChart(values) {
  const validValues = values.filter(value => value != null);
  const max = Math.max(...validValues, 1);
  const labelIndexes = new Set();
  const thresholdIndexes = new Set();
  let nextThreshold = 50;
  values.forEach((value, index) => {
    if (value == null || value === 0 || (index > 0 && value === values[index - 1])) return;
    if (value >= nextThreshold) {
      thresholdIndexes.add(index);
      nextThreshold += 50;
    }
    labelIndexes.add(index);
  });
  const latestIndex = values.findLastIndex(value => value != null);
  const chartWidth = document.querySelector('#chart').clientWidth || 800;
  const plotLeft = 42;
  const plotWidth = Math.max(1, chartWidth - plotLeft - 4);
  const plotHeight = 238;
  const visibleLabelIndexes = getVisibleLabelIndexes(values, labelIndexes, thresholdIndexes, index => plotLeft + ((index + 0.5) / values.length) * plotWidth, index => 10 + plotHeight - (values[index] == null ? 0 : Math.max(4, values[index] / max * 100) / 100 * plotHeight));
  const xAxisLabels = getXAxisLabels();
  const visibleXIndexes = getVisibleXAxisIndexes(xAxisLabels, index => plotLeft + ((index + 0.5) / values.length) * plotWidth);
  const bars = values.map((value, index) => {
    const valueLabel = visibleLabelIndexes.has(index) ? `<small class="bar-value-label ${thresholdIndexes.has(index) ? 'chart-threshold-label' : ''}">${number(value)}</small>` : '<small class="bar-value-label"></small>';
    const xLabelText = String(xAxisLabels[index]).split('\n').join('<br>');
    const xLabel = visibleXIndexes.has(index) ? `<small class="bar-x-label" data-x-axis-label="true" tabindex="0">${xLabelText}</small>` : '<small class="bar-x-label"></small>';
    const height = value == null ? 0 : Math.max(4, value / max * 100);
    return `<div class="bar-wrap" data-chart-point-index="${index}" title="${xAxisLabels[index]}: ${number(value)}">${valueLabel}<div class="bar" style="height:${height}%"></div>${xLabel}</div>`;
  }).join('');
  const tickCount = Math.min(4, Math.max(1, Math.floor(max)));
  const yLabels = Array.from({ length: tickCount + 1 }, (_, index) => `<span>${number(Math.round(max * (tickCount - index) / tickCount))}</span>`).join('');
  document.querySelector('#chart').innerHTML = `<div class="bar-chart delta-chart"><div class="bar-y-labels">${yLabels}</div><div class="bar-plot">${bars}</div><div data-x-axis-label="true" style="position:absolute;left:0;right:0;bottom:0;height:32px;z-index:3;cursor:pointer"></div></div><div class="chart-tooltip" hidden></div><div class="chart-value">${number(latestIndex >= 0 ? values[latestIndex] : null)} <small>since previous</small></div><div class="chart-legend"><span>${getXAxisModeLabel()}（タップで切替）</span></div>`;
  bindChartInteractions();
}

load().catch(() => { document.querySelector('#detail').innerHTML = '<p class="error">作品が見つかりませんでした。</p>'; });