#!/usr/bin/env python3
"""Build the hosted browser app from the local catalog without personal records."""
import json
import shutil
import sqlite3
from pathlib import Path
from catalog_api import FIELDS, BASE, title_dict

ROOT = Path(__file__).resolve().parents[1]
HIDDEN = {'resolution', 'character_arc', 'mystery', 'tragedy'}


def build():
    db = sqlite3.connect(ROOT / 'data/watch-map.sqlite3')
    db.row_factory = sqlite3.Row
    taxonomy = json.loads((ROOT / 'analysis/taxonomy.json').read_text())
    dimensions = [dict(r) for r in db.execute('SELECT slug,name,description FROM dimensions ORDER BY name')
                  if r['slug'] not in HIDDEN]
    dim_index = {d['slug']: i for i, d in enumerate(dimensions)}
    titles = []
    for row in db.execute(f'SELECT {FIELDS} {BASE} WHERE t.in_scope=1 ORDER BY t.imdb_id'):
        value = title_dict(row)
        value.pop('seen', None)
        value.pop('watchlist', None)
        titles.append(value)
    indices = {t['imdb_id']: i for i, t in enumerate(titles)}
    snapshots = {r['imdb_id']: r for r in map(json.loads, (ROOT / 'analysis/annotations/catalog-profiles.jsonl').read_text().splitlines())}
    profiles = {}
    for row in db.execute('SELECT * FROM title_profiles'):
        identifier = row['imdb_id']
        if identifier not in indices:
            continue
        snap = snapshots[identifier]
        profiles[identifier] = {'status': row['status'], 'summary': row['profile_summary'],
                                'positions': {d['slug']: snap['positions'].get(d['slug']) for d in dimensions}, 'extras': {}}
    for row in db.execute('''SELECT a.*,tr.label FROM title_attributes a
            JOIN title_profiles p ON p.imdb_id=a.imdb_id AND p.current_run_id=a.analysis_run_id
            LEFT JOIN traits tr ON tr.id=a.trait_id'''):
        d = row['dimension_slug']
        if d in HIDDEN or row['imdb_id'] not in profiles:
            continue
        evidence = [dict(e) for e in db.execute('''SELECT DISTINCT d.source_url,d.provider FROM attribute_evidence e
                       JOIN source_documents d ON d.id=e.document_id WHERE e.attribute_id=?''', (row['id'],))]
        if evidence or row['label'] not in taxonomy[d]:
            profiles[row['imdb_id']]['extras'].setdefault(d, []).append({
                'trait': row['label'], 'description': row['description'], 'evidence': evidence,
                'evidence_type': row['evidence_type'], 'review_status': row['review_status']})
    edges = []
    manual = []
    for row in db.execute('''SELECT c.*,r.method,d.name dimension_name,m.ranking_weight
            FROM connections c JOIN analysis_runs r ON r.id=c.analysis_run_id
            JOIN dimensions d ON d.slug=c.dimension_slug
            LEFT JOIN graph_candidate_metadata m ON m.connection_id=c.id ORDER BY c.id'''):
        if row['dimension_slug'] in HIDDEN or row['title_a'] not in indices or row['title_b'] not in indices:
            continue
        if row['method'] == 'shared_semantic_trait_candidates_v1':
            # Personal feedback stays in its original database. Hosted feedback is browser-local.
            edges.append([row['id'], indices[row['title_a']], indices[row['title_b']],
                          dim_index[row['dimension_slug']], row['shared_quality'], round(row['ranking_weight'] or 0, 6)])
        elif row['method'] == 'user_validated_pair_example_v1':
            manual.append({k: row[k] for k in ('id','title_a','title_b','dimension_slug','dimension_name',
                                               'shared_quality','explanation','differences','review_status')})
    db.close()
    payload = {'version': 1, 'titles': titles, 'dimensions': dimensions, 'profiles': profiles,
               'edges': edges, 'manual': manual}
    dist = ROOT / 'dist'
    if dist.exists():
        shutil.rmtree(dist)
    shutil.copytree(ROOT / 'public', dist)
    (dist / 'data').mkdir()
    data_file = dist / 'data/catalog.json'
    data_file.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')))
    (dist / 'runtime-config.js').write_text('globalThis.MOVIE_LINKS_DATA_URL="/data/catalog.json";\n')
    # Directory entrypoints work on static hosts without an API server or SPA fallback.
    (dist / 'index.html').write_text((dist / 'graph.html').read_text())
    for route, source in [('graph', 'graph.html'), ('explore', 'browse.html')]:
        (dist / route).mkdir()
        shutil.copyfile(dist / source, dist / route / 'index.html')
    (dist / 'ratings').mkdir()
    shutil.copyfile(ROOT / 'output/imdb-ratings-browser.html', dist / 'ratings/index.html')
    print(json.dumps({'titles': len(titles), 'candidate_connections': len(edges), 'visible_families': len(dimensions),
                      'data_bytes': data_file.stat().st_size, 'personal_library_exported': False}))


if __name__ == '__main__':
    build()
