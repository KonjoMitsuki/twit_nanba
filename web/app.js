const state = { date: new Date() };
const monthName = new Intl.DateTimeFormat('ja-JP', { year: 'numeric', month: 'long' });
const number = value => value == null ? '—' : new Intl.NumberFormat('ja-JP').format(value);
const shortNumber = value => value == null ? '—' : value >= 10000 ? `${(value / 1000).toFixed(1)}k` : number(value);

async function loadCalendar() {
  const year = state.date.getFullYear();
  const month = state.date.getMonth() + 1;
  document.querySelector('#month-title').textContent = monthName.format(state.date);
  const response = await fetch(`/api/calendar?year=${year}&month=${month}`);
  const data = await response.json();
  const profileLink = document.querySelector('#tracked-profile-link');
  if (data.tracked_profile_url) {
    profileLink.href = data.tracked_profile_url;
    profileLink.hidden = false;
  }
  renderSummary(data.summary);
  renderCalendar(data);
}

function renderSummary(summary) {
  const items = [['FOLLOWERS', number(summary.followers), summary.followers_delta == null ? '期間データなし' : `${summary.followers_delta >= 0 ? '+' : ''}${number(summary.followers_delta)} this month`], ['POSTS', number(summary.posts), 'published works'], ['LIKES', number(summary.likes), 'latest snapshots'], ['REPOSTS', number(summary.retweets), 'latest snapshots']];
  document.querySelector('#summary').innerHTML = items.map(([label, value, note]) => `<div class="summary-item"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`).join('');
}

