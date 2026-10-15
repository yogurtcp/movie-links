#!/usr/bin/env python3
"""Resolve IMDb IDs through Wikidata and cache Wikipedia descriptions locally.

Usage: python3 analysis/enrich_wikipedia.py [--limit 100] [--full]
Default: batched article introductions. --full fetches full plain-text articles.
"""
import argparse
import hashlib
import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'watch-map.sqlite3'
AGENT = 'WatchMapResearch/0.1 (personal noncommercial film and television analysis)'
LAST_REQUEST = 0
LAST_SPARQL_REQUEST = 0


def now():
    return datetime.now(timezone.utc).isoformat()


def get_json(base, params):
    global LAST_REQUEST, LAST_SPARQL_REQUEST
    encoded = urllib.parse.urlencode(params)
    is_sparql = 'query.wikidata.org' in base
    use_post = is_sparql and len(encoded) > 6000
    url = base if use_post else base + '?' + encoded
    for attempt in range(4):
        time.sleep(max(0, 6 - (time.monotonic() - LAST_REQUEST)))
        if is_sparql:
            time.sleep(max(0, 65 - (time.monotonic() - LAST_SPARQL_REQUEST)))
            LAST_SPARQL_REQUEST = time.monotonic()
        LAST_REQUEST = time.monotonic()
        try:
            headers = {'User-Agent': AGENT, 'Accept': 'application/sparql-results+json' if is_sparql else 'application/json'}
            if use_post:
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
            request = urllib.request.Request(url, data=encoded.encode() if use_post else None, headers=headers)
            with urllib.request.urlopen(request, timeout=45) as response:
                result = json.load(response)
            if 'error' in result:
                raise ValueError(str(result['error']))
            return result
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            if attempt == 3:
                raise
            print(json.dumps({'request_retry': attempt + 1, 'error': str(error)[:160]}), flush=True)
            if isinstance(error, urllib.error.HTTPError) and error.code == 429:
                retry_after = error.headers.get('Retry-After', '')
                time.sleep(max(65, int(retry_after) if retry_after.isdigit() else 65))
            else:
                time.sleep(3 * (attempt + 1))


def fetch_state(db, identifier, provider, status, requested_url, document_id=None, error=None):
    db.execute('''INSERT INTO source_fetches(imdb_id,provider,requested_url,fetched_at,status,http_status,error,document_id)
        VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(imdb_id,provider) DO UPDATE SET requested_url=excluded.requested_url,
        fetched_at=excluded.fetched_at,status=excluded.status,http_status=excluded.http_status,error=excluded.error,
        document_id=excluded.document_id,attempts=source_fetches.attempts+1''',
        (identifier, provider, requested_url, now(), status, 200 if status in ('found', 'not_found') else None, error, document_id))


def resolve(db, identifiers):
    pending = [identifier for identifier in identifiers if not db.execute("SELECT 1 FROM source_fetches WHERE imdb_id=? AND provider='wikidata' AND status IN ('found','not_found')", (identifier,)).fetchone()]
    for start in range(0, len(pending), 1000):
        batch = pending[start:start + 1000]
        values = ' '.join(json.dumps(identifier) for identifier in batch)
        query = '''SELECT ?imdb ?item ?article WHERE { VALUES ?imdb { ''' + values + ''' }
            ?item wdt:P345 ?imdb . OPTIONAL { ?article schema:about ?item; schema:isPartOf <https://en.wikipedia.org/> . } }'''
        result = get_json('https://query.wikidata.org/sparql', {'query': query, 'format': 'json'})
        matches = defaultdict(list)
        for binding in result['results']['bindings']:
            matches[binding['imdb']['value']].append(binding)
        with db:
            for identifier in batch:
                found = matches.get(identifier, [])
                # Ambiguous mappings are not resolved by title similarity.
                article_matches = {(r['item']['value'].rsplit('/', 1)[-1], r['article']['value']) for r in found if 'article' in r}
                if len(article_matches) != 1:
                    fetch_state(db, identifier, 'wikidata', 'not_found' if not found else 'error', 'https://query.wikidata.org/sparql', error='No unique English Wikipedia article linked through the exact IMDb ID' if found else None)
                    continue
                qid, article = next(iter(article_matches))
                owner = db.execute("SELECT imdb_id FROM external_ids WHERE provider='wikipedia_en' AND external_id=?", (article,)).fetchone()
                if owner and owner[0] != identifier:
                    fetch_state(db, identifier, 'wikidata', 'error', 'https://query.wikidata.org/sparql', error='The linked article is already associated with another selected IMDb title; requires review')
                    continue
                db.execute('''INSERT INTO external_ids(imdb_id,provider,external_id) VALUES(?,'wikidata',?)
                    ON CONFLICT(imdb_id,provider) DO UPDATE SET external_id=excluded.external_id''', (identifier, qid))
                db.execute('''INSERT INTO external_ids(imdb_id,provider,external_id) VALUES(?,'wikipedia_en',?)
                    ON CONFLICT(imdb_id,provider) DO UPDATE SET external_id=excluded.external_id''', (identifier, article))
                fetch_state(db, identifier, 'wikidata', 'found', 'https://www.wikidata.org/wiki/' + qid)
        print(json.dumps({'mapping_processed': min(start + 1000, len(pending)), 'mapping_scheduled': len(pending)}), flush=True)


