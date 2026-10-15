# How this graph is constructed

## Catalog and positions

The catalog contains the agreed IMDb selection: at least 50,000 votes, then at least the median rating within movies or TV. The snapshot and cutoffs are documented in the README.

Each exact work receives an assessment in 26 descriptive families. The four spoiler-sensitive families are retained only in the local analysis database; they are omitted from profiles and graph displays. The interface exposes the other 22 families. A family contains zero or more semantic positions; it is not a numeric axis. For example, a relationship family can include both divided loyalties and a sibling bond. `null` in the exported snapshot means unknown, not absent. Ending types, character destinations, mystery/revelation mechanisms, and tragic events are intentionally excluded from profiles, graph links, pair comparisons, and exported profile snapshots. Plot descriptions are collapsed behind a spoiler warning. Source passages are never shown inline; external source pages carry a warning before they open.

The bulk pass uses model interpretations from the provided exact-title descriptions and model knowledge. It does not independently research or verify each judgment. Unfamiliar works and unsupported technical aspects remain unknown. The local database can retain a small earlier pilot with passage-level citations; raw quoted passages are not part of the shareable profile snapshot. The interface distinguishes provisional positions, cited interpretations and user-reviewed connections.

`analysis/taxonomy.json` lists the reusable positions. Current profiles refer to a specific analysis run; older revisions remain in the local database. `analysis/annotations/catalog-profiles.jsonl` preserves original model summaries and positions for restoration without regenerating judgments. Raw third-party descriptions, IMDb rating/vote data, and personal library records are excluded from that snapshot.

## Candidate retrieval

1. Join titles that share an assigned position **within the same family**.
2. Skip resolution, character arc, mystery/revelation, and tragedy families to avoid spoilers about endings, character destinations, and story turns. Skip several generic positions such as linear structure, minimal humor, and continuing story; they remain visible in profiles but do not generate graph links by themselves.
3. Within each family, rank potential neighbors by the sum of `log(1 + N / frequency)` over shared positions. Uncommon positions weigh more heavily. Use the number of shared positions across families to break ties, then the IMDb identifier for reproducibility.
4. Retain three candidate neighbors per title per family. Merge reciprocal links. This produces an undirected graph with multiple labeled connections between the same pair.
5. The displayed neighborhood prefers user-accepted links, then pairs with more shared families and more retrieval weight. It tries to include several different families and shows up to eight neighbors.

These retrieval weights are internal ordering heuristics. They are not measured similarity, confidence, quality, or enjoyment scores. Model mistakes and broad labels can produce poor matches. A whole-catalog graph would be visually dense; the interface displays the neighborhood of one title at a time. Distance and node position have no analytical meaning.

## Pair search and review

A direct comparison also checks all shared positions in the current profiles, even when a pair was not retained among three neighbors. The comparison table shows the 22 exposed families, including differences and unknowns; the ending, arc, mystery/revelation, and tragedy families stay hidden. Automatically generated explanations describe overlapping labels; they are not individual critical essays about each pair.

The Attack on Titan / Death Note example has three separately written connections that the user endorsed: extreme choices justified by moral conviction, information changing power, and anticipation of strategic countermoves. This acceptance records the user's judgment that the comparison made sense. It does not verify every title attribute.

“Useful” and “Not useful” record local feedback on a particular connection. Rejected links are hidden from subsequent results. Rebuilding candidates preserves feedback for surviving pair/family/quality combinations. Graph changes can remove a candidate; acceptance does not freeze a candidate that no longer exists. The manually saved example survives candidate rebuilds.

## Limits of this pass

- A few shared labels cannot capture every important distinction or predict taste.
- Unknowns do not imply a title lacks the quality.
- Profiles describe the overall work; this pass does not provide complete season-by-season profiles.
- Series can change substantially over time. Documentary and reality formats also need different interpretation from fiction.
- Pair-specific source review, richer descriptions, vocabulary refinement and user feedback remain ways to improve the provisional graph. They are separate from completing the first catalog pass.
