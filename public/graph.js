const $ = id => document.getElementById(id);
const state = {titles: [], byId: new Map(), byLabel: new Map(), labels: new Map(), seed: null, data: null, request: 0, titleCache: new Map()};
const format = title => title.title_type === 'movie' ? 'Movie' : title.title_type === 'tvMiniSeries' ? 'Miniseries' : 'Series';
const shortLabel = title => `${title.title} · ${format(title)}`;
const label = title => state.labels.get(title.imdb_id) || `${title.title} (${title.start_year || 'year unknown'}) · ${format(title)}`;
const api = (path, options) => globalThis.MovieLinksAPI.request(path, options);
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function button(text, className, action) {
  const node = element('button', text, className); node.type = 'button'; node.onclick = action; return node;
}
function showError(error) { $('error').textContent = error.message; $('error').hidden = false; $('status').textContent = ''; }
function resolve(input) {
  const exact = state.byLabel.get(input.value);
  if (exact) return exact;
  const value = input.value.trim().toLowerCase();
  const matches = state.titles.filter(t => t.title.toLowerCase() === value || t.imdb_id === value);
  if (matches.length === 1) { input.value = label(matches[0]); return matches[0]; }
  throw Error('Choose a title from the suggestions. Each suggestion includes its year and whether it is a movie or show.');
}
function metadata(title) {
  const node = element('div', undefined, 'title-meta');
  node.append(element('span', format(title), 'format-pill'));
  if (title.start_year) node.append(element('span', String(title.start_year)));
  const imdb = element('a', title.rating ? `IMDb ${title.rating.toFixed(1)} ↗` : 'IMDb ↗', 'imdb-title-link');
  imdb.href = `https://www.imdb.com/title/${encodeURIComponent(title.imdb_id)}/`;
  imdb.target = '_blank'; imdb.rel = 'noopener noreferrer';
  imdb.setAttribute('aria-label', `Open ${shortLabel(title)} on IMDb (new tab)`);
  node.append(imdb);
  return node;
}
async function fullTitle(title) {
  if ('summary' in title && Array.isArray(title.genres)) return title;
  if (!state.titleCache.has(title.imdb_id)) {
    state.titleCache.set(title.imdb_id, api('/api/title?id=' + encodeURIComponent(title.imdb_id))
      .then(result => { if (!result.title) throw Error('This title is unavailable.'); return result.title; })
      .catch(error => { state.titleCache.delete(title.imdb_id); throw error; }));
  }
  return {...title, ...await state.titleCache.get(title.imdb_id)};
}
function description(title) {
  const details = element('details', undefined, 'description');
  const summary = element('summary', 'Read description');
  summary.append(element('small', 'may include spoilers'));
  const content = element('div'); details.append(summary, content);
  let loaded = false;
  details.addEventListener('toggle', async () => {
    if (!details.open || loaded) return;
    loaded = true; content.replaceChildren(element('p', 'Loading description…'));
    try {
      const full = await fullTitle(title);
      if (!details.isConnected) return;
      content.replaceChildren();
      if (full.genres?.length) content.append(element('p', full.genres.join(' · '), 'description-basis'));
      const text = full.summary || title.profile_summary;
      if (text) {
        content.append(element('p', full.summary ? `${full.source_provider === 'wikipedia' ? 'Wikipedia' : 'TVmaze'} description` : 'Provisional overview from the title profile', 'description-basis'));
        content.append(element('p', text));
      } else content.append(element('p', 'A description has not been collected for this title yet.'));
      if (full.summary && /^https:\/\/(www\.tvmaze\.com|en\.wikipedia\.org)\//.test(full.source_url || '')) {
        const source = element('a', 'Read the source · may contain more plot details'); source.href = full.source_url;
        source.target = '_blank'; source.rel = 'noopener noreferrer'; content.append(source, element('p', 'Source description: CC BY-SA. Attribution is linked above.', 'description-basis'));
      }
    } catch (error) { loaded = false; content.replaceChildren(element('p', error.message)); }
  });
  return details;
}
function connection(value) {
  const section = element('article', undefined, 'connection');
  section.append(element('h3', value.dimension_name), element('h4', value.shared_quality));
  const badge = element('span', value.review_status === 'accepted' ? 'Reviewed connection' : 'Suggested connection', 'badge' + (value.review_status === 'accepted' ? ' accepted' : ''));
  section.append(badge, element('p', value.explanation));
  if (value.differences) {
    const differences = element('details'); differences.append(element('summary', 'Differences · may include plot details'), element('p', value.differences)); section.append(differences);
  }
  const sources = element('details'); sources.append(element('summary', 'Basis & sources'));
  const seen = new Set();
  for (const evidence of value.evidence || []) {
    const key = evidence.imdb_id + '|' + evidence.source_url;
    if (!evidence.source_url || seen.has(key)) continue;
    seen.add(key);
    const title = state.byId.get(evidence.imdb_id);
    const link = element('a', `${title ? shortLabel(title) : evidence.imdb_id}: source (may include spoilers)`);
    link.href = evidence.source_url; link.target = '_blank'; link.rel = 'noopener noreferrer';
    const p = element('p'); p.append(link); sources.append(p);
  }
  sources.append(element('p', seen.size ? 'Sources support profile attributes. They do not verify that a recommendation will suit you. Plot excerpts stay hidden.' : 'These are shared model-assigned qualities. This connection has no cited passage attached.'));
  section.append(sources);
  if (value.id) {
    const controls = element('div', undefined, 'feedback');
    for (const [text, status] of [['Useful', 'accepted'], ['Not useful', 'rejected']]) {
      const control = button(text, '', async () => {
        control.disabled = true;
        try {
          await api('/api/connection-feedback', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({connection_id: value.id, status, connection: {title_a: value.title_a, title_b: value.title_b, dimension_slug: value.dimension_slug, shared_quality: value.shared_quality}})});
          badge.textContent = status === 'accepted' ? 'Reviewed connection' : 'Hidden from future results'; badge.className = 'badge' + (status === 'accepted' ? ' accepted' : '');
          for (const item of controls.children) item.setAttribute('aria-pressed', String(item === control));
        } catch (error) { showError(error); } finally { control.disabled = false; }
      });
      control.setAttribute('aria-pressed', String(value.review_status === status)); controls.append(control);
    }
    section.append(controls);
  }
  return section;
}
function libraryButton(title, key) {
  const text = () => key === 'seen' ? (title.seen ? 'Seen ✓' : 'Mark seen') : (title.watchlist ? 'Saved ✓' : 'Save');
  const control = button(text(), 'library-button' + (title[key] ? ' active' : ''), async () => {
    control.disabled = true;
    try {
      const result = await api('/api/library', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({imdb_id: title.imdb_id, [key]: !title[key]})});
      title[key] = result.title[key]; control.textContent = text(); control.classList.toggle('active', Boolean(title[key])); control.setAttribute('aria-pressed', String(Boolean(title[key])));
      if (key === 'seen' && $('unseen').checked) await load({page: state.data.page});
    } catch (error) { showError(error); } finally { control.disabled = false; }
  });
  control.setAttribute('aria-pressed', String(Boolean(title[key]))); control.setAttribute('aria-label', `${key === 'seen' ? 'Toggle seen status for' : 'Toggle watchlist for'} ${shortLabel(title)}`);
  return control;
}
function goTo(title) {
  $('seed').value = label(title);
  return load({navigation: 'push'});
}
function renderStartingTitle(title) {
  const out = $('starting-title'); out.replaceChildren(element('p', 'EXPLORING FROM', 'eyebrow'), metadata(title), element('h2', title.title, 'title-heading'));
  if (title.genres?.length) out.append(element('p', title.genres.join(' · '), 'genres'));
  out.append(description(title));
}
function recommendation(neighbor) {
  const title = neighbor.title;
  const card = element('article', undefined, 'recommendation-card'); card.id = 'title-' + title.imdb_id;
  const heading = element('h3', title.title, 'title-heading'); heading.tabIndex = -1;
  card.append(metadata(title), heading);
  const previews = element('ul', undefined, 'connection-preview');
  for (const value of neighbor.connections.slice(0, 3)) {
    const row = element('li'); row.append(element('span', value.dimension_name), element('strong', value.shared_quality));
    if (value.review_status === 'accepted') row.append(element('small', 'Reviewed connection', 'reviewed'));
    previews.append(row);
  }
  card.append(previews, description(title));
  const actions = element('div', undefined, 'card-actions');
  actions.append(button('Explore its connections →', 'explore-button', async () => {
    await goTo(title);
    $('starting-title').scrollIntoView({behavior: matchMedia('(prefers-reduced-motion:reduce)').matches ? 'instant' : 'smooth', block: 'start'});
  }), libraryButton(title, 'watchlist'), libraryButton(title, 'seen'));
  card.append(actions);
  const details = element('details', undefined, 'connection-breakdown');
  details.append(element('summary', `Why these connect · ${neighbor.connections.length} shared ${neighbor.connections.length === 1 ? 'quality' : 'qualities'}`));
  for (const value of neighbor.connections) details.append(connection(value));
  const profile = element('a', 'All profile dimensions →'); profile.href = '/explore/?' + new URLSearchParams({search: title.title, title: title.imdb_id});
  const p = element('p'); p.append(profile); details.append(p); card.append(details);
  return card;
}
function renderRecommendations(data) {
  const out = $('recommendations'); out.replaceChildren();
  if (!data.neighbors.length) out.append(element('p', 'No connected titles match these filters. Try another shared quality, include seen titles, or compare a specific pair below.', 'empty-connections'));
  else for (const neighbor of data.neighbors) out.append(recommendation(neighbor));
}
function renderMap(data) {
  const map = $('map'); map.replaceChildren();
  if (!data.neighbors.length) { map.append(element('p', 'No connections for these filters.', 'empty-connections')); return; }
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('viewBox', '0 0 100 100'); svg.setAttribute('preserveAspectRatio', 'none'); svg.setAttribute('aria-hidden', 'true'); map.append(svg);
  const coordinates = [[17,12],[83,12],[17,37],[83,37],[17,63],[83,63],[17,88],[83,88]];
  data.neighbors.forEach((neighbor, index) => {
    const [x,y] = coordinates[index]; const line = document.createElementNS(svg.namespaceURI, 'line');
    for (const [key,value] of Object.entries({x1:50,y1:50,x2:x,y2:y})) line.setAttribute(key,value);
    svg.append(line);
    const node = button('', 'node', () => {
      for (const card of document.querySelectorAll('.recommendation-card.highlight')) card.classList.remove('highlight');
      const card = $('title-' + neighbor.title.imdb_id); card.classList.add('highlight'); card.scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth'}); card.querySelector('h3').focus({preventScroll:true});
    });
    node.style.left = x + '%'; node.style.top = y + '%';
    node.append(element('small', `${format(neighbor.title)} · ${neighbor.title.start_year || 'Year unavailable'}`), element('strong', neighbor.title.title), element('em', neighbor.shared_quality)); map.append(node);
  });
  const seed = element('div', undefined, 'node seed'); seed.style.left = '50%'; seed.style.top = '50%';
  seed.append(element('small', `${format(data.seed)} · ${data.seed.start_year || 'Year unavailable'}`), element('strong', data.seed.title), element('small', 'EXPLORING FROM')); map.append(seed);
}
function renderPair(pair) {
  const out = $('pair'); out.replaceChildren(); if (!pair) return;
  out.append(element('h2', `${shortLabel(state.data.seed)} ↔ ${shortLabel(pair.title)}`, 'pair-heading'));
  for (const title of [state.data.seed, pair.title]) {
    const teaser = element('section', undefined, 'pair-title'); teaser.append(metadata(title), element('h3', title.title), description(title)); out.append(teaser);
  }
  if (!pair.connections.length) out.append(element('p', 'No shared qualities are assigned in the current profiles. This does not mean the titles have nothing in common.', 'pair-note'));
  for (const value of pair.connections) out.append(connection(value));
  if (pair.dimensions) {
    const details = element('details', undefined, 'comparison-table'); details.append(element('summary', 'All connection families, side by side'));
    const wrap = element('div', undefined, 'table-scroll'), table = element('table'), head = element('thead'), header = element('tr');
    for (const text of ['Shared quality', shortLabel(state.data.seed), shortLabel(pair.title)]) header.append(element('th', text));
    head.append(header); table.append(head); const body = element('tbody');
    for (const dimension of pair.dimensions) {
      const row = element('tr'); row.append(element('th', dimension.name));
      for (const key of ['left','right']) { const cell = element('td'); const value = dimension[key]; cell.append(element('span', value.positions.length ? value.positions.map(p=>p.description).join(' · ') : 'Unknown')); row.append(cell); }
      body.append(row);
    }
    table.append(body); wrap.append(table); details.append(wrap); out.append(details);
  }
}
async function load({page = 1, compare = false, navigation = 'replace'} = {}) {
  const token = ++state.request;
  $('recommendations').setAttribute('aria-busy', 'true');
  try {
    $('error').hidden = true;
    const seed = resolve($('seed'));
    const query = new URLSearchParams({seed: seed.imdb_id, page: String(page), dimension: $('dimension').value, unseen: $('unseen').checked ? '1' : '0'});
    if (compare) query.set('compare', resolve($('compare')).imdb_id);
    $('status').textContent = 'Finding connections…';
    const data = await api('/api/graph?' + query);
    if (token !== state.request) return;
    state.seed = seed; state.data = data;
    $('progress').textContent = `${data.progress.total.toLocaleString()} MOVIES & SHOWS`;
    $('status').textContent = `${(data.total_neighbors || 0).toLocaleString()} connected titles · ${data.neighbors.length} on this page`;
    $('previous').disabled = (data.page || 1) <= 1; $('next').disabled = (data.page || 1) >= (data.pages || 1); $('page-label').textContent = `Page ${data.page || 1} of ${data.pages || 1}`;
    renderStartingTitle(data.seed); renderRecommendations(data); renderPair(data.pair);
    if (!$('map-panel').hidden) renderMap(data);
    if (compare) $('compare-section').open = true;
    if (navigation !== 'none') {
      const url = new URL(location); url.search = '';
      url.searchParams.set('seed', seed.imdb_id);
      if (compare) url.searchParams.set('compare', query.get('compare'));
      if ($('dimension').value) url.searchParams.set('dimension', $('dimension').value);
      if ($('unseen').checked) url.searchParams.set('unseen', '1');
      if (data.page > 1) url.searchParams.set('page', String(data.page));
      history[navigation === 'push' ? 'pushState' : 'replaceState'](null, '', url);
    }
  } catch (error) { if (token === state.request) showError(error); }
  finally { if (token === state.request) $('recommendations').setAttribute('aria-busy', 'false'); }
}
function applyUrl() {
  const query = new URLSearchParams(location.search);
  const seed = state.byId.get(query.get('seed') || 'tt2560140') || state.titles[0];
  $('seed').value = label(seed); $('dimension').value = query.get('dimension') || ''; $('unseen').checked = query.get('unseen') === '1';
  const other = state.byId.get(query.get('compare'));
  if (other) $('compare').value = label(other);
  $('compare-section').open = Boolean(other);
  return load({page: Number(query.get('page')) || 1, compare: Boolean(other), navigation: 'none'});
}
$('search').addEventListener('submit', event => { event.preventDefault(); load({navigation:'push'}); });
$('compare-form').addEventListener('submit', event => { event.preventDefault(); load({compare:true,navigation:'push'}); });
$('dimension').addEventListener('change', () => load()); $('unseen').addEventListener('change', () => load());
$('previous').onclick = () => load({page: (state.data?.page || 1) - 1}); $('next').onclick = () => load({page: (state.data?.page || 1) + 1});
$('toggle-map').onclick = () => { const show = $('map-panel').hidden; $('map-panel').hidden = !show; $('toggle-map').setAttribute('aria-expanded',String(show)); $('toggle-map').textContent = show ? 'Hide map' : 'Show map'; if (show && state.data) renderMap(state.data); };
window.addEventListener('popstate', () => { if (state.titles.length) applyUrl(); });
(async () => {
  try {
    const data = await api('/api/graph-titles'); state.titles = data.titles; state.byId = new Map(data.titles.map(t=>[t.imdb_id,t]));
    const counts = new Map(); for (const title of data.titles) { const value = label(title); counts.set(value, (counts.get(value)||0)+1); }
    const fragment = document.createDocumentFragment();
    for (const title of data.titles) { let value = label(title); if (counts.get(value)>1) value += ` [${title.imdb_id}]`; state.labels.set(title.imdb_id,value); state.byLabel.set(value,title); const option=element('option'); option.value=value; fragment.append(option); }
    $('titles').append(fragment);
    for (const dimension of data.dimensions) { const option=element('option',dimension.name); option.value=dimension.slug; $('dimension').append(option); }
    await applyUrl();
  } catch (error) { showError(error); $('recommendations').setAttribute('aria-busy','false'); }
})();
