/** Exercise the hosted transport using real exported data and browser-scoped storage. */
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {runInNewContext} from 'node:vm';
import {spawnSync} from 'node:child_process';

const payload=await readFile(new URL('../dist/data/catalog.json',import.meta.url),'utf8');
const source=await readFile(new URL('../public/app-api.js',import.meta.url),'utf8');
const data=JSON.parse(payload), storage=new Map();
const hidden=new Set(['resolution','character_arc','mystery','tragedy']);
function client() {
  const context={URL,DOMException,console,location:{origin:'https://movie-links.example'},MOVIE_LINKS_DATA_URL:'/data/catalog.json',
    localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},
    fetch:async()=>({ok:true,status:200,text:async()=>payload})};
  runInNewContext(source,context);
  return context.MovieLinksAPI.request;
}
function local(request) {
  const result=spawnSync('python3',['analysis/catalog_api.py'],{input:JSON.stringify(request),encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  return JSON.parse(result.stdout);
}
assert.equal(data.titles.length,2895);
assert.equal(Object.keys(data.profiles).length,2895);
assert.equal(data.edges.length,104002);
assert.equal(data.dimensions.length,22);
assert.ok(data.dimensions.every(d=>!hidden.has(d.slug)));
assert.ok(Object.values(data.profiles).every(p=>Object.keys(p.positions).every(d=>!hidden.has(d))&&Object.keys(p.extras).every(d=>!hidden.has(d))));
assert.ok(data.titles.every(t=>!('seen' in t)&&!('watchlist' in t)));
assert.ok(!payload.includes('"supporting_excerpt":'));
let api=client();
const search=await api('/api/catalog?search=Futurama');
assert.equal(search.total,1);assert.equal(search.titles[0].imdb_id,'tt0149460');
const sourceCatalog=local({action:'catalog',search:'Futurama'});
assert.equal(search.titles[0].rating,sourceCatalog.titles[0].rating);
for(const id of ['tt0149460','tt2560140','tt0877057']) {
  const actual=await api('/api/graph?seed='+id),expected=local({action:'graph',seed:id});
  assert.equal(actual.total_neighbors,expected.total_neighbors,`${id}: neighbor count`);
  assert.equal(actual.neighbors.map(n=>n.title.imdb_id).join(','),expected.neighbors.map(n=>n.title.imdb_id).join(','),`${id}: ranked neighbors`);
}
const pair=await api('/api/graph?seed=tt2560140&compare=tt0877057');
assert.equal(pair.pair.dimensions.length,22);
assert.equal(pair.pair.connections.filter(c=>c.review_status==='accepted').length,3);
assert.ok(pair.pair.connections.every(c=>!hidden.has(c.dimension_slug)));
const profile=await api('/api/profile?id=tt0149460');assert.equal(profile.profile.dimensions.length,22);
await api('/api/library',{body:JSON.stringify({imdb_id:'tt0149460',seen:true,watchlist:true})});
assert.equal((await api('/api/catalog?search=Futurama&library=unseen')).total,0);
assert.equal((await api('/api/catalog?library=watchlist')).total,1);
api=client();assert.equal((await api('/api/title?id=tt0149460')).title.seen,true,'library persists across page loads');
const graph=await api('/api/graph?seed=tt0149460'),edge=graph.neighbors[0].connections[0];
await api('/api/connection-feedback',{body:JSON.stringify({connection_id:edge.id,connection:edge,status:'rejected'})});
api=client();
const other=edge.title_a==='tt0149460'?edge.title_b:edge.title_a;
const reviewed=await api('/api/graph?seed=tt0149460&compare='+other);
assert.ok(!reviewed.pair.connections.some(c=>c.id===edge.id),'rejection persists');
assert.ok(!reviewed.pair.connections.some(c=>c.id===null&&c.dimension_slug===edge.dimension_slug),'rejected family is not reconstructed as an on-demand result');
storage.set('movie-links-library-v1','null');assert.equal((await api('/api/catalog?search=Futurama')).total,1);
console.log('Hosted checks passed: catalog, SQLite graph parity, spoiler exclusions, comparisons, library persistence, and feedback.');
