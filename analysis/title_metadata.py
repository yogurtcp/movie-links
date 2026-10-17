"""Shared local/hosted title metadata and result-filter semantics."""
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

FILE = Path(__file__).resolve().parent / 'annotations/title-origins.json'


@lru_cache(maxsize=1)
def load_metadata():
    return json.loads(FILE.read_text()) if FILE.exists() else {'titles': {}}


def for_title(identifier):
    data = load_metadata()
    row = data['titles'].get(identifier, {})
    return {'languages': row.get('languages', []), 'countries': row.get('countries', []),
            'metadata_source_url': row.get('source_url'), 'metadata_updated_at': data.get('updated_at')}


def matches(title, request):
    kind = request.get('type', 'all')
    if kind == 'movies' and title['title_type'] != 'movie':
        return False
    if kind == 'tv' and title['title_type'] not in ('tvSeries', 'tvMiniSeries'):
        return False
    metadata = for_title(title['imdb_id'])
    for key, field in [('language', 'languages'), ('country', 'countries')]:
        selected = request.get(key, '')
        values = metadata[field]
        if selected == 'unknown':
            if values:
                return False
        elif selected and not any(v['id'] == selected for v in values):
            return False
    return True


def eligible_ids(db, request):
    return [row['imdb_id'] for row in db.execute('SELECT imdb_id,title_type FROM titles WHERE in_scope=1') if matches(row, request)]


def filter_options(db):
    identifiers = [row[0] for row in db.execute('SELECT imdb_id FROM titles WHERE in_scope=1')]
    result = {}
    for field in ('languages', 'countries'):
        counts, labels = Counter(), {}
        for identifier in identifiers:
            values = for_title(identifier)[field]
            if not values:
                counts['unknown'] += 1
            for value in values:
                counts[value['id']] += 1
                labels[value['id']] = value['name']
        result[field] = sorted([{'id': key, 'name': labels[key], 'count': count}
                                for key, count in counts.items() if key != 'unknown'], key=lambda v: v['name'].casefold())
        if counts['unknown']:
            result[field].append({'id': 'unknown', 'name': 'Unknown', 'count': counts['unknown']})
    return result
