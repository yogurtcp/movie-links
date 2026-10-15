# Analysis plan

## Aim

Start with a familiar movie or series, select which qualities to follow, and explore titles that share those qualities. Each connection should explain both its basis and significant differences between the experiences.

## Agreed catalog scope

The 15 October 2026 IMDb snapshot produces 2,519 movies rated at least 6.8 and 376 TV series/miniseries rated at least 8.1, all with at least 50,000 votes. The rating thresholds are the separate group medians after applying the vote filter. Counts are reproducible; the selected records remain local.

## Stage 1: source coverage

1. Preserve the selection manifest and original snapshot dates.
2. Match TVmaze records through exact external IMDb IDs. Record success, missing matches and request failures separately.
3. Measure summary availability and length; length is only a coverage indicator, not a quality score.
4. Identify reusable movie descriptions and critical discussion. IMDb's public bulk tables do not provide plot or review text. This provider remains unselected; movies should show `not_attempted`, not `not_found`, in the current TVmaze-only report.
5. Evaluate where episode/season summaries and critical discussion are needed. Introductory summaries are unlikely to support all style, relationship and emotional attributes.

## Stage 2: an evidence-backed pilot

Select 40–60 titles across formats, genres, periods and approaches, including comedy, drama, animation and speculative fiction. Agree the profile format by inspecting these examples.

Candidate dimensions are extensible and do not impose a fixed number of traits. Current schema seeds relationships, character construction, story mechanics, structure, pacing/payoff, emotion, themes, worldview, world/setting, stakes, humor, tragedy, dialogue/performance, visual storytelling, sound/music, atmosphere, and viewing experience.

Descriptions need supporting source passages and a distinction between explicit statements and interpretation. Unknowns remain unknown. Do not invent numeric intensity/confidence scores. Keep the extraction method, model and prompt version alongside each analysis. Model memory alone is not source evidence.

Review whether multiple sources independently support an interpretation. Record disagreements. Keep twist-revealing evidence separate from spoiler-safe browsing descriptions.

## Stage 3: evaluate connections

Compare title profiles separately within each dimension. Retrieve candidate pairs based on the qualities being followed, then inspect those pairs more closely. Store a precise shared quality, an explanation, important differences and references to evidence-backed attributes for both titles.

Evaluate whether a connection is specific, supported, useful for discovery and meaningfully different from simple genre matching. Inspect rejected and misleading matches as well as successful ones. Build user feedback around the usefulness of the connection, in addition to whether the user liked the title.

## Stage 4: scale

Estimate source acquisition and model effort from the pilot. Only then run extraction on the remainder, with resumable work and cached source snapshots. Preserve series-season scope and keep sparse descriptions visibly incomplete.

## Interface

The earlier curated 43-title design draft is separate from the database. It must not be presented as an evidence-backed result or silently used to populate analytical attributes. The catalog now shows the actual current profiles, their cited evidence and unknown dimensions. Initial coverage is 23 source-assessed shows and 105 assessed title/dimension positions; these interpretations are unreviewed. No recommendation edges have been analyzed yet. Remaining bulk semantic work needs a model execution method and review process; collecting source text does not by itself produce profiles.
