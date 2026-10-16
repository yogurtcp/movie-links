/* Optional genre leaderboards. Rating context uses the complete 50K-vote scope. */
(() => {
  const $ = id => document.getElementById(id);
  const number = new Intl.NumberFormat('en-US');
  const initial = new URLSearchParams(location.search);
  const state = {type: initial.get('type') === 'tv' ? 'tv' : 'movies', genre: initial.get('genre') ?? 'Comedy', page: Math.max(1, Number(initial.get('page')) || 1)};
  let data;
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  const format = title => title.title_type === 'movie' ? 'Movie' : title.title_type === 'tvMiniSeries' ? 'Miniseries' : 'Series';
  function link(text, href, className) {
    const node = element('a', text, className); node.href = href; return node;
  }
  function description(title) {
    const details = element('details', undefined, 'description');
    const summary = element('summary', 'Read description'); summary.append(element('small', 'may include spoilers'));
    const content = element('div'); details.append(summary, content);
    let loaded = false;
    details.addEventListener('toggle', async () => {
      if (!details.open || loaded) return;
      loaded = true; content.replaceChildren(element('p', 'Loading description…'));
      try {
        const {title: full} = await globalThis.MovieLinksAPI.request('/api/title?id=' + encodeURIComponent(title.imdb_id));
        if (!details.isConnected) return;
        content.replaceChildren(element('p', full?.summary || 'A description has not been collected for this title yet. You can read more on IMDb.'));
        if (full?.summary && /^https:\/\/(www\.tvmaze\.com|en\.wikipedia\.org)\//.test(full.source_url || '')) {
          const source = link(`Source: ${full.source_provider === 'wikipedia' ? 'Wikipedia' : 'TVmaze'} · CC BY-SA · may include more plot details`, full.source_url);
          source.target = '_blank'; source.rel = 'noopener noreferrer'; content.append(source);
        }
      } catch (error) { loaded = false; content.replaceChildren(element('p', error.message)); }
    });
    return details;
  }
  function renderCard(title, rank) {
    const card = element('li', undefined, 'ranking-card'); card.value = rank;
    const rankLabel = element('span', '#' + rank, 'rank-number'); rankLabel.setAttribute('aria-label', 'Rank ' + rank);
    const meta = element('div', undefined, 'title-meta');
    meta.append(element('span', format(title), 'format-pill'), element('span', title.start_year || 'Year unavailable'), element('span', title.genres.join(' · ')));
    card.append(rankLabel, meta, element('h3', title.title));
    const context = title.rating_context;
    const comparison = state.genre ? context.genres.find(g => g.genre === state.genre) : context.overall;
    const group = state.type === 'movies' ? 'movies' : 'series & miniseries';
    const scores = element('div', undefined, 'ranking-scores');
    const rating = element('div'); rating.append(element('strong', title.rating.toFixed(1) + ' / 10'), element('small', 'IMDb · ' + number.format(title.num_votes) + ' votes'));
    const relative = element('div', undefined, 'genre-score');
    relative.append(element('strong', globalThis.MovieLinksRatings.percent(comparison.percentile) + ' percentile'), element('small', `${state.genre ? state.genre + ' · ' : ''}${number.format(comparison.population)} ${group}${comparison.small_group ? ' · small group' : ''}`));
    scores.append(rating, relative); card.append(scores);
    const actions = element('div', undefined, 'card-actions');
    if (title.in_catalog) {
      actions.append(link('Explore connections →', '/graph/?seed=' + encodeURIComponent(title.imdb_id), 'explore-button'));
      card.append(description(title));
    } else card.append(element('p', 'Connections and descriptions haven’t been mapped for this title yet.', 'unmapped'));
    const imdb = link('Open on IMDb ↗', 'https://www.imdb.com/title/' + encodeURIComponent(title.imdb_id) + '/', 'imdb-title-link');
    imdb.target = '_blank'; imdb.rel = 'noopener noreferrer'; imdb.setAttribute('aria-label', `Open ${title.title} (${format(title)}) on IMDb · may include spoilers`);
    actions.append(imdb); card.append(actions); return card;
  }
  function render(scrollToTop = false) {
    const rows = data.titles.filter(t => t.rating_context.group === state.type && (!state.genre || t.genres.includes(state.genre)))
      .sort((a, b) => b.rating - a.rating || b.num_votes - a.num_votes || a.imdb_id.localeCompare(b.imdb_id));
    const pages = Math.max(1, Math.ceil(rows.length / 20)); state.page = Math.min(state.page, pages);
    const group = state.type === 'movies' ? 'movies' : 'series & miniseries';
    $('ranking-heading').textContent = `Highest-rated ${state.genre ? state.genre.toLowerCase() + ' ' : ''}${group}`;
    $('status').textContent = `${number.format(rows.length)} titles · 50,000+ votes · 15 October 2026 snapshot${rows.length && rows.length < 30 ? ' · Small comparison group' : ''}`;
    const ranks = []; let rank = 0;
    rows.forEach((title, i) => { if (!i || title.rating !== rows[i - 1].rating) rank = i + 1; ranks.push(rank); });
    const start = (state.page - 1) * 20;
    $('rankings').replaceChildren(...rows.slice(start, start + 20).map((title, i) => renderCard(title, ranks[start + i])));
    if (!rows.length) $('rankings').append(element('li', 'No titles with at least 50,000 votes in this group. Choose another genre or format.', 'empty-connections'));
    $('rankings').start = start + 1; $('rankings').setAttribute('aria-busy', 'false');
    $('previous').disabled = state.page <= 1; $('next').disabled = state.page >= pages;
    $('page-label').textContent = `Page ${state.page} of ${pages}`;
    const query = new URLSearchParams({type: state.type, genre: state.genre});
    if (state.page > 1) query.set('page', String(state.page));
    history.replaceState(null, '', location.pathname + '?' + query);
    if (scrollToTop) window.scrollTo({top: 0, left: 0, behavior: 'instant'});
  }
  function genreOptions() {
    $('genre').replaceChildren();
    const all = element('option', 'All genres'); all.value = ''; $('genre').append(all);
    for (const genre of data.genres[state.type]) { const option = element('option', genre); option.value = genre; $('genre').append(option); }
    if (state.genre && !data.genres[state.type].includes(state.genre)) state.genre = '';
    $('genre').value = state.genre;
  }
  $('type').addEventListener('change', () => { state.type = $('type').value; state.page = 1; genreOptions(); render(); });
  $('genre').addEventListener('change', () => { state.genre = $('genre').value; state.page = 1; render(); });
  $('previous').addEventListener('click', () => { state.page--; render(true); });
  $('next').addEventListener('click', () => { state.page++; render(true); });
  (async () => {
    try {
      const response = await fetch(globalThis.MOVIE_LINKS_RANKINGS_URL || '/api/rankings');
      if (!response.ok) throw Error('Rankings could not be loaded. Please reload to try again.');
      data = await response.json(); $('type').value = state.type; genreOptions(); render();
      $('type').disabled = false; $('genre').disabled = false;
    } catch (error) {
      $('error').hidden = false; $('error').textContent = error.message;
      $('status').textContent = 'Rankings unavailable'; $('rankings').setAttribute('aria-busy', 'false');
    }
  })();
})();
