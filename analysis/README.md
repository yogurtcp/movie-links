# IMDb distribution census

This analysis is separate from the paused recommendation interface.

## Reproduce

```bash
cd /home/yevgeny/Documents/Codex/watch-map
python3 analysis/imdb_distribution.py
python3 analysis/render_distribution.py
```

Python 3.10+ is sufficient; there are no package dependencies. The first command downloads approximately 237 MB of compressed official IMDb data. Later runs reuse the local snapshot. To refresh, move or remove the two `.gz` downloads and their `.metadata.json` files from `data/raw/` before rerunning.

## Scope

- Movies: IMDb `titleType=movie`.
- TV shows: `tvSeries` and `tvMiniSeries`, counted once per series, not once per episode or season.
- Only `isAdult=0` records that join to the ratings file.
- All years, genres, countries, and languages; no scripted-only or English-only restriction.
- Shorts, TV movies, videos, episodes, unrated titles, and adult-flagged titles are excluded.
- One observation per title. The distribution is not weighted by vote count.
- IMDb rating is the published weighted average rating; the vote threshold controls which titles enter the distribution.
- Ratings are retained at their published precision (0.1). Aggregates cover several minimum vote thresholds.

## Files

- `data/raw/`: compressed source snapshots and download metadata, ignored by Git.
- `output/imdb-movies-and-tv.csv.gz`: joined rated titles, ignored by Git.
- `output/imdb-rating-distribution.json`: aggregate histograms, source metadata, and scope counts.
- `output/imdb-cutoff-counts.csv`: exact counts above rating cutoffs for each vote threshold.
- `output/imdb-rating-distribution.template.html`: editable chart fragment.
- `output/imdb-rating-distribution.html`: fragment with computed data embedded for the conversation.

Source schema: https://data.imdb.com/non-commercial-datasets/

IMDb makes these datasets available for personal, noncommercial use under its terms. Raw IMDb data is not redistributed by this project.
