#!/usr/bin/env python3
"""Validate and ingest completed semantic annotation batches, preserving citations."""
import argparse
import csv
import hashlib
import json
import sqlite3
import time
from pathlib import Path

from profiles import import_batch

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'watch-map.sqlite3'
TAXONOMY = json.loads((ROOT / 'analysis' / 'taxonomy.json').read_text())
DIMENSIONS = list(TAXONOMY)


def convert(filename):
    group = filename.parent.name
    source_file = ROOT / 'data' / 'profile-input' / group / (filename.stem + '.json')
    source = {row['imdb_id']: row for row in json.loads(source_file.read_text())}
    with filename.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE)
        if reader.fieldnames != ['imdb_id', 'title', 'summary'] + DIMENSIONS:
            raise ValueError(f'Unexpected TSV columns: {filename}')
        rows = list(reader)
    if len(rows) != len(source) or {row['imdb_id'] for row in rows} != set(source):
        raise ValueError(f'Batch IDs or row count mismatch: {filename}')
    if len({row['imdb_id'] for row in rows}) != len(rows):
        raise ValueError('Duplicate title IDs')
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    profiles = []
    for row in rows:
        identifier = row['imdb_id']
        if row['title'] != source[identifier]['title'] or None in row:
            raise ValueError(f'Title mismatch or extra TSV column: {identifier}')
        summary = row['summary'].strip()
        if len(summary.split()) < 7:
            raise ValueError('Missing title-specific summary: ' + identifier)
        current = db.execute('SELECT current_run_id FROM title_profiles WHERE imdb_id=?', (identifier,)).fetchone()
        assessment = []
        for dimension in DIMENSIONS:
            cell = row[dimension].strip()
            if not cell:
                raise ValueError(f'Empty cell: {identifier}/{dimension}; use ? for unknown')
            tags = [] if cell == '?' else cell.split('+')
            if len(tags) > 3 or len(tags) != len(set(tags)) or any(tag not in TAXONOMY[dimension] for tag in tags):
                raise ValueError(f'Invalid tags: {identifier}/{dimension}: {cell}')
            claims = []
            # Preserve only genuinely cited existing assertions, not older provisional labels.
            if current and current[0]:
                for old in db.execute('''SELECT a.*,tr.label FROM title_attributes a LEFT JOIN traits tr ON tr.id=a.trait_id
                    WHERE a.imdb_id=? AND a.dimension_slug=? AND a.analysis_run_id=?
                    AND EXISTS(SELECT 1 FROM attribute_evidence e WHERE e.attribute_id=a.id)''',
                    (identifier, dimension, current[0])):
                    evidence = [{'source_url': e['source_url'], 'excerpt': e['supporting_excerpt'], 'locator': e['locator']}
                                for e in db.execute('''SELECT d.source_url,e.supporting_excerpt,e.locator FROM attribute_evidence e
                                    JOIN source_documents d ON d.id=e.document_id WHERE e.attribute_id=?''', (old['id'],))]
                    claims.append({'trait':old['label'], 'description':old['description'], 'evidence_type':old['evidence_type'],
                                   'season_number':old['season_number'], 'evidence':evidence})
            for tag in tags:
                claims.append({'trait':tag, 'description':tag.replace('-', ' ').capitalize(),
                               'definition':tag.replace('-', ' '), 'evidence_type':'inferred', 'evidence':[]})
            status = 'provisional' if tags else 'source_supported' if claims else 'unknown'
            assessment.append({'dimension':dimension, 'status':status,
                               'reason':'Model assessment from supplied source context and knowledge; unverified.' if tags else
                                        'Preserved cited assessment.' if claims else 'Insufficient knowledge or material to assign a position in this pass.',
                               'claims':claims})
        profiles.append({'imdb_id':identifier, 'title':row['title'], 'summary':summary, 'dimensions':assessment})
    db.close()
    return {'basis':'source_analysis', 'model':'conversation-agent-batch', 'prompt_version':'catalog-provisional-v1',
            'notes':'Model-assigned provisional semantic positions, using the supplied source context and knowledge. Exact source citations from earlier manual work are preserved separately. No source verification is claimed for the generated labels.',
            'profiles':profiles}


def ingest():
    db = sqlite3.connect(DB)
    db.execute('''CREATE TABLE IF NOT EXISTS batch_imports(path TEXT PRIMARY KEY,content_sha256 TEXT NOT NULL,
        imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,profile_count INTEGER NOT NULL)''')
    db.commit()
    count = 0
    for ready in sorted((ROOT / 'data' / 'profile-batches').glob('group-*/batch-*.ready')):
        filename = ready.with_suffix('.tsv')
        digest = hashlib.sha256(filename.read_bytes()).hexdigest()
        key = str(filename.relative_to(ROOT))
        existing = db.execute('SELECT content_sha256 FROM batch_imports WHERE path=?', (key,)).fetchone()
        if existing and existing[0] == digest:
            continue
        batch = convert(filename)
        converted = filename.with_suffix('.profiles.json')
        converted.write_text(json.dumps(batch, ensure_ascii=False, separators=(',', ':'))+'\n')
        import_batch(converted)
        with db:
            db.execute('''INSERT INTO batch_imports(path,content_sha256,profile_count) VALUES(?,?,?)
                ON CONFLICT(path) DO UPDATE SET content_sha256=excluded.content_sha256,imported_at=CURRENT_TIMESTAMP,profile_count=excluded.profile_count''',
                (key,digest,len(batch['profiles'])))
        count += len(batch['profiles'])
        print(json.dumps({'ingested':key,'profiles':len(batch['profiles'])}),flush=True)
    db.close()
    return count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch',action='store_true')
    args=parser.parse_args()
    while True:
        ingest()
        if not args.watch:
            break
        time.sleep(15)
