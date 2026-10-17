# Movie Links

**[Open Movie Links](https://movie-links.yogurt-co.chatgpt.site)** · [Graph search](https://movie-links.yogurt-co.chatgpt.site/graph/) · [Catalog](https://movie-links.yogurt-co.chatgpt.site/explore/) · [Best by genre](https://movie-links.yogurt-co.chatgpt.site/best/)

The hosted app is public and requires no sign-in. Seen titles, watchlist choices, and connection feedback are stored in your browser.

**[Yearly IMDb mean, median and 90th percentile](https://movie-links.yogurt-co.chatgpt.site/years/)** shows separate line graphs for movies and series/miniseries, without vote or rating cutoffs. The solid green line shows each year’s arithmetic mean; the dashed orange line shows its median (averaging the two middle ratings for even title counts). The blue dash-dot line shows the 90th percentile (nearest rank: sorted position ceil(0.9 × title count), with no interpolation). All three use equal weight per title and no smoothing. There are 345,326 movies and 139,880 series in the calculation; 67 rated titles lack a release year. PNG, PDF and CSV downloads of yearly means, medians, 90th percentiles and title counts are available. To regenerate: install `matplotlib`, then run `python3 analysis/year_score.py` before the hosted build.

Movie Links helps explore IMDb-listed movies and TV series through qualities they share: character dynamics, story mechanics, emotional experience, humor, worldview, visual style, pacing, and more. The home page starts with connections: choose a familiar title, read descriptions in the connected-title cards, and continue exploring from any card. Every title is labeled Movie, Series, or Miniseries. Descriptions remain closed behind a spoiler warning. A map and detailed pair comparison are available when wanted.

## Current scope

The catalog was selected from official IMDb snapshots downloaded **15 October 2026**. It includes non-adult movies, TV series and miniseries with at least 50,000 votes and a rating at or above the median for their format.

| Format | At least 50K votes | Median IMDb rating | Selected |
| --- | ---: | ---: | ---: |
| Movies | 4,674 | 6.8 | 2,519 |
| TV series and miniseries | 721 | 8.1 | 376 |
| **Total** |  |  | **2,895** |

Episodes, shorts, TV movies and unrated titles are excluded. All years and genres are included. Ties at the median are included. The selection also includes documentaries, animation and some reality or talk formats.

The optional **Best by genre** view ranks the full **5,395-title** population with at least 50,000 votes, before the graph’s median-rating cutoff. Choose movies or series/miniseries and a genre to see IMDb ratings, vote counts, and percentiles within that genre and format. Equal ratings share a rank and percentile; votes only order tied titles on screen. Multi-genre titles appear in each applicable genre. Titles outside the 2,895-title graph catalog are labeled as not mapped; all titles link to IMDb. Available descriptions stay behind a spoiler warning, and mapped titles link back to their connections.

The graph uses 26 descriptive families for its internal profiles. Its browsing and recommendation views expose 22 families; ending outcomes, character destinations, mystery reveals and tragic events are omitted to reduce spoilers. Plot descriptions and profile summaries stay collapsed until opened with a spoiler warning. Source passages are never shown inline. See [`docs/graph-method.md`](docs/graph-method.md) for the retrieval rules and limits.

The full first pass covers **2,895 titles**, with **104,002 candidate connections** across the 22 visible families. Profile positions are provisional model interpretations, not source-verified ratings. Unknown means this pass did not assign a position; it does not mean the title lacks the quality. Candidate links need individual review and do not predict whether you will enjoy a title. See [`docs/taxonomy-guide.md`](docs/taxonomy-guide.md) for distinctions between labels.

## Run the app

Requirements: Node.js 18+ for the local app, Python 3.10+ for catalog and graph scripts. The project uses standard library Python and Node modules only.

```bash
npm start
```

Open [http://localhost:4173](http://localhost:4173). If that port is already used by another local app, run `PORT=4174 npm start` and open [http://localhost:4174](http://localhost:4174). The home page opens the connection browser. Use **All titles** for the searchable catalog; the optional map and pair comparison are in the main discovery page. Ratings are linked from the explanation at the bottom. Your seen and watchlist choices are saved in the local SQLite database. The server listens on loopback only.

## Restore catalog and graph data

IMDb source files and the SQLite database are intentionally local. The selected title list is reproducible from the official IMDb datasets:

```bash
python3 analysis/imdb_distribution.py
python3 analysis/select_analysis_scope.py
python3 analysis/database.py init
python3 analysis/profiles.py init
python3 analysis/rating_context.py
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

## Rating percentiles

Each title shows its IMDb rating percentile within its format, plus a separate percentile within every IMDb genre in that format. The reference includes all non-adult eligible movies and series with at least 50,000 votes, **before** the median-rating selection: 4,674 movies and 721 series/miniseries in the 15 October 2026 snapshot. Thus the reference includes titles outside the 2,895-title recommendation catalog. Series and miniseries are pooled, as in the selection rule.

Ranks use `100 × (number rated lower + 0.5 × number tied) / group size`. Every title has equal weight. Genres overlap and are never averaged together. The app shows group sizes and marks genre groups with fewer than 30 titles. This is a relative rating position, not an adjusted IMDb score or an enjoyment probability.

`output/rating-reference.json` preserves the aggregate histograms and provenance; regenerate it with `python3 analysis/rating_context.py` after rebuilding the matching IMDb snapshot. Run `npm run check:ratings` for the tie-handling and comparison-membership checks, and `npm run check:hosted` for parity between local and hosted results.
