#!/usr/bin/env python3
"""Initialize coverage and import explicit title profiles with traceable provenance.

python3 analysis/profiles.py init
python3 analysis/profiles.py import path/to/batch.json
python3 analysis/profiles.py report
"""
import argparse
import csv
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'watch-map.sqlite3'


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def initialize():
    with connect() as db:
        db.executescript((ROOT / 'analysis' / 'profile_schema.sql').read_text())
        db.execute('''INSERT OR IGNORE INTO title_profiles(imdb_id,updated_at)
            SELECT imdb_id,? FROM titles WHERE in_scope=1''', (now(),))
        db.execute('''INSERT OR IGNORE INTO profile_dimensions(imdb_id,dimension_slug,reason)
            SELECT p.imdb_id,d.slug,'No assessment has been made for this dimension.'
            FROM title_profiles p CROSS JOIN dimensions d JOIN titles t ON t.imdb_id=p.imdb_id WHERE t.in_scope=1''')
    report()


def import_batch(filename):
    batch = json.loads(Path(filename).read_text())
    if batch.get('basis') not in ('source_analysis', 'model_knowledge_provisional'):
        raise ValueError('Batch basis must be source_analysis or model_knowledge_provisional')
    if not isinstance(batch.get('profiles'), list) or not batch['profiles']:
        raise ValueError('Expected a nonempty profiles list')
    with connect() as db:
        dimensions = {row[0] for row in db.execute('SELECT slug FROM dimensions')}
        cursor = db.execute('''INSERT INTO analysis_runs(created_at,method,model,prompt_version,parameters_json)
            VALUES(?,?,?,?,?)''', (now(), batch['basis'], batch.get('model'), batch.get('prompt_version'),
                                  json.dumps({'filename': Path(filename).name, 'notes': batch.get('notes', '')})))
        run_id = cursor.lastrowid
        seen = set()
        for profile in batch['profiles']:
            identifier = profile['imdb_id']
            if identifier in seen:
                raise ValueError('Duplicate profile in batch: ' + identifier)
            seen.add(identifier)
            title = db.execute('SELECT title FROM titles WHERE imdb_id=? AND in_scope=1', (identifier,)).fetchone()
            if not title:
                raise ValueError('Unknown or out-of-scope title: ' + identifier)
            if profile.get('title') and profile['title'].casefold() != title[0].casefold():
                raise ValueError('Title/ID mismatch: ' + identifier)
            if not db.execute('SELECT 1 FROM title_profiles WHERE imdb_id=?', (identifier,)).fetchone():
                raise ValueError('Run profiles.py init first')
            db.execute('''UPDATE profile_dimensions SET status='unknown',reason='Not assessed in the current profile revision.',analysis_run_id=?
                WHERE imdb_id=?''', (run_id, identifier))
            statuses = []
            assessed = set()
            for assessment in profile.get('dimensions', []):
                dimension = assessment['dimension']
                status = assessment['status']
                if dimension not in dimensions or dimension in assessed:
                    raise ValueError('Unknown or duplicate dimension: ' + dimension)
                assessed.add(dimension)
                if status not in ('unknown', 'provisional', 'source_supported', 'not_applicable'):
                    raise ValueError('Invalid dimension status: ' + status)
                if batch['basis'] == 'model_knowledge_provisional' and status in ('source_supported', 'not_applicable'):
                    raise ValueError('A knowledge-only batch cannot claim source support or established absence')
                claims = assessment.get('claims', [])
                if status in ('source_supported', 'provisional') and not claims:
                    raise ValueError('An assessed position needs at least one claim')
                if status in ('unknown', 'not_applicable') and claims:
                    raise ValueError('Unknown/not-applicable dimensions cannot contain claims')
                if status == 'not_applicable' and not assessment.get('reason', '').strip():
                    raise ValueError('Not-applicable requires a reason')
                db.execute('''UPDATE profile_dimensions SET status=?,reason=?,analysis_run_id=?
                    WHERE imdb_id=? AND dimension_slug=?''', (status, assessment.get('reason', ''), run_id, identifier, dimension))
                statuses.append(status)
                for claim in claims:
                    description = claim['description'].strip()
                    if not description:
                        raise ValueError('Empty claim')
                    label = claim.get('trait', '').strip()
                    trait_id = None
                    if label:
                        db.execute('INSERT OR IGNORE INTO traits(dimension_slug,label,definition) VALUES(?,?,?)',
                                   (dimension, label, claim.get('definition', label)))
                        trait_id = db.execute('SELECT id FROM traits WHERE dimension_slug=? AND label=?', (dimension, label)).fetchone()[0]
                    evidence = claim.get('evidence', [])
                    if status == 'source_supported' and not evidence:
                        raise ValueError('Source-supported claims require evidence')
                    evidence_type = claim.get('evidence_type', 'inferred')
                    if evidence_type not in ('explicit', 'inferred'):
                        raise ValueError('Invalid evidence_type')
                    if not evidence and evidence_type == 'explicit':
                        raise ValueError('Explicit claims require a source excerpt')
                    cursor = db.execute('''INSERT INTO title_attributes(imdb_id,dimension_slug,trait_id,description,season_number,evidence_type,analysis_run_id)
                        VALUES(?,?,?,?,?,?,?)''', (identifier, dimension, trait_id, description, claim.get('season_number'), evidence_type, run_id))
                    attribute_id = cursor.lastrowid
                    for item in evidence:
                        document = db.execute('SELECT id,summary_text FROM source_documents WHERE imdb_id=? AND source_url=? ORDER BY id DESC LIMIT 1',
                                              (identifier, item['source_url'])).fetchone()
                        if not document:
                            raise ValueError('Evidence source not collected for ' + identifier + ': ' + item['source_url'])
                        excerpt = item['excerpt'].strip()
                        normalize = lambda s: ' '.join(s.split()).casefold()
                        if not excerpt or normalize(excerpt) not in normalize(document['summary_text']):
                            raise ValueError('Evidence excerpt is absent from the stored document: ' + identifier)
                        db.execute('INSERT INTO attribute_evidence(attribute_id,document_id,locator,supporting_excerpt) VALUES(?,?,?,?)',
                                   (attribute_id, document['id'], item.get('locator', ''), excerpt))
            status = 'provisional' if batch['basis'] == 'model_knowledge_provisional' or 'provisional' in statuses else 'source_assessed'
            db.execute('UPDATE title_profiles SET current_run_id=?,updated_at=?,profile_summary=?,status=? WHERE imdb_id=?',
                       (run_id, now(), profile.get('summary', ''), status, identifier))
        print(json.dumps({'imported_profiles': len(seen), 'analysis_run_id': run_id, 'basis': batch['basis']}))
    report()


