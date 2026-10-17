#!/usr/bin/env python3
"""Collect original-language and country-of-origin claims via exact Wikidata IDs."""
import argparse
import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data/origin-metadata-cache.json'
OUTPUT = ROOT / 'analysis/annotations/title-origins.json'
ENDPOINT = 'https://query.wikidata.org/sparql'
LAST_QUERY = time.monotonic()


def query_entities(identifiers):
    global LAST_QUERY
    values = ' '.join('wd:' + qid for qid in identifiers if re.fullmatch(r'Q[0-9]+', qid))
    query = '''SELECT DISTINCT ?item ?kind ?value ?valueLabel WHERE { VALUES ?item { ''' + values + ''' }
      { ?item wdt:P364 ?value . BIND("languages" AS ?kind) }
      UNION { ?item wdt:P495 ?value . BIND("countries" AS ?kind) }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }'''
    body = urllib.parse.urlencode({'query': query, 'format': 'json'}).encode()
    for attempt in range(4):
        time.sleep(max(0, 65 - (time.monotonic() - LAST_QUERY)))
        LAST_QUERY = time.monotonic()
        try:
            request = urllib.request.Request(ENDPOINT, data=body, headers={'User-Agent': 'MovieLinks/1.0 (personal noncommercial title metadata)',
                'Accept': 'application/sparql-results+json', 'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.load(response)
            if result.get('error'):
                raise ValueError(result['error']['info'])
            return result['results']['bindings']
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            if attempt == 3:
                raise
            retry_after = getattr(error, 'headers', {}).get('Retry-After', '')
            delay = max(65, int(retry_after) if retry_after.isdigit() else 0)
            print(json.dumps({'retry': attempt + 1, 'error': str(error)[:140], 'wait_seconds': delay}), flush=True)
            time.sleep(delay)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true', help='Refetch all mappings instead of resuming the local cache')
    args = parser.parse_args()
    db = sqlite3.connect(ROOT / 'data/watch-map.sqlite3')
    mapped = dict(db.execute("SELECT e.imdb_id,e.external_id FROM external_ids e JOIN titles t ON t.imdb_id=e.imdb_id WHERE e.provider='wikidata' AND t.in_scope=1"))
    identifiers = [r[0] for r in db.execute('SELECT imdb_id FROM titles WHERE in_scope=1 ORDER BY imdb_id')]
    db.close()
    cache = json.loads(CACHE.read_text()) if CACHE.exists() and not args.refresh else {}
    pending = [i for i in identifiers if i in mapped and i not in cache]
    for start in range(0, len(pending), 1000):
        batch = pending[start:start + 1000]
        rows = query_entities([mapped[i] for i in batch])
        by_item = {mapped[i]: {'languages': {}, 'countries': {}} for i in batch}
        for row in rows:
            qid = row['item']['value'].rsplit('/', 1)[-1]
            value = row['value']['value'].rsplit('/', 1)[-1]
            if qid in by_item and re.fullmatch(r'Q[0-9]+', value):
                by_item[qid][row['kind']['value']][value] = row['valueLabel']['value']
        for identifier in batch:
            cache[identifier] = {kind: sorted([{'id': qid, 'name': name} for qid, name in values.items()], key=lambda v: v['name'])
                                 for kind, values in by_item[mapped[identifier]].items()}
        CACHE.write_text(json.dumps(cache, ensure_ascii=False))
        print(json.dumps({'processed': min(start + len(batch), len(pending)), 'scheduled': len(pending)}), flush=True)
    payload = {'updated_at': datetime.now(timezone.utc).isoformat(), 'provider': 'Wikidata',
               'license': 'CC0', 'properties': {'languages': 'P364', 'countries': 'P495'},
               'definitions': {'languages': 'Original language of film or TV show; not dubbed audio availability',
                               'countries': 'Country of origin; not filming location or streaming availability'},
               'titles': {i: {**cache.get(i, {'languages': [], 'countries': []}),
                              'source_url': 'https://www.wikidata.org/wiki/' + mapped[i] if i in mapped else None}
                          for i in identifiers}}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'titles': len(identifiers), 'with_languages': sum(bool(t['languages']) for t in payload['titles'].values()),
                      'with_countries': sum(bool(t['countries']) for t in payload['titles'].values())}), flush=True)


if __name__ == '__main__':
    main()
