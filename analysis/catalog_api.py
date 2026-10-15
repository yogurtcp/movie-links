#!/usr/bin/env python3
"""SQLite operations for the local catalog HTTP server; JSON on stdin/stdout."""
import json
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'data' / 'watch-map.sqlite3'
SORTS = {
    'votes': 't.num_votes DESC, t.imdb_id',
    'rating': 't.rating_tenths DESC, t.num_votes DESC, t.imdb_id',
    'year': 't.start_year DESC, t.num_votes DESC, t.imdb_id',
    'oldest': 't.start_year ASC, t.num_votes DESC, t.imdb_id',
    'title': 't.title COLLATE NOCASE ASC, t.start_year, t.imdb_id',
}
BASE = '''FROM titles t
LEFT JOIN personal_library l ON l.imdb_id=t.imdb_id
LEFT JOIN source_fetches sf ON sf.imdb_id=t.imdb_id AND sf.provider='tvmaze'
LEFT JOIN source_documents sd ON sd.id=sf.document_id
LEFT JOIN source_fetches wf ON wf.imdb_id=t.imdb_id AND wf.provider='wikipedia_intro'
LEFT JOIN source_documents wd ON wd.id=wf.document_id'''
FIELDS = '''t.imdb_id,t.title,t.title_type,t.start_year,t.rating_tenths/10.0 AS rating,t.num_votes,
COALESCE(l.seen,0) AS seen,COALESCE(l.watchlist,0) AS watchlist,
(SELECT GROUP_CONCAT(genre,',') FROM title_genres WHERE imdb_id=t.imdb_id) AS genres,
COALESCE(NULLIF(sd.summary_text,''),wd.summary_text,'') AS summary,
CASE WHEN LENGTH(COALESCE(sd.summary_text,''))>0 THEN sd.source_url ELSE wd.source_url END AS source_url,
CASE WHEN LENGTH(COALESCE(sd.summary_text,''))>0 THEN 'tvmaze' ELSE 'wikipedia' END AS source_provider,
CASE WHEN LENGTH(COALESCE(sd.summary_text,''))>0 THEN sf.status ELSE COALESCE(wf.status,sf.status,'not_attempted') END AS source_status'''


def title_dict(row):
    result = dict(row)
    result['genres'] = result['genres'].split(',') if result['genres'] else []
    result['seen'] = bool(result['seen'])
    result['watchlist'] = bool(result['watchlist'])
    return result