def collect(db, identifiers, full=False):
    provider = 'wikipedia_full' if full else 'wikipedia_intro'
    pending = []
    for identifier in identifiers:
        match = db.execute("SELECT external_id FROM external_ids WHERE imdb_id=? AND provider='wikipedia_en'", (identifier,)).fetchone()
        done = db.execute('SELECT 1 FROM source_fetches WHERE imdb_id=? AND provider=? AND status IN (\'found\',\'not_found\')', (identifier, provider)).fetchone()
        if match and not done:
            title = urllib.parse.unquote(urllib.parse.urlparse(match[0]).path.removeprefix('/wiki/')).replace('_', ' ')
            pending.append((identifier, title, match[0]))
    batch_size = 1 if full else 20
    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        params = {'action': 'query', 'prop': 'extracts|info|revisions', 'explaintext': 1, 'exlimit': batch_size,
                  'inprop': 'url', 'rvprop': 'ids|timestamp', 'redirects': 1,
                  'titles': '|'.join(item[1] for item in batch), 'format': 'json', 'formatversion': 2, 'maxlag': 5}
        if not full:
            params['exintro'] = 1
        result = get_json('https://en.wikipedia.org/w/api.php', params)
        query = result.get('query', {})
        pages = {page['title']: page for page in query.get('pages', [])}
        aliases = {item['from']: item['to'] for item in query.get('normalized', []) + query.get('redirects', [])}
        with db:
            for identifier, title, article in batch:
                seen = set()
                while title in aliases and title not in seen:
                    seen.add(title)
                    title = aliases[title]
                page = pages.get(title)
                if not page or page.get('missing') or not page.get('extract', '').strip():
                    fetch_state(db, identifier, provider, 'not_found', article)
                    continue
                text = page['extract'].strip()
                serialized = json.dumps(page, sort_keys=True, ensure_ascii=False)
                digest = hashlib.sha256(serialized.encode()).hexdigest()
                source_url = page.get('fullurl', article)
                rights = 'Wikipedia text: CC BY-SA, attribution and ShareAlike apply. Revision and original page URL retained. https://en.wikipedia.org/wiki/Wikipedia:Copyrights'
                db.execute('''INSERT OR IGNORE INTO source_documents(imdb_id,provider,source_url,fetched_at,content_sha256,content_json,summary_text,rights)
                    VALUES(?,?,?,?,?,?,?,?)''', (identifier, provider, source_url, now(), digest, serialized, text, rights))
                document_id = db.execute('SELECT id FROM source_documents WHERE imdb_id=? AND provider=? AND content_sha256=?', (identifier, provider, digest)).fetchone()[0]
                fetch_state(db, identifier, provider, 'found', article, document_id)
        print(json.dumps({'provider': provider, 'articles_processed': min(start + batch_size, len(pending)), 'articles_scheduled': len(pending)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--collect-only', action='store_true', help='Reuse existing IMDb-to-article mappings without querying Wikidata')
    args = parser.parse_args()
    db = sqlite3.connect(DB, timeout=30)
    db.execute('PRAGMA foreign_keys=ON')
    identifiers = [row[0] for row in db.execute('SELECT imdb_id FROM titles WHERE in_scope=1 ORDER BY num_votes DESC')]
    if args.limit:
        identifiers = identifiers[:args.limit]
    try:
        if not args.collect_only:
            resolve(db, identifiers)
        collect(db, identifiers, args.full)
        print(json.dumps({'source_counts': db.execute('SELECT provider,COUNT(*) FROM source_documents GROUP BY provider').fetchall()}), flush=True)
    finally:
        db.close()


if __name__ == '__main__':
    main()
