const jstToday = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Tokyo' }).format(new Date());
const requestedMonth = new URLSearchParams(location.search).get('month');
const initialMonth = /^(20\d{2}|21\d{2}|2200)-(0[1-9]|1[0-2])$/.test(requestedMonth || '') ? requestedMonth : jstToday.slice(0, 7);
const state = { date: new Date(`${initialMonth}-01T12:00:00`), generation: 0 };
const monthName = new Intl.DateTimeFormat('ja-JP', { year: 'numeric', month: 'long' });
const number = value => value == null ? '—' : new Intl.NumberFormat('ja-JP').format(value);
const shortNumber = value => value == null ? '—' : value >= 10000 ? `${(value / 1000).toFixed(1)}k` : number(value);

async function loadCalendar() {
  state.controller?.abort();
  state.controller = new AbortController();
  const generation = ++state.generation;
  const year = state.date.getFullYear();
  const month = state.date.getMonth() + 1;
  document.querySelector('#month-title').textContent = monthName.format(state.date);
  const response = await fetch(`/api/calendar?year=${year}&month=${month}`, { signal: state.controller.signal });
  if (!response.ok) throw new Error('カレンダーを読み込めませんでした');
  const data = await response.json();
  if (generation !== state.generation) return;
  const profileLink = document.querySelector('#tracked-profile-link');
  if (data.tracked_profile_url) {
    profileLink.href = data.tracked_profile_url;
    profileLink.hidden = false;
  }
  const artworks = data.days.flatMap(day => day.artworks);
  const metricTotal = field => {
    const measured = artworks.map(artwork => artwork[field]).filter(value => value != null);
    return measured.length ? measured.reduce((a, b) => a + b, 0) : artworks.length ? null : 0;
  };
  renderSummary({ ...data.summary, likes: metricTotal('likes'), retweets: metricTotal('retweets') });
  renderCalendar(data);
  MonthOverview.renderCalendar(document.querySelector('#calendar-compact'), data);
  const url = new URL(location.href);
  url.searchParams.set('month', `${year}-${String(month).padStart(2, '0')}`);
  history.replaceState(null, '', url);
}

function renderSummary(summary) {
  const items = [['フォロワー', number(summary.followers), summary.followers_delta == null ? '期間データなし' : `期間中 ${summary.followers_delta >= 0 ? '+' : ''}${number(summary.followers_delta)}`], ['投稿数', number(summary.posts), '期間内の作品'], ['獲得いいね', number(summary.likes), '最新の計測値'], ['リポスト', number(summary.retweets), '最新の計測値']];
  document.querySelector('#summary').innerHTML = items.map(([label, value, note]) => `<div class="summary-item"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`).join('');
}

function renderCalendar(data) {
  const calendar = document.querySelector('#calendar');
  const first = new Date(data.year, data.month - 1, 1);
  const daysInMonth = new Date(data.year, data.month, 0).getDate();
  const byDate = Object.fromEntries(data.days.map(day => [day.date, day]));
  calendar.innerHTML = '';
  for (let i = 0; i < (first.getDay() + 6) % 7; i++) calendar.append(document.createElement('div'));
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

function calendarError(error) {
  if (error.name === 'AbortError') return;
  document.querySelector('#calendar').innerHTML = '<p class="error">データを読み込めませんでした。もう一度月を選択してください。</p>';
  document.querySelector('#calendar-compact').textContent = 'データを読み込めませんでした。もう一度月を選択してください。';
  document.querySelector('#summary').innerHTML = '';
  console.error(error);
}
document.querySelector('#prev-month').onclick = () => { if (state.date.getFullYear() === 2000 && state.date.getMonth() === 0) return; state.date.setMonth(state.date.getMonth() - 1); loadCalendar().catch(calendarError); };
document.querySelector('#next-month').onclick = () => { if (state.date.getFullYear() === 2200 && state.date.getMonth() === 11) return; state.date.setMonth(state.date.getMonth() + 1); loadCalendar().catch(calendarError); };
document.querySelector('#today').onclick = () => { state.date = new Date(`${jstToday.slice(0, 7)}-01T12:00:00`); loadCalendar().catch(calendarError); };
document.querySelector('#calendar-display').onclick = (event) => {
  const showImages = event.currentTarget.getAttribute('aria-pressed') !== 'true';
  event.currentTarget.setAttribute('aria-pressed', String(showImages));
  event.currentTarget.textContent = showImages ? '月の概要を表示' : '作品画像を表示';
  document.body.classList.toggle('show-calendar-images', showImages);
};
const startWithImages = window.matchMedia('(min-width: 761px)').matches;
document.body.classList.toggle('show-calendar-images', startWithImages);
document.querySelector('#calendar-display').setAttribute('aria-pressed', String(startWithImages));
document.querySelector('#calendar-display').textContent = startWithImages ? '月の概要を表示' : '作品画像を表示';
const patrolBtn = document.querySelector('#patrol-now');

patrolBtn.onclick = async () => {
  patrolBtn.disabled = true;
  patrolBtn.textContent = '巡回中…';
  try {
    const response = await fetch('/api/detect/trigger', { method: 'POST' });
    if (!response.ok) {
      const error = await response.json();
      alert(error.detail);
      patrolBtn.textContent = '🔍 新着チェック';
      patrolBtn.disabled = false;
      return;
    }

    const poll = setInterval(async () => {
      try {
        const status = await fetch('/api/detect/status').then(result => result.json());
        if (!status.running) {
          clearInterval(poll);
          patrolBtn.textContent = '🔍 新着チェック';
          patrolBtn.disabled = false;
          location.reload();
        }
      } catch (error) {
        clearInterval(poll);
        patrolBtn.textContent = '🔍 新着チェック';
        patrolBtn.disabled = false;
        console.error(error);
      }
    }, 3000);
  } catch (error) {
    patrolBtn.textContent = '🔍 新着チェック';
    patrolBtn.disabled = false;
    console.error(error);
  }
};
loadCalendar().catch(calendarError);
