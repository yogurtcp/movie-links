/* Shared transport for the local server and the hosted browser app. */
(() => {
  const SKIP = new Set(['minimal', 'linear', 'grounded-realism', 'emotional-investment', 'clear-answers', 'completed-arcs', 'continuing-story']);
  const libraryKey = 'movie-links-library-v1';
  const feedbackKey = 'movie-links-feedback-v1';
  let loading;
  const readable = value => value.replaceAll('-', ' ');
  const capitalized = value => value.charAt(0).toUpperCase() + value.slice(1);
  const readStore = key => { try { const value=JSON.parse(localStorage.getItem(key) || '{}'); return value && typeof value==='object' && !Array.isArray(value) ? value : {}; } catch { return {}; } };
  function writeStore(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); }
    catch { throw Error('Your browser could not save this change. Allow site storage and try again.'); }
  }
  async function jsonResponse(response) {
    const raw = await response.text();
    let value;
    try { value = JSON.parse(raw); }
    catch { throw Error(`This address did not return Movie Links data (HTTP ${response.status}). Open the Movie Links app URL or start its local server.`); }
    if (!response.ok) throw Error(value.error || `The request failed (HTTP ${response.status}).`);
    return value;
  }
  async function dataset() {
    if (!loading) loading = fetch(globalThis.MOVIE_LINKS_DATA_URL).then(jsonResponse).then(data => {
      data.byId = new Map(data.titles.map(t => [t.imdb_id, t]));
      data.dimensionsBySlug = new Map(data.dimensions.map(d => [d.slug, d]));
      data.adjacent = new Map();
      const add = (id, edge) => { if (!data.adjacent.has(id)) data.adjacent.set(id, []); data.adjacent.get(id).push(edge); };
      for (const row of data.edges) {
        const a = data.titles[row[1]].imdb_id, b = data.titles[row[2]].imdb_id;
        const edge = {id: row[0], title_a: a, title_b: b, dimension_slug: data.dimensions[row[3]].slug,
          shared_quality: row[4], ranking_weight: row[5], review_status: 'unreviewed'};
        add(a, edge); add(b, edge);
      }
      for (const edge of data.manual) { add(edge.title_a, edge); add(edge.title_b, edge); }
      return data;
    }).catch(error => { loading = null; throw error; });
    return loading;
  }
  function claims(data, id, slug) {
    const profile = data.profiles[id];
    const positions = (profile?.positions[slug] || []).map(tag => ({trait: tag, label: tag,
      description: capitalized(readable(tag)), evidence_type: 'inferred', review_status: 'unreviewed', evidence: []}));
    for (const extra of profile?.extras[slug] || []) {
      const found = positions.find(c => c.trait === extra.trait && c.description === extra.description);
      if (found) Object.assign(found, extra); else positions.push({...extra, label: extra.trait});
    }
    return positions;
  }
  function assessment(data, id, dimension) {
    const values = claims(data, id, dimension.slug);
    const status = data.profiles[id]?.positions[dimension.slug]?.length ? 'provisional' : values.length ? 'source_supported' : 'unknown';
    return {...dimension, status, reason: status === 'unknown' ? 'Insufficient knowledge or material in this pass.' : 'Model interpretation; individual review remains necessary.', claims: values};
  }
  function title(data, id, library) {
    const row = data.byId.get(id);
    return row ? {...row, seen: Boolean(library[id]?.seen), watchlist: Boolean(library[id]?.watchlist),
      profile_status: data.profiles[id]?.status || 'awaiting_analysis', profile_summary: data.profiles[id]?.summary || ''} : null;
  }
  const identity = edge => [edge.title_a, edge.title_b, edge.dimension_slug, edge.shared_quality].join('|');
  function status(edge, feedback) { return feedback[identity(edge)] || edge.review_status; }
  function edgeDetails(data, edge, feedback) {
    const dimension = data.dimensionsBySlug.get(edge.dimension_slug);
    const a = data.byId.get(edge.title_a), b = data.byId.get(edge.title_b);
    const evidence = [a, b].flatMap(t => claims(data, t.imdb_id, edge.dimension_slug).flatMap(c => c.evidence.map(e => ({...e, imdb_id: t.imdb_id}))));
    let differences = edge.differences;
    if (!differences) {
      // Keep profile summaries behind the UI's explicit plot-details disclosure.
      differences = [a, b].map(t => `${t.title}: ${data.profiles[t.imdb_id].summary}`).join('\n');
      const shared = new Set(edge.shared_quality.split(', '));
      const other = [a, b].map(t => `${t.title} — ${claims(data, t.imdb_id, dimension.slug).map(c => readable(c.trait || '')).filter(v => !shared.has(v)).join(', ') || 'none assigned'}`);
      differences += '\nOther positions in this family: ' + other.join('; ') + '.';
    }
    return {...edge, dimension_name: dimension.name, review_status: status(edge, feedback), evidence,
      explanation: edge.explanation || `Both current profiles include ${edge.shared_quality} under ${dimension.name.toLowerCase()}. This is a provisional candidate connection; its usefulness still needs review.`, differences};
  }
  function compare(data, seed, other, feedback, library) {
    const saved = (data.adjacent.get(seed.imdb_id) || []).filter(e => e.title_a === other.imdb_id || e.title_b === other.imdb_id);
    const savedFamilies = new Set(saved.map(e => e.dimension_slug));
    const connections = saved.filter(e => status(e, feedback) !== 'rejected')
      .sort((a,b) => Number(status(b,feedback)==='accepted') - Number(status(a,feedback)==='accepted') || (b.ranking_weight||0)-(a.ranking_weight||0))
      .map(e => edgeDetails(data, e, feedback));
    const dimensions = data.dimensions.map(d => {
      const left = assessment(data, seed.imdb_id, d), right = assessment(data, other.imdb_id, d);
      if (!savedFamilies.has(d.slug)) {
        const labels = new Set(right.claims.map(c => c.trait));
        const shared = [...new Set(left.claims.map(c => c.trait).filter(t => labels.has(t) && !SKIP.has(t)))].sort().map(readable);
        if (shared.length) connections.push({id: null, dimension_slug: d.slug, dimension_name: d.name, shared_quality: shared.join(', '),
          explanation: 'Both current profiles have these provisional positions. This pair has not been individually reviewed.',
          differences: [[seed,left],[other,right]].map(([t,p]) => `${t.title}: ${p.claims.map(c => c.description).join(', ')}`).join('\n'),
          review_status: 'unreviewed', evidence: []});
      }
      return {...d, left: {status: left.status, positions: left.claims}, right: {status: right.status, positions: right.claims}};
    });
    return {title: title(data, other.imdb_id, library), connections, dimensions,
      note: 'A connection describes a particular shared quality. It is not a prediction of overall enjoyment.'};
  }
  function graph(data, params, library, feedback) {
    const seed = title(data, params.get('seed'), library);
    if (!seed) throw Error('Choose a title from the catalog');
    const dimension = params.get('dimension');
    const edges = (data.adjacent.get(seed.imdb_id) || []).filter(e => status(e, feedback) !== 'rejected' && (!dimension || e.dimension_slug === dimension))
      .sort((a,b) => Number(status(b,feedback)==='accepted') - Number(status(a,feedback)==='accepted') || (b.ranking_weight||0)-(a.ranking_weight||0) || a.id-b.id);
    const grouped = new Map();
    for (const edge of edges) {
      const other = edge.title_a === seed.imdb_id ? edge.title_b : edge.title_a;
      if (!matchesFilters(data.byId.get(other), params)) continue;
      if (params.get('unseen') === '1' && library[other]?.seen) continue;
      if (!grouped.has(other)) grouped.set(other, []);
      grouped.get(other).push(edge);
    }
    const measure = id => {const rows=grouped.get(id);return {accepted: rows.some(e=>status(e,feedback)==='accepted'),families: new Set(rows.map(e=>e.dimension_slug)).size,weight: rows.reduce((n,e)=>n+(e.ranking_weight||0),0)};};
    const ranked = [...grouped.keys()].sort((a,b) => {const x=measure(a), y=measure(b);return Number(y.accepted)-Number(x.accepted)||y.families-x.families||y.weight-x.weight||a.localeCompare(b);});
    const chosen = [], used = new Set();
    if (!dimension) for (const id of ranked) {
      const families = grouped.get(id).map(e=>e.dimension_slug);
      if (families.every(d=>used.has(d))) continue;
      chosen.push(id); families.forEach(d=>used.add(d)); if (chosen.length>=6) break;
    }
    chosen.push(...ranked.filter(id=>!chosen.includes(id)));
    const pages=Math.max(1,Math.ceil(chosen.length/8)), page=Math.max(1,Math.min(Number(params.get('page'))||1,pages));
    const result={seed,state:'ready',progress:{profiled:Object.keys(data.profiles).length,total:data.titles.length},total_neighbors:grouped.size,page,pages,pair:null,
      neighbors:chosen.slice((page-1)*8,page*8).map(id=>{const connections=grouped.get(id).map(e=>edgeDetails(data,e,feedback));return {title:title(data,id,library),connections,route:connections[0].dimension_name,shared_quality:connections[0].shared_quality};})};
    const compareId=params.get('compare');
    if (compareId) {
      if (compareId === seed.imdb_id) throw Error('Choose two different titles to compare');
      const other=title(data,compareId,library);if(!other)throw Error('Choose the comparison title from the catalog');
      result.pair=compare(data,seed,other,feedback,library);
    }
    return result;
  }
  function matchesFilters(title, params) {
    const type = params.get('type');
    if (type === 'movies' && title.title_type !== 'movie') return false;
    if (type === 'tv' && !['tvSeries', 'tvMiniSeries'].includes(title.title_type)) return false;
    for (const [key, field] of [['language', 'languages'], ['country', 'countries']]) {
      const selected = params.get(key), values = title[field] || [];
      if (selected === 'unknown' ? values.length > 0 : selected && !values.some(v => v.id === selected)) return false;
    }
    return true;
  }
  function filterOptions(data) {
    if (data.filterOptions) return data.filterOptions;
    const result = {};
    for (const field of ['languages', 'countries']) {
      const values = new Map();
      for (const title of data.titles) for (const value of title[field]?.length ? title[field] : [{id: 'unknown', name: 'Unknown'}]) {
        if (!values.has(value.id)) values.set(value.id, {...value, count: 0});
        values.get(value.id).count++;
      }
      result[field] = [...values.values()].sort((a,b) => a.id === 'unknown' ? 1 : b.id === 'unknown' ? -1 : a.name.localeCompare(b.name));
    }
    return data.filterOptions = result;
  }
  function catalog(data, params, library) {
    let rows=data.titles.map(t=>title(data,t.imdb_id,library));
    const search=(params.get('search')||'').trim().toLocaleLowerCase();
    if(search)rows=rows.filter(t=>t.title.toLocaleLowerCase().includes(search));
    const type=params.get('type');if(type==='movies')rows=rows.filter(t=>t.title_type==='movie');else if(type==='tv')rows=rows.filter(t=>t.title_type!=='movie');
    rows=rows.filter(t=>matchesFilters(t,params));
    const genre=params.get('genre');if(genre)rows=rows.filter(t=>t.genres.includes(genre));
    if(params.get('profiled')==='1')rows=rows.filter(t=>t.profile_status!=='awaiting_analysis');
    const filter=params.get('library');if(filter==='seen')rows=rows.filter(t=>t.seen);else if(filter==='unseen')rows=rows.filter(t=>!t.seen);else if(filter==='watchlist')rows=rows.filter(t=>t.watchlist);
    const sort=params.get('sort')||'votes';
    rows.sort((a,b)=>{let n=0;if(sort==='rating')n=b.rating-a.rating||b.num_votes-a.num_votes;else if(sort==='year')n=(b.start_year||0)-(a.start_year||0)||b.num_votes-a.num_votes;else if(sort==='oldest')n=(a.start_year||0)-(b.start_year||0)||b.num_votes-a.num_votes;else if(sort==='title')n=a.title.localeCompare(b.title,undefined,{sensitivity:'base'})||(a.start_year||0)-(b.start_year||0);else n=b.num_votes-a.num_votes;return n||a.imdb_id.localeCompare(b.imdb_id);});
    const pages=Math.max(1,Math.ceil(rows.length/20)),page=Math.max(1,Math.min(Number(params.get('page'))||1,pages));
    const counts=new Map();for(const t of data.titles)for(const g of t.genres)counts.set(g,(counts.get(g)||0)+1);
    return {titles:rows.slice((page-1)*20,page*20),total:rows.length,page,pages,page_size:20,genres:[...counts].sort(([a],[b])=>a.localeCompare(b)).map(([genre,count])=>({genre,count})),
      library:{seen:data.titles.filter(t=>library[t.imdb_id]?.seen).length,watchlist:data.titles.filter(t=>library[t.imdb_id]?.watchlist).length},filters:filterOptions(data)};
  }
  async function request(path,options={}) {
    if(!globalThis.MOVIE_LINKS_DATA_URL)return jsonResponse(await fetch(path,options));
    if(options.signal?.aborted)throw new DOMException('Request aborted','AbortError');
    const data=await dataset();if(options.signal?.aborted)throw new DOMException('Request aborted','AbortError');
    const url=new URL(path,location.origin),library=readStore(libraryKey),feedback=readStore(feedbackKey);
    const body=options.body?JSON.parse(options.body):{};
    switch(url.pathname){
      case '/api/graph-titles':return {titles:data.titles.map(({imdb_id,title,title_type,start_year})=>({imdb_id,title,title_type,start_year})),dimensions:data.dimensions,filters:filterOptions(data)};
      case '/api/graph':return graph(data,url.searchParams,library,feedback);
      case '/api/catalog':return catalog(data,url.searchParams,library);
      case '/api/title':return {title:title(data,url.searchParams.get('id'),library)};
      case '/api/profile':{
        const id=url.searchParams.get('id'),p=data.profiles[id];if(!p)return {profile:null};
        const dimensions=data.dimensions.map(d=>assessment(data,id,d));
        return {profile:{imdb_id:id,title:data.byId.get(id).title,status:p.status,summary:p.summary,dimensions,assessed_dimensions:dimensions.filter(d=>d.status!=='unknown').length}};
      }
      case '/api/library':{
        if(!data.byId.has(body.imdb_id))throw Error('Unknown title');
        const patch=Object.fromEntries(['seen','watchlist'].filter(k=>k in body).map(k=>[k,body[k]]));
        if(!Object.keys(patch).length||Object.values(patch).some(v=>typeof v!=='boolean'))throw Error('Expected a boolean seen or watchlist value');
        library[body.imdb_id]={...library[body.imdb_id],...patch};writeStore(libraryKey,library);return {title:title(data,body.imdb_id,library)};
      }
      case '/api/connection-feedback':{
        if(!['accepted','rejected','unreviewed'].includes(body.status))throw Error('Invalid feedback state');
        const edge=(data.adjacent.get(body.connection?.title_a)||[]).find(e=>e.id===body.connection_id&&identity(e)===identity(body.connection));
        if(!edge)throw Error('This connection changed. Reload before reviewing it.');
        feedback[identity(edge)]=body.status;writeStore(feedbackKey,feedback);return {connection_id:edge.id,status:body.status};
      }
      default:throw Error('Unknown Movie Links endpoint');
    }
  }
  globalThis.MovieLinksAPI={request};
})();
