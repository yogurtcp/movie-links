#!/usr/bin/env python3
"""Prepare disjoint, source-rich work packets for conversational analysis agents."""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'profile-input'
OUT.mkdir(parents=True, exist_ok=True)
db = sqlite3.connect(ROOT / 'data' / 'watch-map.sqlite3')
db.row_factory = sqlite3.Row
rows = db.execute('SELECT * FROM titles WHERE in_scope=1 ORDER BY num_votes DESC,imdb_id').fetchall()
taxonomy = json.loads((ROOT / 'analysis' / 'taxonomy.json').read_text())
manifest = {'dimensions': list(taxonomy), 'groups': {}}
for group in range(3):
    selected = rows[group::3]
    folder = OUT / f'group-{group+1}'
    folder.mkdir(exist_ok=True)
    for start in range(0,len(selected),25):
        titles = []
        for row in selected[start:start+25]:
            value = dict(row)
            value['genres'] = [r[0] for r in db.execute('SELECT genre FROM title_genres WHERE imdb_id=? ORDER BY genre',(row['imdb_id'],))]
            value['sources'] = [dict(r) for r in db.execute('SELECT provider,source_url,summary_text FROM source_documents WHERE imdb_id=? ORDER BY id',(row['imdb_id'],))]
            titles.append(value)
        (folder / f'batch-{start//25+1:02d}.json').write_text(json.dumps(titles,ensure_ascii=False,indent=2)+'\n')
    manifest['groups'][str(group+1)] = {'titles':len(selected),'batches':(len(selected)+24)//25,'imdb_ids':[r['imdb_id'] for r in selected]}
(OUT / 'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({g:{k:v for k,v in values.items() if k!='imdb_ids'} for g,values in manifest['groups'].items()},indent=2))
