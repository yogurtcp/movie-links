import http from 'node:http';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), 'public');
const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.pdf': 'application/pdf', '.csv': 'text/csv; charset=utf-8', '.json': 'application/json; charset=utf-8' };
const port = Number(process.env.PORT || 4173);
function database(request) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.env.PYTHON || 'python3', [path.join(root, '..', 'analysis', 'catalog_api.py')], { stdio: ['pipe', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', chunk => { stdout += chunk; });
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.on('error', reject);
    child.on('close', code => {
      try {
        const value = JSON.parse(stdout);
        if (code || value.error) reject(new Error(value.error || 'Database request failed'));
        else resolve(value);
      } catch { reject(new Error(stderr ? 'Could not read the local catalog' : 'Invalid database response')); }
    });
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify(request));
  });
}
function json(res, status, value) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
  res.end(JSON.stringify(value));
}
const server = http.createServer(async (req, res) => {
  try {
    const hostname = new URL('http://' + req.headers.host).hostname;
    if (!['localhost', '127.0.0.1', '[::1]'].includes(hostname)) {
      res.writeHead(403).end('Use the local server address');
      return;
    }
    const url = new URL(req.url, 'http://localhost');
    const pathname = decodeURIComponent(url.pathname);
    if (pathname === '/api/rankings' && req.method === 'GET') {
      return json(res, 200, await database({ action: 'rankings' }));
    }
    if (pathname === '/api/catalog' && req.method === 'GET') {
      return json(res, 200, await database({ ...Object.fromEntries(url.searchParams), action: 'catalog' }));
    }
    if (pathname === '/api/title' && req.method === 'GET') {
      return json(res, 200, await database({ action: 'title', imdb_id: url.searchParams.get('id') }));
    }
    if (pathname === '/api/profile' && req.method === 'GET') {
      return json(res, 200, await database({ action: 'profile', imdb_id: url.searchParams.get('id') }));
    }
    if (pathname === '/api/graph' && req.method === 'GET') {
      return json(res, 200, await database({ ...Object.fromEntries(url.searchParams), action: 'graph' }));
    }
    if (pathname === '/api/graph-titles' && req.method === 'GET') {
      return json(res, 200, await database({ action: 'graph_titles' }));
    }
    if (pathname === '/api/connection-feedback' && req.method === 'POST') {
      const origin=req.headers.origin;
      if ((origin && new URL(origin).host!==req.headers.host) || !req.headers['content-type']?.startsWith('application/json')) return json(res,403,{error:'Use the local graph page.'});
      let body='';for await(const chunk of req){body+=chunk;if(body.length>2048)return json(res,413,{error:'Request too large'});}
      let value;try{value=JSON.parse(body);}catch{return json(res,400,{error:'Invalid JSON'});}
      return json(res,200,await database({...value,action:'graph_feedback'}));
    }
    if (pathname === '/api/library' && req.method === 'POST') {
      const origin = req.headers.origin;
      if ((origin && new URL(origin).host !== req.headers.host) || !req.headers['content-type']?.startsWith('application/json')) {
        return json(res, 403, { error: 'Use the local catalog page to update your library.' });
      }
      let body = '';
      for await (const chunk of req) {
        body += chunk;
        if (body.length > 2048) return json(res, 413, { error: 'Request too large' });
      }
      let value;
      try { value = JSON.parse(body); } catch { return json(res, 400, { error: 'Invalid JSON' }); }
      return json(res, 200, await database({ ...value, action: 'library' }));
    }
    if (pathname.startsWith('/api/')) return json(res, 404, { error: 'Unknown endpoint' });
    if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405).end('Method not allowed'); return; }
    const isChart = /^\/ratings\/?$/.test(pathname);
    const filename = isChart ? path.join(root, '..', 'output', 'imdb-ratings-browser.html')
      : path.resolve(root, '.' + (['/','/index.html','/graph','/graph/'].includes(pathname) ? '/graph.html' : ['/explore','/explore/'].includes(pathname) ? '/browse.html' : ['/best','/best/'].includes(pathname) ? '/best.html' : ['/years','/years/'].includes(pathname) ? '/years.html' : pathname));
    if (!isChart && !filename.startsWith(root + path.sep)) {
      res.writeHead(403).end('Forbidden');
      return;
    }
    const body = await readFile(filename);
    res.writeHead(200, { 'Content-Type': types[path.extname(filename)] || 'application/octet-stream', 'Cache-Control': 'no-cache', 'X-Content-Type-Options': 'nosniff' });
    res.end(req.method === 'HEAD' ? undefined : body);
  } catch (error) {
    if (req.url.startsWith('/api/')) return json(res, 400, { error: error.message });
    res.writeHead(error.code === 'ENOENT' || error.code === 'EISDIR' ? 404 : 400).end('Not found');
  }
});
server.on('error', error => { console.error(error.message); process.exitCode = 1; });
server.listen(port, '127.0.0.1', () => console.log(`Movie Links: http://localhost:${port}`));
