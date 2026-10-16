"""Genre leaderboards from the full 50K-vote reference population."""
import csv
import gzip
from pathlib import Path
from rating_context import context_for_title, load_reference

ROOT = Path(__file__).resolve().parents[1]


def build_rankings(db):
    reference = load_reference()
    mapped = {row[0] for row in db.execute('SELECT imdb_id FROM titles WHERE in_scope=1')}
    titles = []
    counts = {'movies': 0, 'tv': 0}
    with gzip.open(ROOT / 'output/imdb-movies-and-tv.csv.gz', 'rt', encoding='utf-8', newline='') as source:
        for row in csv.DictReader(source):
            if int(row['votes']) < reference['minimum_votes_inclusive']:
                continue
            if row['title_type'] not in ('movie', 'tvSeries', 'tvMiniSeries'):
                continue
            title = {'imdb_id': row['imdb_id'], 'title': row['title'], 'title_type': row['title_type'],
                     'start_year': int(row['start_year']) if row['start_year'].isdigit() else None,
                     'genres': sorted(set(row['genres'].split(',')) - {'', '\\N'}),
                     'rating': float(row['rating']), 'num_votes': int(row['votes']),
                     'in_catalog': row['imdb_id'] in mapped}
            title['rating_context'] = context_for_title(title, reference)
            counts[title['rating_context']['group']] += 1
            titles.append(title)
    for group, count in counts.items():
        if count != reference['groups'][group]['population']:
            raise ValueError('Leaderboard titles and rating reference have different populations: ' + group)
    return {'titles': titles, 'snapshot_date': reference['snapshot_date'],
            'minimum_votes': reference['minimum_votes_inclusive'], 'counts': counts,
            'genres': {group: list(values['genres']) for group, values in reference['groups'].items()}}
