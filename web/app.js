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
    cell.className = 'day-cell';
    cell.innerHTML = `<div class="day-number">${day}</div>`;
    if (dayData) {
      const cards = dayData.artworks.slice(0, 3).map(art => `<a class="art-card" href="/artworks/${art.id}"><div class="thumb">${art.image_url ? `<img src="${art.image_url}" alt="">` : '<span>NO IMAGE</span>'}</div><div class="art-meta"><b>${shortNumber(art.likes)} likes</b><span>↗ ${shortNumber(art.retweets)}</span></div><small>${new Date(art.posted_at).toLocaleTimeString('ja-JP', {hour: '2-digit', minute: '2-digit'})}</small></a>`).join('');
      const more = dayData.artworks.length > 3 ? `<span class="more">+${dayData.artworks.length - 3} more</span>` : '';
      cell.insertAdjacentHTML('beforeend', `<div class="artworks">${cards}${more}</div><div class="day-footer"><span class="delta ${dayData.followers_delta > 0 ? 'positive' : ''}">${dayData.followers_delta == null ? '—' : `${dayData.followers_delta >= 0 ? '+' : ''}${number(dayData.followers_delta)} followers`}</span><span>${dayData.artworks.length} post${dayData.artworks.length === 1 ? '' : 's'}</span></div>`);
    }
    calendar.append(cell);
  }
}

document.querySelector('#prev-month').onclick = () => { state.date.setMonth(state.date.getMonth() - 1); loadCalendar(); };
document.querySelector('#next-month').onclick = () => { state.date.setMonth(state.date.getMonth() + 1); loadCalendar(); };
document.querySelector('#today').onclick = () => { state.date = new Date(); loadCalendar(); };
loadCalendar().catch(error => { document.querySelector('#calendar').innerHTML = `<p class="error">データを読み込めませんでした。API が起動しているか確認してください。</p>`; console.error(error); });