def run(request):
    if not DB.exists():
        raise ValueError('Local catalog is not initialized. Run python3 analysis/database.py init.')
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        action = request.get('action', 'catalog')
        if action in ('graph','graph_titles','graph_feedback'):
            from graph_api import run_graph
            return run_graph(request,db)
        has_profiles = bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='title_profiles'").fetchone())
        if action == 'profile':
            identifier = request.get('imdb_id')
            title = db.execute('SELECT imdb_id,title FROM titles WHERE imdb_id=? AND in_scope=1', (identifier,)).fetchone()
            if not title:
                return {'profile': None}
            profile = db.execute('SELECT * FROM title_profiles WHERE imdb_id=?', (identifier,)).fetchone() if has_profiles else None
            result = {'imdb_id':identifier,'title':title['title'],'status':profile['status'] if profile else 'awaiting_analysis',
                      'summary':profile['profile_summary'] if profile else '', 'dimensions':[]}
            for dimension in db.execute('SELECT * FROM dimensions ORDER BY name'):
                # Do not expose ending outcomes in browsing profiles.
                if dimension['slug'] in ('resolution','character_arc','mystery','tragedy'):
                    continue
                assessment = db.execute('SELECT * FROM profile_dimensions WHERE imdb_id=? AND dimension_slug=?', (identifier,dimension['slug'])).fetchone() if has_profiles else None
                item = {'slug':dimension['slug'],'name':dimension['name'],'description':dimension['description'],
                        'status':assessment['status'] if assessment else 'unknown','reason':assessment['reason'] if assessment else '', 'claims':[]}
                if assessment and profile and profile['current_run_id']:
                    for claim in db.execute('''SELECT a.id,a.description,a.evidence_type,a.review_status,a.season_number,tr.label AS trait
                        FROM title_attributes a LEFT JOIN traits tr ON tr.id=a.trait_id
                        WHERE a.imdb_id=? AND a.dimension_slug=? AND a.analysis_run_id=? ORDER BY a.id''', (identifier,dimension['slug'],profile['current_run_id'])):
                        value=dict(claim)
                        value['evidence']=[dict(row) for row in db.execute('''SELECT d.source_url,d.provider,e.locator,e.supporting_excerpt
                            FROM attribute_evidence e JOIN source_documents d ON d.id=e.document_id WHERE e.attribute_id=?''', (claim['id'],))]
                        # The interface links to a source only after warning;
                        # never hand a plot passage to the browser client.
                        for evidence in value['evidence']:
                            evidence.pop('supporting_excerpt',None)
                        item['claims'].append(value)
                result['dimensions'].append(item)
            result['assessed_dimensions']=sum(item['status'] in ('source_supported','provisional') for item in result['dimensions'])
            return {'profile':result}
        if action == 'library':
            identifier = request.get('imdb_id')
            if not db.execute('SELECT 1 FROM titles WHERE imdb_id=? AND in_scope=1', (identifier,)).fetchone():
                raise ValueError('Unknown title')
            update = {key: request[key] for key in ['seen', 'watchlist'] if key in request}
            if not update or any(type(v) is not bool for v in update.values()):
                raise ValueError('Expected a boolean seen or watchlist value')
            with db:
                db.execute('INSERT OR IGNORE INTO personal_library(imdb_id) VALUES(?)', (identifier,))
                for key, value in update.items():
                    db.execute(f'UPDATE personal_library SET {key}=? WHERE imdb_id=?', (int(value), identifier))
            row = db.execute(f'SELECT {FIELDS} {BASE} WHERE t.imdb_id=?', (identifier,)).fetchone()
            return {'title': title_dict(row)}
        if action == 'title':
            row = db.execute(f'SELECT {FIELDS} {BASE} WHERE t.imdb_id=? AND t.in_scope=1', (request.get('imdb_id'),)).fetchone()
            return {'title': title_dict(row) if row else None}
        if action != 'catalog':
            raise ValueError('Unknown action')
        params = []
        conditions = ['t.in_scope=1']
        if request.get('profiled') == '1':
            conditions.append("EXISTS(SELECT 1 FROM title_profiles p WHERE p.imdb_id=t.imdb_id AND p.status!='awaiting_analysis')" if has_profiles else '0')
        search = str(request.get('search', '')).strip()[:200]
        if search:
            escaped = search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            conditions.append("t.title LIKE ? ESCAPE '\\'")
            params.append('%' + escaped + '%')
        title_type = request.get('type', 'all')
        if title_type == 'movies':
            conditions.append("t.title_type='movie'")
        elif title_type == 'tv':
            conditions.append("t.title_type IN ('tvSeries','tvMiniSeries')")
        genre = str(request.get('genre', ''))[:60]
        if genre:
            conditions.append('EXISTS(SELECT 1 FROM title_genres g WHERE g.imdb_id=t.imdb_id AND g.genre=?)')
            params.append(genre)
        library = request.get('library', 'all')
        if library == 'unseen':
            conditions.append('COALESCE(l.seen,0)=0')
        elif library == 'seen':
            conditions.append('l.seen=1')
        elif library == 'watchlist':
            conditions.append('l.watchlist=1')
        where = ' WHERE ' + ' AND '.join(conditions)
        count = db.execute(f'SELECT COUNT(*) {BASE} {where}', params).fetchone()[0]
        page_size = 20
        pages = max(1, (count + page_size - 1) // page_size)
        page = max(1, min(int(request.get('page', 1)), pages))
        order = SORTS.get(request.get('sort'), SORTS['votes'])
        rows = db.execute(f'SELECT {FIELDS} {BASE} {where} ORDER BY {order} LIMIT ? OFFSET ?', (*params, page_size, (page-1)*page_size)).fetchall()
        genres = [dict(row) for row in db.execute('''SELECT genre,COUNT(*) AS count FROM title_genres
            WHERE imdb_id IN (SELECT imdb_id FROM titles WHERE in_scope=1) GROUP BY genre ORDER BY genre''')]
        library_counts = dict(db.execute('''SELECT COALESCE(SUM(l.seen),0) AS seen,COALESCE(SUM(l.watchlist),0) AS watchlist
            FROM titles t LEFT JOIN personal_library l ON l.imdb_id=t.imdb_id WHERE t.in_scope=1''').fetchone())
        return {'titles': [title_dict(row) for row in rows], 'total': count, 'page': page, 'pages': pages,
                'page_size': page_size, 'genres': genres, 'library': library_counts}
    finally:
        db.close()


if __name__ == '__main__':
    try:
        request = json.load(sys.stdin)
        print(json.dumps(run(request), ensure_ascii=False))
    except (ValueError, sqlite3.Error) as error:
        print(json.dumps({'error': str(error)}))
        sys.exit(1)
