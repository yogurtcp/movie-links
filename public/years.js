/* The same yearly statistics, recalculated for each vote-count population. */
(() => {
  const $ = id => document.getElementById(id);
  const count = new Intl.NumberFormat('en-US');
  let metadata;
  function apply() {
    const popular = $('votes').value === '50000';
    const suffix = popular ? '-50k' : '';
    const label = popular ? '50,000+ votes' : 'All vote counts';
    const groups = ['movies', 'tv'].map(format => metadata.groups[format + suffix]);
    for (const [index, format] of ['movies', 'tv'].entries()) {
      const group = groups[index];
      const title = format === 'movies' ? 'Movies' : 'Series & miniseries';
      const base = '/plots/imdb-score-by-year-' + format + suffix;
      $(format + '-image').src = base + '.png';
      $(format + '-image').alt = `${title}: yearly mean, median and 90th-percentile IMDb scores for ${count.format(group.plotted_titles)} titles, ${label.toLowerCase()}, ${group.first_year}–${group.last_year}. Every title counts equally.`;
      $(format + '-open').href = base + '.png';
      for (const extension of ['png', 'pdf', 'csv']) $(format + '-' + extension).href = base + '.' + extension;
      $(format + '-caption').textContent = `${title} · ${count.format(group.plotted_titles)} titles · ${label}`;
    }
    $('scope-status').textContent = `${label}: ${count.format(groups[0].plotted_titles)} movies and ${count.format(groups[1].plotted_titles)} series/miniseries. No rating cutoff.`;
    $('overall-medians').textContent = `Across all release years, the median is ${groups[0].overall_median.toFixed(1)} for movies and ${groups[1].overall_median.toFixed(1)} for series in this group. The plotted medians are calculated separately for each year.`;
    const missing = groups.reduce((sum, group) => sum + group.missing_release_year, 0);
    $('missing-years').textContent = `${count.format(missing)} other rated titles in this vote group lack a release year and cannot be plotted.`;
    const url = new URL(location); url.searchParams.set('votes', popular ? '50000' : '0'); history.replaceState(null, '', url);
  }
  $('votes').addEventListener('change', apply);
  (async () => {
    try {
      const response = await fetch('/plots/imdb-score-by-year.json');
      if (!response.ok) throw Error('Could not load the graph filter. Please reload to try again.');
      metadata = await response.json();
      $('votes').value = new URLSearchParams(location.search).get('votes') === '0' ? '0' : '50000';
      apply(); $('votes').disabled = false;
    } catch (error) { $('filter-error').hidden = false; $('filter-error').textContent = error.message; }
  })();
})();
