#!/usr/bin/env python3
"""Download IMDb's public title/rating tables and count rating distributions.

Run from any directory with Python 3.10+: python3 analysis/imdb_distribution.py
Raw downloads are cached in data/raw; no third-party packages are required.
"""
from __future__ import annotations

import csv
import gzip
import json
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUTPUT = ROOT / "output"
BASE = "https://datasets.imdbws.com/"
MIN_VOTES = [0, 100, 500, 1000, 5000, 10000, 50000, 100000]
TYPES = {"movie": "movies", "tvSeries": "tv", "tvMiniSeries": "tv"}


def download(name: str) -> dict:
    target = RAW / name
    metadata_file = RAW / (name + ".metadata.json")
    if target.exists() and metadata_file.exists():
        info = json.loads(metadata_file.read_text())
        if target.stat().st_size == info["bytes"]:
            print(f"Using cached {name}", flush=True)
            return info
    req = urllib.request.Request(BASE + name, headers={"User-Agent": "WatchMap-personal-data-analysis/0.1"})
    temporary = target.with_suffix(target.suffix + ".partial")
    with urllib.request.urlopen(req, timeout=120) as response, temporary.open("wb") as out:
        info = {"url": BASE + name, "last_modified": response.headers.get("Last-Modified"),
                "downloaded_at": datetime.now(timezone.utc).isoformat(), "bytes": 0}
        last_report = 0
        while block := response.read(1024 * 1024):
            out.write(block)
            info["bytes"] += len(block)
            if info["bytes"] - last_report >= 32 * 1024 * 1024:
                print(f"{name}: {info['bytes'] / 1024 / 1024:.0f} MiB downloaded", flush=True)
                last_report = info["bytes"]
        if response.headers.get("Content-Length") and info["bytes"] != int(response.headers["Content-Length"]):
            raise ValueError(f"Incomplete download: {name}")
    temporary.replace(target)
    metadata_file.write_text(json.dumps(info, indent=2) + "\n")
    print(f"Finished {name}: {info['bytes']:,} bytes", flush=True)
    return info


def main() -> None:
    started = time.monotonic()
    RAW.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        sources = list(pool.map(download, ["title.ratings.tsv.gz", "title.basics.tsv.gz"]))

    ratings = {}
    with gzip.open(RAW / "title.ratings.tsv.gz", "rt", encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        assert next(reader) == ["tconst", "averageRating", "numVotes"]
        for identifier, rating, votes in reader:
            ratings[identifier] = (int(round(float(rating) * 10)), int(votes))
    print(f"Loaded ratings for {len(ratings):,} titles (all title types)", flush=True)

    histograms = {group: {str(v): [0] * 101 for v in MIN_VOTES} for group in ["movies", "tv"]}
    catalog_totals = Counter()
    rated_totals = Counter()
    adult_excluded = Counter()
    genre_counts = {group: Counter() for group in ["movies", "tv"]}
    raw_types = Counter()
    joined_path = OUTPUT / "imdb-movies-and-tv.csv.gz"
    with gzip.open(RAW / "title.basics.tsv.gz", "rt", encoding="utf-8", newline="") as f, gzip.open(joined_path, "wt", encoding="utf-8", newline="") as out:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        headers = next(reader)
        assert headers == ["tconst", "titleType", "primaryTitle", "originalTitle", "isAdult", "startYear", "endYear", "runtimeMinutes", "genres"]
        writer = csv.writer(out)
        writer.writerow(["imdb_id", "title_type", "title", "start_year", "genres", "rating", "votes"])
        for line_no, row in enumerate(reader, 1):
            identifier, title_type, title, original_title, adult, year, end_year, runtime, genres = row
            raw_types[title_type] += 1
            if title_type not in TYPES:
                continue
            group = TYPES[title_type]
            if adult != "0":
                adult_excluded[group] += 1
                continue
            catalog_totals[group] += 1
            if identifier not in ratings:
                continue
            rating, votes = ratings[identifier]
            assert 10 <= rating <= 100 and votes > 0
            rated_totals[group] += 1
            for minimum in MIN_VOTES:
                if votes >= minimum:
                    histograms[group][str(minimum)][rating] += 1
            genre_counts[group].update(genres.split(",") if genres != "\\N" else [])
            writer.writerow([identifier, title_type, title, year, genres, f"{rating / 10:.1f}", votes])
            if sum(rated_totals.values()) % 100000 == 0:
                print(f"Joined {sum(rated_totals.values()):,} rated movies/shows", flush=True)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "scope": {"movies": ["movie"], "tv": ["tvSeries", "tvMiniSeries"], "isAdult": "0", "years": "all", "genres": "all", "countries": "all", "unrated": "excluded from distributions"},
        "minimum_vote_options": MIN_VOTES,
        "catalog_totals_in_scope": dict(catalog_totals),
        "rated_totals": dict(rated_totals),
        "adult_or_unknown_flag_excluded": dict(adult_excluded),
        "all_title_type_counts": dict(raw_types),
        "genre_counts_rated": {k: dict(v) for k, v in genre_counts.items()},
        "histograms": histograms,
        "cutoff_counts": {},
    }
    for group in histograms:
        summary["cutoff_counts"][group] = {}
        for minimum in MIN_VOTES:
            counts = histograms[group][str(minimum)]
            assert sum(counts) <= rated_totals[group]
            summary["cutoff_counts"][group][str(minimum)] = {
                "rated_titles": sum(counts),
                **{f"rating_at_least_{cutoff / 10:.1f}": sum(counts[cutoff:]) for cutoff in [65, 70, 75, 80, 85, 90]},
            }
    for group in histograms:
        assert sum(histograms[group]["0"]) == rated_totals[group]
        for low, high in zip(MIN_VOTES, MIN_VOTES[1:]):
            assert all(a >= b for a, b in zip(histograms[group][str(low)], histograms[group][str(high)]))
    output = OUTPUT / "imdb-rating-distribution.json"
    output.write_text(json.dumps(summary, indent=2) + "\n")
    with (OUTPUT / "imdb-cutoff-counts.csv").open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["group", "minimum_votes", "rated_titles", "rating>=6.5", "rating>=7.0", "rating>=7.5", "rating>=8.0", "rating>=8.5", "rating>=9.0"])
        for group, thresholds in summary["cutoff_counts"].items():
            for minimum, counts in thresholds.items():
                writer.writerow([group, minimum, *counts.values()])
    print(json.dumps({"rated_totals": summary["rated_totals"], "at_1000_votes": {g: summary["cutoff_counts"][g]["1000"] for g in histograms}, "elapsed_seconds": round(time.monotonic() - started, 1), "output": str(output)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
