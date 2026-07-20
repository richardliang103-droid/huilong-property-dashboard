const state = {data: null, filters: {search: '', source: 'all', sort: 'price-asc', fresh: 'all'}};
const $ = selector => document.querySelector(selector);
const escapeHtml = value => String(value).replace(/[&<>'"]/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[char]));
const val = (value, fallback = '—') => value == null || value === '' ? fallback : value;
const text = (value, fallback = '—') => escapeHtml(val(value, fallback));
const money = value => value == null || value === '' ? '—' : `${Number(value).toLocaleString('zh-TW')} 萬`;
function dateText(value) { return value ? escapeHtml(String(value).replace('T', ' ').slice(0, 16)) : '—'; }
function safeUrl(value) {
  try {
    const url = new URL(String(value));
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '#';
  } catch (_) {
    return '#';
  }
}
function today() { return state.data.generated_at.slice(0, 10); }
function isNew(item) { return item['首次出現'] === today() && !item['重新上架日期']; }
function isRelisted(item) { return item['重新上架日期'] === today(); }
function isPendingRemoval(item) { return String(item['備註'] || '').includes('[待確認下架:'); }
function sourceMatch(item) { return state.filters.source === 'all' || String(item['來源網站'] || '').includes(state.filters.source); }
function searchMatch(item) {
  const query = state.filters.search.trim().toLowerCase();
  return !query || ['社區名稱', '地址', '標題', '格局'].some(key => String(item[key] || '').toLowerCase().includes(query));
}
function filtered() {
  const rows = state.data.active.filter(item => sourceMatch(item) && searchMatch(item) && (state.filters.fresh === 'all' || isNew(item)));
  return rows.sort((a, b) => {
    if (state.filters.sort === 'price-desc') return (b['總價(萬)'] || 0) - (a['總價(萬)'] || 0);
    if (state.filters.sort === 'area-desc') return (b['建坪'] || 0) - (a['建坪'] || 0);
    if (state.filters.sort === 'updated') return String(b['最後更新'] || '').localeCompare(String(a['最後更新'] || ''));
    return (a['總價(萬)'] || 0) - (b['總價(萬)'] || 0);
  });
}
function renderMetrics() {
  const data = state.data;
  const fresh = data.active.filter(isNew).length;
  const relisted = data.active.filter(isRelisted).length;
  const pending = data.active.filter(isPendingRemoval).length;
  $('#hero-count').textContent = data.active.length;
  $('#metrics').innerHTML = [['架上物件', data.active.length], ['新上架', fresh], ['重新上架', relisted], ['待確認下架', pending], ['價格變動', data.price_changes.length]].map(metric => `<div class="metric"><span>${metric[0]}</span><strong>${metric[1]}</strong></div>`).join('');
  const callout = $('#new-callout');
  if (!fresh) {
    callout.hidden = true;
    callout.innerHTML = '';
    return;
  }
  callout.hidden = false;
  callout.innerHTML = `<div><strong>今日有 ${fresh} 間新上架</strong><span>優先查看今天首次出現的物件</span></div><button id="new-only" class="new-only ${state.filters.fresh === 'new' ? 'active' : ''}" type="button">${state.filters.fresh === 'new' ? '顯示全部架上' : '只看新上架'}</button>`;
  $('#new-only').addEventListener('click', () => {
    state.filters.fresh = state.filters.fresh === 'new' ? 'all' : 'new';
    renderMetrics();
    renderListings();
  });
}
function renderListings() {
  const rows = filtered();
  $('#result-count').textContent = `／ ${rows.length} 筆`;
  if (!rows.length) {
    $('#listings').innerHTML = '<div class="empty">找不到符合條件的物件</div>';
    return;
  }
  $('#listings').innerHTML = rows.map(item => {
    const fresh = isNew(item);
    const relisted = isRelisted(item);
    const badges = [
      fresh ? '<span class="badge badge-new">新上架</span>' : '',
      relisted ? '<span class="badge badge-relisted">重新上架</span>' : '',
      isPendingRemoval(item) ? '<span class="badge badge-pending">待確認下架</span>' : '',
    ].filter(Boolean).join('');
    const title = text(item['標題'], item['社區名稱'] || item['地址'] || '—');
    const community = text(item['社區名稱'], item['地址'] || '—');
    return `<article class="listing ${fresh ? 'is-new ' : ''}${relisted ? 'is-relisted' : ''}"><div class="listing-top"><div><div class="listing-title">${title}</div><div class="community">${community}・${text(item['行政區'])}</div></div><div class="badges">${badges}</div></div><div class="price">${money(item['總價(萬)'])} <small>總價</small></div><div class="facts"><div class="fact"><span>建坪</span><strong>${text(item['建坪'])} 坪</strong></div><div class="fact"><span>格局</span><strong>${text(item['格局'])}</strong></div><div class="fact"><span>樓層</span><strong>${text(item['樓層'])}</strong></div><div class="fact"><span>屋齡</span><strong>${text(item['屋齡(年)'])} 年</strong></div><div class="fact"><span>車位</span><strong>${text(item['車位型'])}</strong></div><div class="fact"><span>更新</span><strong>${dateText(item['最後更新'])}</strong></div></div><div class="listing-bottom"><span class="listing-source">來源：${text(item['來源網站'])}</span><a href="${safeUrl(item['來源連結'])}" target="_blank" rel="noopener noreferrer">查看房源 →</a><a href="${safeUrl(item['地圖連結'])}" target="_blank" rel="noopener noreferrer">地圖 →</a></div></article>`;
  }).join('');
}
function renderSourceHealth() {
  const health = state.data.source_health;
  const section = $('#source-health-section');
  if (!health || !health.sources) {
    section.hidden = true;
    return;
  }
  const sources = Object.values(health.sources);
  section.hidden = false;
  $('#source-health-note').textContent = health.removal_allowed ? '本次資料完整，已啟用下架判定' : '本次有來源不完整，已暫停下架判定';
  $('#source-health').innerHTML = sources.map(source => {
    const stateText = source.complete ? '資料完整' : source.error ? '抓取失敗' : '資料不完整';
    const error = source.error ? `<small>${text(source.error)}</small>` : '';
    return `<article class="source-card ${source.complete ? 'is-healthy' : 'is-warning'}"><strong>${text(source.name)}</strong><span>${stateText}</span><b>${text(source.collected, 0)} 筆</b>${error}</article>`;
  }).join('');
}
function renderHistory() {
  const rows = [
    ...(state.data.price_changes || []).map(item => ({date: item['日期'], name: text(item['社區名稱'], '物件'), detail: `${money(item['舊總價(萬)'])} → ${money(item['新總價(萬)'])}`, type: '價格變動'})),
    ...(state.data.removed || []).slice(0, 20).map(item => ({date: item['下架日期'], name: text(item['標題'], item['社區名稱'] || '物件'), detail: money(item['總價(萬)']), type: '下架'})),
  ].sort((a, b) => String(b.date).localeCompare(String(a.date)));
  $('#history').innerHTML = rows.length ? rows.map(item => `<div class="history-row"><span>${dateText(item.date)}</span><strong>${item.name}</strong><span>${item.detail}</span><span>${item.type}</span></div>`).join('') : '<div class="empty">目前沒有變動紀錄</div>';
}
function render() {
  renderMetrics();
  renderSourceHealth();
  renderListings();
  renderHistory();
  $('#updated').textContent = `資料更新 ${dateText(state.data.generated_at)}`;
  $('#footer-date').textContent = `　最後匯出：${dateText(state.data.generated_at)}`;
}
async function init() {
  try {
    state.data = await fetch('data/properties.json', {cache: 'no-store'}).then(response => {
      if (!response.ok) throw Error('data');
      return response.json();
    });
    render();
  } catch (_) {
    $('#listings').innerHTML = '<div class="empty">資料載入失敗，請稍後重新整理。</div>';
  }
}
$('#search').addEventListener('input', event => { state.filters.search = event.target.value; renderListings(); });
$('#source').addEventListener('change', event => { state.filters.source = event.target.value; renderListings(); });
$('#sort').addEventListener('change', event => { state.filters.sort = event.target.value; renderListings(); });
$('#reset').addEventListener('click', () => {
  $('#search').value = '';
  $('#source').value = 'all';
  $('#sort').value = 'price-asc';
  state.filters = {search: '', source: 'all', sort: 'price-asc', fresh: 'all'};
  renderMetrics();
  renderListings();
});
init();
