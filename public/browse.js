const $ = selector => document.querySelector(selector);
const controls = Object.fromEntries(['search','type','genre','library','sort'].map(key => [key, $('#' + key)]));
const list = $('#title-list');
const detail = $('#detail');
const number = new Intl.NumberFormat('en-US');
const compact = new Intl.NumberFormat('en-US', { notation:'compact', maximumFractionDigits:1 });
const initial = new URLSearchParams(location.search);
let state = { search:initial.get('search') || '', type:initial.get('type') || 'all', genre:initial.get('genre') || '', library:initial.get('library') || 'all', sort:initial.get('sort') || 'votes', profiled:initial.get('profiled')==='1'?'1':'', page:Math.max(1, Number(initial.get('page')) || 1) };
let selectedId = initial.get('title');
let selected = null;
let result = null;
let aborter;
let requestId = 0;
let searchTimer;
const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const format = title => title.title_type === 'movie' ? 'Movie' : title.title_type === 'tvMiniSeries' ? 'Miniseries' : 'Series';

function showError(message) {
  $('#error').textContent = message;
  $('#error').hidden = !message;
}
function syncUrl() {
  const query = new URLSearchParams();
  for (const [key,value] of Object.entries(state)) {
    if (value && !((key==='type'||key==='library')&&value==='all') && !(key==='sort'&&value==='votes') && !(key==='page'&&value===1)) query.set(key,value);
  }
  if (selectedId) query.set('title',selectedId);
  history.replaceState(null, '', location.pathname + (query.size ? '?' + query : ''));
}
function renderList() {
  list.replaceChildren();
  if (!result.titles.length) {
    const empty = document.createElement('p');
    empty.className = 'no-results';
    empty.textContent = state.library==='watchlist' ? 'Your watchlist has no matching titles yet. Save a title to start it.' : 'No titles match these filters. Try another search or genre.';
    list.append(empty);
  }
  for (const title of result.titles) {
    const button = document.createElement('button');
    button.className = 'title-row' + (title.imdb_id === selectedId ? ' selected' : '');
    button.type = 'button';
    button.setAttribute('aria-pressed',String(title.imdb_id===selectedId));
    button.setAttribute('aria-label',`${title.title}, ${title.start_year || 'year unknown'}, ${format(title)}, rating ${title.rating.toFixed(1)}, ${number.format(title.num_votes)} votes`);
    const markers = [title.seen ? 'Seen' : '', title.watchlist ? 'Watchlist' : ''].filter(Boolean).join(' · ');
    button.innerHTML = `<span><span class="row-name">${escape(title.title)}${markers ? `<span class="row-marker">${escape(markers)}</span>` : ''}</span><span class="row-description">${escape(title.start_year || '—')} · ${format(title)} · ${escape(title.genres.join(' / '))}</span></span><span class="row-rating">${title.rating.toFixed(1)}</span><span class="row-votes">${compact.format(title.num_votes)}</span>`;
    button.addEventListener('click',event=>{
      selected=title;selectedId=title.imdb_id;renderList();renderDetail();syncUrl();
      if(event.detail===0)list.querySelector('[aria-pressed="true"]')?.focus({preventScroll:true});
      if(window.matchMedia('(max-width:760px)').matches)detail.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth',block:'start'});
    });
    list.append(button);
  }
}
function renderDetail() {
  if (!selected) {
    detail.innerHTML='<p class="empty-detail">Choose a title to see its details.</p>';
    return;
  }
  const title = selected;
  const source = /^https:\/\/(www\.tvmaze\.com|en\.wikipedia\.org)\//.test(title.source_url || '') ? title.source_url : null;
  detail.innerHTML = `<div class="detail-head"><div class="detail-kicker">${format(title).toUpperCase()}</div><h2>${escape(title.title)}</h2><div class="detail-year">${escape(title.start_year || 'Year unavailable')}</div></div><div class="detail-body"><div class="detail-stats"><div class="detail-stat"><strong>${title.rating.toFixed(1)} <small>/ 10</small></strong><small>IMDb rating</small></div><div class="detail-stat"><strong>${number.format(title.num_votes)}</strong><small>User votes</small></div></div><div class="tags">${title.genres.map(genre=>`<span class="tag">${escape(genre)}</span>`).join('')}</div>${title.summary ? `<details class="spoiler-description"><summary>Plot description (may include spoilers)</summary><p class="summary">${escape(title.summary)}</p>${source ? `<div class="source-link">Source: <a href="${escape(source)}" target="_blank" rel="noreferrer">${title.source_provider==='wikipedia'?'Wikipedia':'TVmaze'} ↗</a> · CC BY-SA</div>` : ''}</details>` : `<p class="not-collected">${title.title_type==='movie' ? 'Movie descriptions haven’t been collected yet. You can open IMDb for more information.' : 'An exact TVmaze description wasn’t found for this title. You can open IMDb for more information.'}</p>`}<div class="detail-actions"><button type="button" class="action ${title.seen?'active':''}" id="mark-seen" aria-pressed="${title.seen}">${title.seen?'✓ Seen':'Mark as seen'}</button><button type="button" class="action ${title.watchlist?'active':''}" id="mark-watchlist" aria-pressed="${title.watchlist}">${title.watchlist?'✓ On watchlist':'+ Watchlist'}</button></div><a class="imdb-link" href="https://www.imdb.com/title/${encodeURIComponent(title.imdb_id)}/" target="_blank" rel="noreferrer">Open on IMDb ↗</a></div>`;
  const profilePanel=document.createElement('section');
  profilePanel.className='profile-section';profilePanel.setAttribute('aria-label','Derived title profile');
  profilePanel.innerHTML='<h3>Connection profile</h3><p class="profile-note">Loading the current assessment…</p>';
  detail.querySelector('.detail-body').append(profilePanel);
  loadProfile(title.imdb_id,profilePanel);
  $('#mark-seen').addEventListener('click',()=>updateLibrary('seen',!title.seen));
  $('#mark-watchlist').addEventListener('click',()=>updateLibrary('watchlist',!title.watchlist));
  const graphLink=document.createElement('a');graphLink.className='imdb-link';graphLink.href='/graph?seed='+encodeURIComponent(title.imdb_id);graphLink.textContent='Explore graph connections →';detail.querySelector('.detail-body').append(graphLink);
}
async function loadProfile(identifier,panel) {
  try {
    const body=await globalThis.MovieLinksAPI.request('/api/profile?id='+encodeURIComponent(identifier));
    if(selectedId!==identifier||!panel.isConnected)return;
    const profile=body.profile;
    if(!profile||profile.status==='awaiting_analysis') {
      panel.innerHTML='<h3>Connection profile</h3><p class="profile-note">This title is awaiting semantic analysis. Its descriptive positions have not been assigned yet.</p>';
      return;
    }
    const withheld=new Set(['resolution','character_arc','mystery','tragedy']);
    const safeDimensions=profile.dimensions.filter(d=>!withheld.has(d.slug));
    const assessed=safeDimensions.filter(d=>['source_supported','provisional'].includes(d.status));
    const unknown=safeDimensions.filter(d=>d.status==='unknown');
    const label=profile.status==='provisional'?'Provisional model assessment':'Source-based assessment · unreviewed';
    panel.innerHTML=`<h3>Connection profile</h3><p class="profile-note">${label}<br>${assessed.length} of ${safeDimensions.length} dimensions assessed. Endings, character destinations, revelations and tragic events are hidden.</p>${assessed.map(d=>`<section class="profile-dimension"><h4>${escape(d.name)}${d.status==='provisional'?'<span class="provisional">Provisional</span>':''}</h4>${d.claims.map(claim=>`<p>${escape(claim.description)}</p>${claim.evidence.length?`<details class="claim-evidence"><summary>Cited source (open source externally)</summary><p>A supporting passage is attached to this profile. It is hidden here because it may reveal plot details.</p><a href="${escape(claim.evidence[0].source_url)}" target="_blank" rel="noreferrer">${escape(claim.evidence[0].provider)} ↗</a></details>`:''}`).join('')}</section>`).join('')}${unknown.length?`<details class="unknown-dimensions"><summary>Unknown dimensions without ending or reveal details (${unknown.length})</summary><p>${unknown.map(d=>escape(d.name)).join(' · ')}</p></details>`:''}`;
  }catch(error){if(panel.isConnected)panel.innerHTML='<h3>Connection profile</h3><p class="profile-note">'+escape(error.message)+'</p>';}
}
async function updateLibrary(key,value) {
  const identifier=selected.imdb_id;
  $('#mark-seen').disabled=true;
  $('#mark-watchlist').disabled=true;
  showError('');
  try {
    const body=await globalThis.MovieLinksAPI.request('/api/library',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({imdb_id:identifier,[key]:value})});
    selected=body.title;
    $('#save-status').textContent = `${selected.title}: ${key==='seen' ? (value?'marked as seen':'marked as not seen') : (value?'added to your watchlist':'removed from your watchlist')}. Saved locally.`;
    await load();
  } catch(error) {
    showError(error.message);
    renderDetail();
  }
}
async function load() {
  const id=++requestId;
  aborter?.abort();
  aborter=new AbortController();
  list.setAttribute('aria-busy','true');
  showError('');
  try {
    const body=await globalThis.MovieLinksAPI.request('/api/catalog?'+new URLSearchParams(state),{signal:aborter.signal});
    if(id!==requestId)return;
    result=body;
    state.page=body.page;
    if (controls.genre.options.length===1) {
      for(const genre of body.genres) {
        const option=document.createElement('option');option.value=genre.genre;option.textContent=genre.genre;controls.genre.append(option);
      }
    }
    for(const [key,control] of Object.entries(controls))control.value=state[key];
    $('#profiled').checked=state.profiled==='1';
    selected=body.titles.find(title=>title.imdb_id===selectedId) || body.titles[0] || null;
    selectedId=selected?.imdb_id || null;
    $('#result-count').innerHTML=`<strong>${number.format(body.total)}</strong> ${body.total===1?'title':'titles'}${state.search ? ' matching “'+escape(state.search)+'”' : ''}`;
    $('#library-counts').textContent=`${number.format(body.library.seen)} seen · ${number.format(body.library.watchlist)} on watchlist`;
    $('#page-label').textContent=`Page ${body.page} of ${body.pages}`;
    $('#previous').disabled=body.page<=1;
    $('#next').disabled=body.page>=body.pages;
    renderList();renderDetail();syncUrl();
  } catch(error) {
    if(error.name!=='AbortError') {
      showError(error.message);
      $('#result-count').textContent='Catalog unavailable';
    }
  } finally {
    if(id===requestId)list.setAttribute('aria-busy','false');
  }
}
for(const [key,control] of Object.entries(controls)) {
  control.value=state[key];
  control.addEventListener(key==='search'?'input':'change',()=>{
    clearTimeout(searchTimer);
    state[key]=control.value;state.page=1;
    if(key==='search')searchTimer=setTimeout(load,180);
    else load();
  });
}
$('#previous').addEventListener('click',()=>{state.page--;load();});
$('#next').addEventListener('click',()=>{state.page++;load();});
$('#profiled').checked=state.profiled==='1';
$('#profiled').addEventListener('change',()=>{state.profiled=$('#profiled').checked?'1':'';state.page=1;load();});
await load();

if(globalThis.MOVIE_LINKS_DATA_URL)$('#save-status').textContent='Your seen titles and watchlist are saved in this browser.';
