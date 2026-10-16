#!/usr/bin/env python3
"""Plot every rated movie/series in the snapshot, without vote/rating cutoffs.

Requires matplotlib and numpy (only for regenerating these figures).
"""
import csv
import gzip
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.ticker import FuncFormatter, MultipleLocator
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'public/plots'
FORMATS = {'movie': 'movies', 'tvSeries': 'tv', 'tvMiniSeries': 'tv'}


def main():
    source = json.loads((ROOT / 'output/imdb-rating-distribution.json').read_text())
    groups = {group: {'rated': 0, 'missing_year': 0, 'cells': Counter()} for group in ('movies', 'tv')}
    with gzip.open(ROOT / 'output/imdb-movies-and-tv.csv.gz', 'rt', encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            group = groups[FORMATS[row['title_type']]]
            group['rated'] += 1
            if not row['start_year'].isdigit():
                group['missing_year'] += 1
                continue
            group['cells'][(int(row['start_year']), round(float(row['rating']) * 10))] += 1
    first_year = min(year for group in groups.values() for year, _ in group['cells'])
    last_year = max(year for group in groups.values() for year, _ in group['cells'])
    maximum = max(max(group['cells'].values()) for group in groups.values())
    year_edges = np.arange(first_year - .5, last_year + 1.5)
    score_edges = np.arange(9.5, 101.5) / 10
    TARGET.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'axes.titlesize': 21,
                         'axes.labelsize': 12, 'figure.facecolor': '#f7f6f1', 'axes.facecolor': '#fffefa',
                         'text.color': '#2d302b', 'axes.labelcolor': '#2d302b',
                         'xtick.color': '#555d51', 'ytick.color': '#555d51', 'axes.edgecolor': '#cbd2c3'})
    metadata = {'snapshot_date': '2026-10-15', 'scope': source['scope'],
                'cutoffs': 'No minimum vote count or rating cutoff; every rated title has equal weight.',
                'cell': 'One release year × 0.1 IMDb rating', 'color_scale': 'logarithmic',
                'source_urls': [s['url'] for s in source['sources']], 'groups': {}}
    for key, group in groups.items():
        plotted = sum(group['cells'].values())
        label = 'Movies' if key == 'movies' else 'TV series & miniseries'
        group_meta = {'rated_titles': group['rated'], 'plotted_titles': plotted,
                      'missing_release_year': group['missing_year'],
                      'first_year': min(y for y, _ in group['cells']),
                      'last_year': max(y for y, _ in group['cells'])}
        metadata['groups'][key] = group_meta
        values = np.zeros((91, last_year - first_year + 1), dtype=int)
        for (year, score), count in group['cells'].items():
            values[score - 10, year - first_year] = count
        fig, ax = plt.subplots(figsize=(13.5, 6.5))
        fig.subplots_adjust(left=.07, right=.88, bottom=.23, top=.81)
        mesh = ax.pcolormesh(year_edges, score_edges, np.ma.masked_equal(values, 0),
                             cmap='viridis', norm=LogNorm(vmin=1, vmax=maximum), rasterized=True)
        ax.set(xlim=(first_year - .5, last_year + .5), ylim=(.95, 10.05),
               xlabel='Release year' if key == 'movies' else 'Series premiere year', ylabel='IMDb score / 10')
        ax.xaxis.set_major_locator(MultipleLocator(10)); ax.yaxis.set_major_locator(MultipleLocator(1))
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='y', color='#70806a', alpha=.13, linewidth=.6)
        ax.set_axisbelow(True)
        color_ax = fig.add_axes([.90, .23, .016, .58])
        bar = fig.colorbar(mesh, cax=color_ax)
        bar.set_label('Titles per year / score cell (log scale)', labelpad=12, fontsize=10)
        bar.set_ticks([n for n in [1, 3, 10, 30, 100, 300, 1000, 3000] if n <= maximum])
        bar.ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:,.0f}'))
        bar.ax.tick_params(labelsize=9); bar.ax.minorticks_off()
        fig.text(.07, .925, f'{label}: IMDb score vs release year', fontsize=21, weight='medium')
        fig.text(.07, .865, f'{plotted:,} titles · All vote counts and ratings · IMDb snapshot: 15 October 2026', fontsize=11, color='#626b5b')
        fig.text(.07, .105, 'Each cell counts titles released in one year with the same score (0.1-point steps). Brighter = more titles.', fontsize=10, color='#626b5b')
        fig.text(.07, .067, f'No vote weighting. Blank = no titles. {group["missing_year"]:,} rated titles have no release year and cannot be plotted.', fontsize=10, color='#626b5b')
        fig.text(.07, .029, 'Non-adult movies / series / miniseries. Unrated titles, episodes, shorts and TV movies are outside this scope.', fontsize=9, color='#76796f')
        fig.savefig(TARGET / f'imdb-score-by-year-{key}.png', dpi=180)
        fig.savefig(TARGET / f'imdb-score-by-year-{key}.pdf')
        plt.close(fig)
        with (TARGET / f'imdb-score-by-year-{key}.csv').open('w', newline='') as stream:
            writer = csv.writer(stream); writer.writerow(['release_year', 'imdb_score', 'title_count'])
            for (year, score), count in sorted(group['cells'].items()):
                writer.writerow([year, f'{score / 10:.1f}', count])
    (TARGET / 'imdb-score-by-year.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata['groups']))


if __name__ == '__main__':
    main()
