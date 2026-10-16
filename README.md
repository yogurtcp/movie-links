# Movie Links

**[Open Movie Links](https://movie-links.yogurt-co.chatgpt.site)** · [Graph search](https://movie-links.yogurt-co.chatgpt.site/graph/) · [Catalog](https://movie-links.yogurt-co.chatgpt.site/explore/)

The hosted app is public and requires no sign-in. Seen titles, watchlist choices, and connection feedback are stored in your browser.

Movie Links helps explore IMDb-listed movies and TV series through qualities they share: character dynamics, story mechanics, emotional experience, humor, worldview, visual style, pacing, and more. Choose a familiar title, follow labeled links, and compare a pair directly.

## Current scope

The catalog was selected from official IMDb snapshots downloaded **15 October 2026**. It includes non-adult movies, TV series and miniseries with at least 50,000 votes and a rating at or above the median for their format.

| Format | At least 50K votes | Median IMDb rating | Selected |
| --- | ---: | ---: | ---: |
| Movies | 4,674 | 6.8 | 2,519 |
| TV series and miniseries | 721 | 8.1 | 376 |
| **Total** |  |  | **2,895** |

Episodes, shorts, TV movies and unrated titles are excluded. All years and genres are included. Ties at the median are included. The selection also includes documentaries, animation and some reality or talk formats.

The graph uses 26 descriptive families for its internal profiles. Its browsing and recommendation views expose 22 families; ending outcomes, character destinations, mystery reveals and tragic events are omitted to reduce spoilers. Plot descriptions and profile summaries stay collapsed until opened with a spoiler warning. Source passages are never shown inline. See [`docs/graph-method.md`](docs/graph-method.md) for the retrieval rules and limits.

The full first pass covers **2,895 titles**, with **104,002 candidate connections** across the 22 visible families. Profile positions are provisional model interpretations, not source-verified ratings. Unknown means this pass did not assign a position; it does not mean the title lacks the quality. Candidate links need individual review and do not predict whether you will enjoy a title. See [`docs/taxonomy-guide.md`](docs/taxonomy-guide.md) for distinctions between labels.

## Run the app

Requirements: Node.js 18+ for the local app, Python 3.10+ for catalog and graph scripts. The project uses standard library Python and Node modules only.

```bash
npm start
```

Open [http://localhost:4173](http://localhost:4173). If that port is already used by another local app, run `PORT=4174 npm start` and open [http://localhost:4174](http://localhost:4174). Use **Explore** to search the catalog, **Graph** to follow connections or compare two titles, and **Ratings** for IMDb score distributions. Your seen and watchlist choices are saved in the local SQLite database. The server listens on loopback only.

## Restore catalog and graph data

IMDb source files and the SQLite database are intentionally local. The selected title list is reproducible from the official IMDb datasets:

```bash
python3 analysis/imdb_distribution.py
python3 analysis/select_analysis_scope.py
python3 analysis/database.py init
python3 analysis/profiles.py init
python3 analysis/profile_snapshot.py import
python3 analysis/save_validated_example.py
python3 analysis/build_graph.py
```

The first command downloads about 237 MB compressed. The exported profile snapshot at `analysis/annotations/catalog-profiles.jsonl` contains semantic tags with the four spoiler-sensitive families omitted, plus profile summaries that may contain plot details. The app keeps those summaries collapsed with a warning. The snapshot has no IMDb ratings, source article text or personal library state. It can restore the provisional profile positions without rerunning the interpretation pass. The local database is created at `data/watch-map.sqlite3` and is ignored by Git.

To refresh aggregate reports after profile changes:

```bash
python3 analysis/semantic_report.py
```

The optional TVmaze source-coverage audit can be run with `python3 analysis/database.py audit-tv`; `--limit 10` limits a run and `--refresh` retries completed matches. Wikipedia title mapping and introduction collection are managed by `analysis/enrich_wikipedia.py` and are separate from the provisional graph pass.

## Project contents

- `public/` — local catalog, rating chart and interactive graph.
- `analysis/` — IMDb selection, SQLite schema, source collection, profile import/export and candidate graph builder.
- `analysis/taxonomy.json` — the reusable semantic vocabulary.
- `analysis/annotations/catalog-profiles.jsonl` — shareable spoiler-filtered profile snapshot.
- `docs/` — graph method, taxonomy notes and research plan.
- `output/` — aggregate coverage reports; no personal library data.

## Data and attribution

IMDb datasets are governed by [IMDb's non-commercial dataset terms](https://data.imdb.com/non-commercial-datasets/). TVmaze summaries are attributed to their original title pages and subject to [TVmaze API terms](https://www.tvmaze.com/api), including attribution and ShareAlike requirements. Wikipedia text is collected locally with source URL and revision metadata under [Wikipedia's licensing terms](https://en.wikipedia.org/wiki/Wikipedia:Copyrights). Third-party raw source dumps, ratings/votes, the SQLite database and personal seen/watchlist records are not included in this repository.

## Hosted build

Run `npm run build:hosted` after restoring or updating the local catalog and graph, followed by `npm run check:hosted`. It creates `dist/` with the complete catalog, spoiler-filtered profiles, and compact graph data. Personal library records and prior personal feedback are excluded. The hosted version runs in the browser and stores new library choices and connection feedback in browser storage. The local Node/Python server continues to use SQLite.

Sites hosting configuration is tracked in `.openai/hosting.json`. The generated `dist/` directory and its IMDb-derived catalog stay out of the public GitHub source tree.
