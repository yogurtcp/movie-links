#!/usr/bin/env python3
"""Select titles with >=50,000 votes and >=their format group's median rating."""
import csv
import gzip
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
MINIMUM_VOTES = 50000
snapshot = json.loads((OUTPUT / "imdb-rating-distribution.json").read_text())
groups = {}
for group in ["movies", "tv"]:
    histogram = snapshot["histograms"][group][str(MINIMUM_VOTES)]
    median = statistics.median([i / 10 for i, count in enumerate(histogram) for _ in range(count)])
    groups[group] = {"eligible_before_rating_cutoff": sum(histogram), "median_rating": median,
                     "selected_count": 0}

target = OUTPUT / "analysis-titles-50k-median.csv"
type_counts = Counter()
with gzip.open(OUTPUT / "imdb-movies-and-tv.csv.gz", "rt", encoding="utf-8", newline="") as source, target.open("w", encoding="utf-8", newline="") as out:
    reader = csv.DictReader(source)
    writer = csv.DictWriter(out, fieldnames=reader.fieldnames)
    writer.writeheader()
    for row in reader:
        group = "movies" if row["title_type"] == "movie" else "tv"
        if int(row["votes"]) >= MINIMUM_VOTES and float(row["rating"]) >= groups[group]["median_rating"]:
            writer.writerow(row)
            groups[group]["selected_count"] += 1
            type_counts[row["title_type"]] += 1

manifest = {"source_snapshot": snapshot["sources"], "base_scope": snapshot["scope"],
            "minimum_votes_inclusive": MINIMUM_VOTES, "rating_comparison": ">=",
            "median_population": "Calculated separately for movies and TV series/miniseries, after applying the minimum vote threshold",
            "groups": groups, "selected_type_counts": dict(type_counts),
            "selected_total": sum(g["selected_count"] for g in groups.values()),
            "title_file": target.name}
(OUTPUT / "analysis-scope.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps(manifest, indent=2))
