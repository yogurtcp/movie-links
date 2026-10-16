/* Relative IMDb rating ranks. All genre comparisons use the title's own format. */
(() => {
  const number = new Intl.NumberFormat('en-US', {maximumFractionDigits: 1});
  const count = new Intl.NumberFormat('en-US');
  const percent = value => value < 0.1 ? '<0.1%' : value > 99.9 ? '>99.9%' : number.format(value) + '%';
  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function render(title) {
    const context = title.rating_context;
    if (!context?.overall) return document.createDocumentFragment();
    const movies = context.group === 'movies';
    const group = movies ? 'movies' : 'series';
    const section = element('section', undefined, 'rating-context');
    section.setAttribute('aria-label', 'IMDb rating percentiles for ' + title.title);
    section.append(element('p', `Rating percentiles within ${group}`, 'rating-context-heading'));
    const ranks = element('div', undefined, 'rating-percentiles');
    const values = [{label: 'All ' + group, ...context.overall}, ...context.genres.map(g => ({label: g.genre, ...g}))];
    for (let i = 0; i < values.length; i++) {
      const value = values[i];
      const chip = element('div', undefined, 'rank-chip' + (i === 0 ? ' overall-rank' : ''));
      chip.append(element('span', value.label), element('strong', percent(value.percentile)));
      chip.setAttribute('aria-label', `${value.label}: ${percent(value.percentile)} rating percentile among ${count.format(value.population)} ${context.comparison_label}`);
      if (value.small_group) chip.append(element('small', 'small group', 'small-comparison'));
      ranks.append(chip);
    }
    section.append(ranks);
    const details = element('details', undefined, 'rating-method');
    details.append(element('summary', 'Comparison groups & method'));
    details.append(element('p', `Compared with ${context.comparison_label} with at least ${count.format(context.minimum_votes_inclusive)} IMDb votes in the ${context.snapshot_date} snapshot, before our median-rating cutoff. Each title counts equally; vote totals do not weight the ranks.`));
    const table = element('table'), head = element('thead'), header = element('tr');
    for (const text of ['Comparison group', 'Titles', 'Percentile']) header.append(element('th', text));
    head.append(header); table.append(head);
    const body = element('tbody');
    for (let i = 0; i < values.length; i++) {
      const value = values[i], row = element('tr');
      row.append(element('td', i === 0 ? 'All ' + context.comparison_label : `${value.label} ${context.comparison_label}`), element('td', count.format(value.population)), element('td', percent(value.percentile)));
      body.append(row);
    }
    table.append(body); details.append(table);
    details.append(element('p', 'Percentile = 100 × (titles rated lower + half of titles with the same rating) ÷ group size. Tied IMDb scores receive the same percentile. This describes relative rating position, not a new IMDb score or a chance of enjoying the title.'));
    if (!movies) details.append(element('p', 'Series and miniseries share one comparison population.'));
    details.append(element('p', 'Genres overlap: a title belongs to each of its IMDb genres. Genre ranks are shown separately, without averaging them.'));
    if (values.some(value => value.small_group)) details.append(element('p', '“Small group” means fewer than 30 comparison titles; a few titles can noticeably change that percentile.'));
    section.append(details);
    return section;
  }
  globalThis.MovieLinksRatings = {render, percent};
})();
