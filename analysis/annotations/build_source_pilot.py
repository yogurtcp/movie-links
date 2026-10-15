#!/usr/bin/env python3
"""Package manually interpreted, source-grounded pilot claims for strict import."""
import csv
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
db = sqlite3.connect(ROOT / 'data' / 'watch-map.sqlite3')
db.row_factory = sqlite3.Row
profiles = {}
with (HERE / 'source-pilot.tsv').open(encoding='utf-8', newline='') as f:
    reader = csv.reader((line for line in f if not line.startswith('#')), delimiter='\t', quoting=csv.QUOTE_NONE)
    for title, dimension, trait, description, excerpt in reader:
        rows = db.execute('''SELECT t.imdb_id,sd.source_url FROM titles t JOIN source_fetches f ON f.imdb_id=t.imdb_id
            AND f.provider='tvmaze' JOIN source_documents sd ON sd.id=f.document_id
            WHERE t.title=? AND t.in_scope=1''', (title,)).fetchall()
        if len(rows) != 1:
            raise ValueError('Expected one exact collected TV title: ' + title)
        row = rows[0]
        profile = profiles.setdefault(row['imdb_id'], {'imdb_id': row['imdb_id'], 'title': title, 'summary': 'Initial source-grounded assessment from the collected TVmaze description. Unassessed dimensions remain unknown.', 'dimensions': {}})
        assessment = profile['dimensions'].setdefault(dimension, {'dimension': dimension, 'status': 'source_supported', 'claims': []})
        assessment['claims'].append({'trait': trait, 'description': description, 'evidence_type': 'inferred',
                                     'evidence': [{'source_url': row['source_url'], 'excerpt': excerpt, 'locator': 'TVmaze show description'}]})
batch = {'basis': 'source_analysis', 'model': 'conversation-agent', 'prompt_version': 'source-pilot-v1',
         'notes': 'Manually interpreted after reading cached source descriptions; no model API or pattern-based bulk classifier used. Claims require review of entailment, not only quote matching.',
         'profiles': [{**profile, 'dimensions': list(profile['dimensions'].values())} for profile in profiles.values()]}
target = ROOT / 'data' / 'source-pilot-batch.json'
target.write_text(json.dumps(batch, indent=2, ensure_ascii=False) + '\n')
print(target)
db.close()
