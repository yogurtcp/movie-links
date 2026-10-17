#!/usr/bin/env python3
"""Plot yearly statistics for all titles and for titles with 50K+ votes.

Requires matplotlib (only for regenerating these figures).
"""
import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'public/plots'
FORMATS = {'movie': 'movies', 'tvSeries': 'tv', 'tvMiniSeries': 'tv'}


def main():
    source = json.loads((ROOT / 'output/imdb-rating-distribution.json').read_text())
    groups = {group: {'rated': 0, 'missing_year': 0, 'cells': Counter()}
              for group in ('movies', 'tv', 'movies-50k', 'tv-50k')}
    with gzip.open(ROOT / 'output/imdb-movies-and-tv.csv.gz', 'rt', encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            key = FORMATS[row['title_type']]
            selected = [key] + ([key + '-50k'] if int(row['votes']) >= 50000 else [])
            for identifier in selected:
                group = groups[identifier]
                group['rated'] += 1
                if not row['start_year'].isdigit():
                    group['missing_year'] += 1
                    continue
                group['cells'][(int(row['start_year']), round(float(row['rating']) * 10))] += 1
    first_year = min(year for group in groups.values() for year, _ in group['cells'])
    last_year = max(year for group in groups.values() for year, _ in group['cells'])
    TARGET.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.titlesize': 21,
                         'axes.labelsize': 12, 'figure.facecolor': '#f7f6f1', 'axes.facecolor': '#fffefa',
                         'text.color': '#2d302b', 'axes.labelcolor': '#2d302b',
                         'xtick.color': '#555d51', 'ytick.color': '#555d51', 'axes.edgecolor': '#cbd2c3'})
    metadata = {'snapshot_date': '2026-10-15', 'scope': source['scope'],
                'cutoffs': 'Separate all-vote-count and >=50,000-vote populations. No rating cutoff in either; every title has equal weight.',
                'statistics': {'mean': 'sum(title IMDb ratings) / number of rated titles in that year',
                               'median': 'Middle title rating after sorting; mean of the two middle ratings for even title counts',
                               'p90': 'Nearest-rank 90th percentile: sorted rating at 1-based position ceil(0.9 * title count); no interpolation'},
                'weighting': 'Each title has equal weight; no vote weighting or smoothing.',
                'source_urls': [s['url'] for s in source['sources']], 'groups': {}}
    for key, group in groups.items():
        plotted = sum(group['cells'].values())
        is_movie = key.startswith('movies')
        minimum_votes = 50000 if key.endswith('-50k') else 0
        vote_label = '50,000+ votes' if minimum_votes else 'All vote counts'
        label = 'Movies' if is_movie else 'TV series & miniseries'
        group_meta = {'rated_titles': group['rated'], 'plotted_titles': plotted,
                      'minimum_votes': minimum_votes,
                      'missing_release_year': group['missing_year'],
                      'first_year': min(y for y, _ in group['cells']),
                      'last_year': max(y for y, _ in group['cells'])}
        metadata['groups'][key] = group_meta
        year_counts, year_score_totals = Counter(), Counter()
        year_ratings = defaultdict(list)
        for (year, score), count in group['cells'].items():
            year_counts[year] += count
            year_score_totals[year] += score * count
            year_ratings[year].extend([score] * count)
        year_medians = {year: median(scores) / 10 for year, scores in year_ratings.items()}
        group_meta['overall_median'] = median([score for scores in year_ratings.values() for score in scores]) / 10
        year_p90 = {year: sorted(scores)[(9 * len(scores) + 9) // 10 - 1] / 10
                    for year, scores in year_ratings.items()}
        years = list(range(first_year, last_year + 1))
        means = [year_score_totals[year] / (10 * year_counts[year]) if year_counts[year] else float('nan') for year in years]
        medians = [year_medians.get(year, float('nan')) for year in years]
        p90 = [year_p90.get(year, float('nan')) for year in years]
        fig, ax = plt.subplots(figsize=(13.5, 6.5))
        fig.subplots_adjust(left=.07, right=.96, bottom=.23, top=.81)
        ax.plot(years, means, color='#516d53', linewidth=2, marker='o', markersize=2.8, label='Average (mean)')
        ax.plot(years, medians, color='#ad593c', linewidth=1.8, linestyle='--', marker='D', markersize=2.5, label='Median')
        ax.plot(years, p90, color='#3c6f9e', linewidth=1.8, linestyle='-.', marker='^', markersize=2.8, label='90th percentile (P90)')
        ax.legend(loc='upper left', frameon=False, ncol=3, fontsize=11)
        ax.set(xlim=(first_year - .5, last_year + .5), ylim=(1, 10),
               xlabel='Release year' if is_movie else 'Series premiere year', ylabel='IMDb score / 10')
        ax.xaxis.set_major_locator(MultipleLocator(10)); ax.yaxis.set_major_locator(MultipleLocator(1))
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='y', color='#70806a', alpha=.13, linewidth=.6)
        ax.set_axisbelow(True)
        fig.text(.07, .925, f'{label}: IMDb scores by year', fontsize=20)
        fig.text(.07, .865, f'{plotted:,} titles · {vote_label} · No rating cutoff · IMDb snapshot: 15 October 2026', fontsize=11, color='#626b5b')
        fig.text(.07, .105, 'Every title counts equally. P90 = rating at or below which at least 90% of that year’s titles fall.', fontsize=10, color='#626b5b')
        fig.text(.07, .067, f'No vote weighting or smoothing. Gaps = no rated titles. {group["missing_year"]:,} titles lack a release year. Sparse years can fluctuate.', fontsize=10, color='#626b5b')
        fig.text(.07, .029, 'Non-adult movies / series / miniseries. Unrated titles, episodes, shorts and TV movies excluded. 2026 is incomplete.', fontsize=9, color='#76796f')
        fig.savefig(TARGET / f'imdb-score-by-year-{key}.png', dpi=180)
        fig.savefig(TARGET / f'imdb-score-by-year-{key}.pdf')
        plt.close(fig)
        with (TARGET / f'imdb-score-by-year-{key}.csv').open('w', newline='') as stream:
            writer = csv.writer(stream); writer.writerow(['release_year', 'average_imdb_score', 'median_imdb_score', 'p90_imdb_score', 'title_count'])
            for year in sorted(year_counts):
                writer.writerow([year, f'{year_score_totals[year] / (10 * year_counts[year]):.6f}', f'{year_medians[year]:.2f}', f'{year_p90[year]:.1f}', year_counts[year]])
    (TARGET / 'imdb-score-by-year.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata['groups']))


if __name__ == '__main__':
    main()