function renderCalendar(data) {
  const calendar = document.querySelector('#calendar');
  const first = new Date(data.year, data.month - 1, 1);
  const daysInMonth = new Date(data.year, data.month, 0).getDate();
  const byDate = Object.fromEntries(data.days.map(day => [day.date, day]));
  calendar.innerHTML = '';
  for (let i = 0; i < first.getDay(); i++) calendar.append(document.createElement('div'));
  for (let day = 1; day <= daysInMonth; day++) {
    const dateKey = `${data.year}-${String(data.month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const dayData = byDate[dateKey];
    const cell = document.createElement('div');
    cell.className = `day-cell${dayData && dayData.artworks.length > 1 ? ' day-cell--multiple' : ''}`;
    cell.innerHTML = `<div class="day-number">${day}</div>`;
    if (dayData) {
      const extraCount = Math.max(dayData.artworks.length - 2, 0);
      const cards = dayData.artworks.slice(0, 3).map((art, index) => `<a class="art-card${index > 0 ? ' art-card--extra' : ''}" href="/artworks/${art.id}"><div class="thumb">${art.image_url ? `<img src="${art.image_url}" alt="">` : '<span>NO IMAGE</span>'}${index === 0 && extraCount > 0 ? `<span class="art-extra-badge">+${extraCount}</span>` : ''}</div><div class="art-meta"><b class="art-likes">${shortNumber(art.likes)}</b><span class="art-likes-label"> likes</span><span class="art-rt">↗ ${shortNumber(art.retweets)}</span></div><small class="art-time">${new Date(art.posted_at).toLocaleTimeString('ja-JP', {hour: '2-digit', minute: '2-digit'})}</small></a>`).join('');
      const more = dayData.artworks.length > 3 ? `<span class="more">+${dayData.artworks.length - 3} more</span>` : '';
      cell.insertAdjacentHTML('beforeend', `<div class="artworks">${cards}${more}</div><div class="day-footer"><span class="delta ${dayData.followers_delta > 0 ? 'positive' : ''}">${dayData.followers_delta == null ? '—' : `${dayData.followers_delta >= 0 ? '+' : ''}${number(dayData.followers_delta)} followers`}</span><span class="post-count">${dayData.artworks.length} post${dayData.artworks.length === 1 ? '' : 's'}</span></div>`);
    }
    calendar.append(cell);
  }
}

document.querySelector('#prev-month').onclick = () => { state.date.setMonth(state.date.getMonth() - 1); loadCalendar(); };
document.querySelector('#next-month').onclick = () => { state.date.setMonth(state.date.getMonth() + 1); loadCalendar(); };
document.querySelector('#today').onclick = () => { state.date = new Date(); loadCalendar(); };
const patrolBtn = document.querySelector('#patrol-now');
const urlBtn = document.querySelector('#add-post-url');
const urlDialog = document.querySelector('#post-url-dialog');
const urlInput = document.querySelector('#post-url');
const urlSubmit = document.querySelector('#submit-post-url');
let detectionBusy = false;

function setDetectionBusy(busy, fromURL = false) {
  detectionBusy = busy;
  patrolBtn.disabled = busy;
  urlBtn.disabled = busy;
  urlSubmit.disabled = busy;
  urlInput.disabled = busy;
  patrolBtn.textContent = busy && !fromURL ? '巡回中…' : '🔍 新着チェック';
  urlSubmit.textContent = busy ? '確認・登録中…' : '追加する';
  document.querySelector('#post-url-form').setAttribute('aria-busy', String(busy));
}

function showDetectionFeedback(message, isError = false) {
  // Announce once: the calendar is inert while the modal is open.
  for (const selector of ['#detect-feedback', '#post-url-feedback']) {
    const target = document.querySelector(selector);
    target.textContent = message;
    target.dataset.error = String(isError);
  }
}

async function pollDetection() {
  while (true) {
    await new Promise(resolve => setTimeout(resolve, 3000));
    const response = await fetch('/api/detect/status');
    if (!response.ok) throw new Error('処理状況を取得できませんでした。時間をおいて再確認してください。');
    const status = await response.json();
    if (status.running) continue;
    const result = status.result || {};
    if (result.status === 'failed') throw new Error(result.message);
    if (result.status === 'registered' || result.status === 'already_registered') {
      showDetectionFeedback(result.status === 'registered'
        ? '作品を追加しました。数値の計測は定期実行で行います。'
        : 'この投稿は登録済みです。');
      if (result.posted_at) state.date = new Date(result.posted_at);
    } else {
      showDetectionFeedback(result.detected ? '新しい作品を追加しました。' : '新しい作品は見つかりませんでした。');
    }
    await loadCalendar();
    return;
  }
}

async function startDetection(url = null) {
  if (detectionBusy) return;
  setDetectionBusy(true, Boolean(url));
  showDetectionFeedback(url ? '投稿を確認して登録しています…' : '新着を確認しています…');
  try {
    const response = await fetch(url ? '/api/detect/url' : '/api/detect/trigger', {
      method: 'POST',
      ...(url ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) } : {}),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(typeof error.detail === 'string' ? error.detail : 'Xの投稿URLを確認してください。');
    }
    await pollDetection();
  } catch (error) {
    showDetectionFeedback(error.message || '通信に失敗しました。時間をおいて再実行してください。', true);
  } finally {
    setDetectionBusy(false);
  }
}

patrolBtn.onclick = () => startDetection();
urlBtn.onclick = () => {
  document.querySelector('#post-url-feedback').textContent = '';
  urlDialog.showModal();
  urlInput.focus();
};
document.querySelector('#close-post-url').onclick = () => urlDialog.close();
document.querySelector('#post-url-form').onsubmit = event => {
  event.preventDefault();
  startDetection(urlInput.value.trim());
};

// A reload or another tab may leave a manual check in progress.
fetch('/api/detect/status').then(response => {
  if (!response.ok) return null;
  return response.json();
}).then(async status => {
  if (!status?.running || detectionBusy) return;
  setDetectionBusy(true);
  showDetectionFeedback('新着の確認・登録を実行中です…');
  try { await pollDetection(); }
  catch (error) { showDetectionFeedback(error.message, true); }
  finally { setDetectionBusy(false); }
}).catch(error => console.error(error));
loadCalendar().catch(error => { document.querySelector('#calendar').innerHTML = `<p class="error">データを読み込めませんでした。API が起動しているか確認してください。</p>`; console.error(error); });