def report():
    with connect() as db:
        titles = {row[0]: row[1] for row in db.execute('SELECT status,COUNT(*) FROM title_profiles GROUP BY status')}
        coverage = {row[0]: row[1] for row in db.execute('SELECT status,COUNT(*) FROM profile_dimensions GROUP BY status')}
        summary = {'generated_at': now(), 'profile_status_counts': titles, 'dimension_status_counts': coverage,
                   'dimension_count': db.execute('SELECT COUNT(*) FROM dimensions').fetchone()[0],
                   'note': 'Initialized unknown positions are coverage records, not derived profiles. Source-supported descriptions still require interpretive review.'}
        (ROOT / 'output' / 'profile-coverage.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps(summary, indent=2))


def export_profiles():
    with connect() as db, (ROOT / 'output' / 'title-profiles.csv').open('w', newline='', encoding='utf-8') as out:
        dimensions = [row[0] for row in db.execute('SELECT slug FROM dimensions ORDER BY slug')]
        writer = csv.writer(out, lineterminator='\n')
        writer.writerow(['imdb_id', 'title', 'type', 'profile_status'] + [value for dimension in dimensions for value in [dimension, dimension + '_status']])
        for title in db.execute('''SELECT t.imdb_id,t.title,t.title_type,p.status,p.current_run_id
            FROM titles t JOIN title_profiles p ON p.imdb_id=t.imdb_id WHERE t.in_scope=1 ORDER BY t.title'''):
            row = [title['imdb_id'], title['title'], title['title_type'], title['status']]
            for dimension in dimensions:
                assessment = db.execute('SELECT status FROM profile_dimensions WHERE imdb_id=? AND dimension_slug=?', (title['imdb_id'], dimension)).fetchone()
                claims = [r[0] for r in db.execute('SELECT description FROM title_attributes WHERE imdb_id=? AND dimension_slug=? AND analysis_run_id=?', (title['imdb_id'], dimension, title['current_run_id']))]
                row.extend([' | '.join(claims) if claims else 'Unknown', assessment['status'] if assessment else 'unknown'])
            writer.writerow(row)
    print(ROOT / 'output' / 'title-profiles.csv')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'import', 'report', 'export'])
    parser.add_argument('filename', nargs='?')
    args = parser.parse_args()
    if args.command == 'init':
        initialize()
    elif args.command == 'import':
        if not args.filename:
            parser.error('import requires a batch JSON path')
        import_batch(args.filename)
    elif args.command == 'export':
        export_profiles()
    else:
        report()
