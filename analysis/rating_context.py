#!/usr/bin/env python3
"""IMDb rating midrank percentiles by format and format/genre, before selection."""
import csv
import gzip
import json
from collections import defaultdict
from functools import lru_cache
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'output/rating-reference.json'
MINIMUM_VOTES = 50000
FORMATS = {'movie': 'movies', 'tvSeries': 'tv', 'tvMiniSeries': 'tv'}


def make_reference(rows, snapshot_date, sources=None):
    """The input CSV has the same non-adult movie/series scope as the charts."""
    totals = {group: [0] * 101 for group in ('movies', 'tv')}
    genres = {group: defaultdict(lambda: [0] * 101) for group in totals}
    for row in rows:
        group = FORMATS.get(row['title_type'])
        if not group or int(row['votes']) < MINIMUM_VOTES:
            continue
        score = round(float(row['rating']) * 10)
        if not 10 <= score <= 100:
            continue
        totals[group][score] += 1
        for genre in set(row['genres'].split(',')) - {'', '\\N'}:
            genres[group][genre][score] += 1
    return {'version': 1, 'minimum_votes_inclusive': MINIMUM_VOTES,
            'snapshot_date': snapshot_date, 'sources': sources or [],
            'method': 'midrank', 'formula': '100 * (count_lower + 0.5 * count_equal) / population',
            'population': 'All eligible titles before the median-rating selection; each title has equal weight.',
            'series_definition': ['tvSeries', 'tvMiniSeries'],
            'groups': {group: {'population': sum(hist), 'histogram': hist,
                              'genres': {genre: {'population': sum(values), 'histogram': values}
                                         for genre, values in sorted(genres[group].items())}}
                       for group, hist in totals.items()}}


def midrank(histogram, rating_tenths):
    population = sum(histogram)
    if not population:
        return None
    lower = sum(histogram[:rating_tenths])
    equal = histogram[rating_tenths]
    return {'percentile': round(100 * (lower + 0.5 * equal) / population, 4),
            'population': population, 'lower_rated': lower, 'equal_rated': equal}


@lru_cache(maxsize=1)
def load_reference():
    if not REFERENCE.exists():
        return None
    return json.loads(REFERENCE.read_text())


def context_for_title(title, reference=None):
    reference = reference if reference is not None else load_reference()
    group = FORMATS.get(title.get('title_type'))
    votes = title.get('num_votes', title.get('votes', 0))
    if not reference or not group or int(votes) < reference['minimum_votes_inclusive']:
        return None
    score = title.get('rating_tenths')
    if score is None:
        score = round(float(title['rating']) * 10)
    bucket = reference['groups'][group]
    overall = midrank(bucket['histogram'], score)
    if overall is None:
        return None
    genres = title.get('genres', [])
    if isinstance(genres, str):
        genres = genres.split(',')
    genre_ranks = []
    for genre in sorted(set(genres)):
        if genre in bucket['genres']:
            rank = midrank(bucket['genres'][genre]['histogram'], score)
            if rank:
                genre_ranks.append({'genre': genre, **rank, 'small_group': rank['population'] < 30})
    return {'group': group, 'comparison_label': 'movies' if group == 'movies' else 'series and miniseries',
            'minimum_votes_inclusive': reference['minimum_votes_inclusive'],
            'snapshot_date': reference['snapshot_date'], 'method': reference['method'],
            'overall': overall, 'genres': genre_ranks}


def build():
    manifest = json.loads((ROOT / 'output/analysis-scope.json').read_text())
    snapshot_date = parsedate_to_datetime(manifest['source_snapshot'][0]['last_modified']).date().isoformat()
    with gzip.open(ROOT / 'output/imdb-movies-and-tv.csv.gz', 'rt', encoding='utf-8', newline='') as stream:
        reference = make_reference(csv.DictReader(stream), snapshot_date, manifest['source_snapshot'])
    # Use the snapshot's ISO date; never silently mix a refreshed CSV with old selection counts.
    reference['base_scope'] = manifest['base_scope']
    for group in ('movies', 'tv'):
        if reference['groups'][group]['population'] != manifest['groups'][group]['eligible_before_rating_cutoff']:
            raise ValueError('Rating-reference population differs from the selected catalog snapshot: ' + group)
    REFERENCE.write_text(json.dumps(reference, indent=2) + '\n')
    print(json.dumps({'snapshot_date': reference['snapshot_date'], 'populations':
                     {group: {'overall': values['population'], 'genres': len(values['genres'])}
                      for group, values in reference['groups'].items()}}))


if __name__ == '__main__':
    build()
