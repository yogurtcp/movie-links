#!/usr/bin/env python3
"""Local SQLite catalog and resumable TVmaze source-coverage audit. Stdlib only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import sqlite3
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'watch-map.sqlite3'
OUTPUT = ROOT / 'output'
DIMENSIONS = {
    'relationships': ('Character relationships', 'Loyalties, power, intimacy, conflict and the evolution of relationships.'),
    'character': ('Character construction', 'Agency, flaws, motivations, competence, ensembles and character development.'),
    'story_engine': ('Story mechanics', 'What drives events: investigation, rivalry, survival, escalation and other mechanisms.'),
    'structure': ('Narrative structure', 'Chronology, viewpoint, episodic or serialized organization and narrative reliability.'),
    'pacing': ('Pacing and payoff', 'Rhythm, density, patience required and the way payoffs are developed.'),
    'emotion': ('Emotional experience', 'Emotional registers and the way the work invites or distances emotional investment.'),
    'themes': ('Themes and questions', 'Ideas the work examines, supported by specific narrative or critical evidence.'),
    'worldview': ('Worldview', 'Moral outlook, agency, optimism, fatalism and attitudes to institutions.'),
    'world': ('World and setting', 'Social environment, worldbuilding, realism, rules and historical or speculative setting.'),
    'stakes': ('Scale and stakes', 'Personal, relational, communal or larger consequences of the central conflicts.'),
    'humor': ('Humor mechanisms', 'How humor is constructed, its targets and its relationship to the surrounding tone.'),
    'tragedy': ('Suffering and tragedy', 'Sources and treatment of suffering, loss and tragic causality; potential spoilers.'),
    'dialogue': ('Dialogue and performance', 'Verbal rhythms, subtext, delivery and performance style.'),
    'visual_style': ('Visual storytelling', 'Composition, editing, camera, animation and the narrative use of images.'),
    'sound': ('Sound and music', 'The contribution of music, silence, sound design and sonic motifs.'),
    'atmosphere': ('Atmosphere', 'Qualities of the overall sensory and dramatic environment.'),
    'viewer_contract': ('Viewing experience', 'Ambiguity, attention, immersion, discomfort and the expectations placed on viewers.'),
    'emotional_progression': ('Emotional progression', 'How the emotional experience develops: accumulation, shifts, release and catharsis.'),
    'ensemble': ('Ensemble dynamics', 'How a group functions: factions, found family, coworkers and partnerships.'),
    'character_arc': ('Character development', 'The direction and mechanism of character change over the story.'),
    'power': ('Power dynamics', 'How power is held, exchanged, exerted and resisted between characters and institutions.'),
    'conflict': ('Sources of conflict', 'The personal, interpersonal, environmental or structural forces generating conflict.'),
    'mystery': ('Mystery and revelation', 'Hidden information, discoveries, reinterpretation and uncertainty about trust.'),
    'world_rules': ('World rules', 'Realism, speculative consistency, dream logic and unexplained phenomena.'),
    'resolution': ('Ambiguity and resolution', 'How fully narrative questions and moral issues are resolved.'),
    'combinations': ('Distinctive combinations', 'Specific combinations of qualities that create a distinctive experience.'),
}


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    return db


def initialize():
    manifest = json.loads((OUTPUT / 'analysis-scope.json').read_text())
    selection = json.dumps(manifest, sort_keys=True)
    with connect() as db:
        db.executescript((ROOT / 'analysis' / 'schema.sql').read_text())
        db.execute('INSERT OR IGNORE INTO dataset_snapshots(name,imported_at,selection_json) VALUES(?,?,?)', ('imdb-50k-group-median', now(), selection))
        snapshot_id = db.execute('SELECT id FROM dataset_snapshots WHERE name=? AND selection_json=?', ('imdb-50k-group-median', selection)).fetchone()[0]
        for slug, (name, description) in DIMENSIONS.items():
            db.execute('INSERT INTO dimensions(slug,name,description) VALUES(?,?,?) ON CONFLICT(slug) DO UPDATE SET name=excluded.name,description=excluded.description', (slug, name, description))
        db.execute('UPDATE titles SET in_scope=0')
        with (OUTPUT / manifest['title_file']).open(newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                year = int(row['start_year']) if row['start_year'] != '\\N' else None
                db.execute('''INSERT INTO titles(imdb_id,title,title_type,start_year,rating_tenths,num_votes,snapshot_id,in_scope)
                    VALUES(?,?,?,?,?,?,?,1) ON CONFLICT(imdb_id) DO UPDATE SET title=excluded.title,title_type=excluded.title_type,
                    start_year=excluded.start_year,rating_tenths=excluded.rating_tenths,num_votes=excluded.num_votes,snapshot_id=excluded.snapshot_id,in_scope=1''',
                    (row['imdb_id'], row['title'], row['title_type'], year, round(float(row['rating']) * 10), int(row['votes']), snapshot_id))
                db.execute('DELETE FROM title_genres WHERE imdb_id=?', (row['imdb_id'],))
                for genre in row['genres'].split(','):
                    if genre != '\\N':
                        db.execute('INSERT INTO title_genres(imdb_id,genre) VALUES(?,?)', (row['imdb_id'], genre))
        count = db.execute('SELECT COUNT(*) FROM titles WHERE in_scope=1').fetchone()[0]
        if count != manifest['selected_total']:
            raise ValueError(f'Expected {manifest["selected_total"]} titles; imported {count}')
    print(json.dumps({'database': str(DB), 'imported_titles': count, 'candidate_dimensions': len(DIMENSIONS)}, indent=2), flush=True)


def audit_tv(limit=None, refresh=False):
    with connect() as db:
        rows = db.execute('''SELECT t.imdb_id,t.title FROM titles t LEFT JOIN source_fetches f
            ON f.imdb_id=t.imdb_id AND f.provider='tvmaze' WHERE t.in_scope=1 AND t.title_type IN ('tvSeries','tvMiniSeries')
            AND (? OR f.status IS NULL OR f.status='error') ORDER BY t.num_votes DESC''', (int(refresh),)).fetchall()
    if limit is not None:
        rows = rows[:limit]
    results = Counter()
    last_request = 0.0
    for i, row in enumerate(rows, 1):
        requested_url = 'https://api.tvmaze.com/lookup/shows?imdb=' + row['imdb_id']
        status, http_status, error, document = 'error', None, None, None
        for attempt in range(3):
            delay = max(0, 0.75 - (time.monotonic() - last_request))
            if delay:
                time.sleep(delay)
            request = urllib.request.Request(requested_url, headers={'User-Agent': 'WatchMap-personal-source-audit/0.1', 'Accept': 'application/json'})
            last_request = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=25) as response:
                    document = json.load(response)
                    http_status = response.status
                # An exact external IMDb ID is required; fuzzy title matches are never substituted.
                if document.get('externals', {}).get('imdb') != row['imdb_id']:
                    raise ValueError('TVmaze external IMDb ID did not match the requested title')
                status, error = 'found', None
                break
            except urllib.error.HTTPError as exc:
                http_status = exc.code
                error = str(exc)
                if exc.code == 404:
                    status, error = 'not_found', None
                    break
                if exc.code not in (429, 500, 502, 503, 504):
                    break
                time.sleep(min(30, int(exc.headers.get('Retry-After', '5')) if exc.headers.get('Retry-After', '').isdigit() else 5 * (attempt + 1)))
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                error = str(exc)
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        fetched = now()
        with connect() as db:
            document_id = None
            if status == 'found':
                serialized = json.dumps(document, sort_keys=True, ensure_ascii=False)
                digest = hashlib.sha256(serialized.encode()).hexdigest()
                summary = html.unescape(re.sub('<[^>]*>', ' ', document.get('summary') or ''))
                summary = re.sub(r'\s+', ' ', summary).strip()
                source_url = document['url']
                db.execute('''INSERT OR IGNORE INTO source_documents(imdb_id,provider,source_url,fetched_at,content_sha256,content_json,summary_text,rights)
                    VALUES(?,'tvmaze',?,?,?,?,?,?)''', (row['imdb_id'], source_url, fetched, digest, serialized, summary, 'TVmaze API: CC BY-SA; attribution and ShareAlike apply. https://www.tvmaze.com/api#licensing'))
                document_id = db.execute("SELECT id FROM source_documents WHERE imdb_id=? AND provider='tvmaze' AND content_sha256=?", (row['imdb_id'], digest)).fetchone()[0]
                db.execute('''INSERT INTO external_ids(imdb_id,provider,external_id) VALUES(?,'tvmaze',?)
                    ON CONFLICT(imdb_id,provider) DO UPDATE SET external_id=excluded.external_id''', (row['imdb_id'], str(document['id'])))
            db.execute('''INSERT INTO source_fetches(imdb_id,provider,requested_url,fetched_at,status,http_status,error,document_id)
                VALUES(?,'tvmaze',?,?,?,?,?,?) ON CONFLICT(imdb_id,provider) DO UPDATE SET requested_url=excluded.requested_url,
                fetched_at=excluded.fetched_at,status=excluded.status,http_status=excluded.http_status,error=excluded.error,
                document_id=excluded.document_id,attempts=source_fetches.attempts+1''',
                (row['imdb_id'], requested_url, fetched, status, http_status, error, document_id))
        results[status] += 1
        if i % 25 == 0 or i == len(rows):
            print(json.dumps({'processed': i, 'scheduled': len(rows), 'this_run': dict(results)}), flush=True)
    report()


def report():
    with connect() as db:
        integrity = db.execute('PRAGMA quick_check').fetchone()[0]
        foreign_keys = [tuple(row) for row in db.execute('PRAGMA foreign_key_check')]
        if integrity != 'ok' or foreign_keys:
            raise ValueError(f'Database integrity issue: {integrity}, {foreign_keys}')
        type_counts = dict(db.execute('SELECT title_type,COUNT(*) FROM titles WHERE in_scope=1 GROUP BY title_type').fetchall())
        coverage = [dict(row) for row in db.execute('''SELECT CASE WHEN title_type='movie' THEN 'movies' ELSE 'tv' END AS title_group,
            tvmaze_status,COUNT(*) AS titles,SUM(CASE WHEN summary_characters>0 THEN 1 ELSE 0 END) AS with_summary
            FROM title_source_coverage GROUP BY title_group,tvmaze_status''')]
        summaries = [row[0] for row in db.execute("SELECT summary_characters FROM title_source_coverage WHERE tvmaze_status='found'")]
        attributes = db.execute('SELECT COUNT(*) FROM title_attributes').fetchone()[0]
        connections = db.execute('SELECT COUNT(*) FROM connections').fetchone()[0]
        dimensions = db.execute('SELECT COUNT(*) FROM dimensions').fetchone()[0]
        source_counts = dict(db.execute('SELECT provider,COUNT(*) FROM source_documents GROUP BY provider').fetchall())
        manifest = json.loads((OUTPUT / 'analysis-scope.json').read_text())
        summary = {'generated_at': now(), 'database': 'data/watch-map.sqlite3', 'selection': manifest['groups'],
                   'title_counts': type_counts, 'source_coverage': coverage,
                   'tvmaze_summary_lengths': {'found': len(summaries), 'empty': sum(n == 0 for n in summaries), 'under_300_characters': sum(0 < n < 300 for n in summaries), 'at_least_300_characters': sum(n >= 300 for n in summaries)},
                   'dimensions_available': dimensions, 'attributes_extracted': attributes,
                   'source_document_counts': source_counts,
                   'connections_analyzed': connections, 'integrity': integrity,
                   'notes': ['TVmaze lookup uses exact IMDb identifiers.', 'The per-title coverage view is specific to TVmaze. Other providers are counted separately.',
                             'A summary being present does not establish sufficient evidence for detailed attributes.',
                             'No attributes or connections have been inferred from IMDb genres or model memory.']}
        OUTPUT.mkdir(exist_ok=True)
        (OUTPUT / 'source-coverage.json').write_text(json.dumps(summary, indent=2) + '\n')
        with (OUTPUT / 'source-coverage.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            query = db.execute('SELECT * FROM title_source_coverage ORDER BY title_type,title')
            writer.writerow([column[0] for column in query.description])
            writer.writerows(query)
    print(json.dumps(summary, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init', 'audit-tv', 'report'])
    parser.add_argument('--limit', type=int)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    if args.command == 'init':
        initialize()
    elif args.command == 'audit-tv':
        audit_tv(args.limit, args.refresh)
    else:
        report()


if __name__ == '__main__':
    main()
