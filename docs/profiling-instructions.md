# Title profiling instructions, version 1

## Output

Produce a profile for the exact IMDb title and format supplied. Address all 26 connection families, with multiple descriptive claims where useful. Use natural-language positions and reusable, specific trait labels. Numerical scores are not required: many of these families describe several different mechanisms rather than a single intensity scale.

The JSON envelope has `basis` (`source_analysis` or `model_knowledge_provisional`), `model`, `prompt_version`, `notes`, and `profiles`. A profile has `imdb_id`, `title`, `summary`, and `dimensions`. Each dimension has `dimension`, `status`, `reason`, and `claims`. Claims have `trait`, `description`, `evidence_type`, optional `season_number`, and `evidence` entries with `source_url`, `excerpt`, and `locator`.

## Families

`emotion`, `atmosphere`, `emotional_progression`, `humor`, `tragedy`, `relationships`, `ensemble`, `character`, `character_arc`, `power`, `conflict`, `story_engine`, `structure`, `mystery`, `pacing`, `themes`, `worldview`, `world`, `world_rules`, `stakes`, `visual_style`, `dialogue`, `sound`, `viewer_contract`, `resolution`, `combinations`.

## Analysis requirements

- Match the exact work, year and format. A remake, adaptation, film and series with the same title are distinct.
- State specific mechanisms and relationships. Avoid vague filler such as "complex characters" or "interesting themes."
- Several positions can coexist within a family. A title can be gentle and melancholy, or have both comic and tragic mechanisms.
- Separate a character's outlook from the outlook of the work. An immoral protagonist alone does not establish a cynical worldview.
- A narrative event is insufficient to establish the tone of an entire work. A murder does not by itself establish sustained dread.
- A short plot summary often cannot establish pacing, performance, visual craft, sound, or resolution. Use appropriate richer material or return `unknown`.
- State season scope where a series changes, and acknowledge major changes rather than merging contradictory tendencies.
- Treat model-knowledge interpretations as `provisional`, with no fabricated sources or excerpts. Model familiarity is not source verification.
- In source analysis, distinguish explicit statements from interpretations. Every `source_supported` claim needs a passage from a collected source for the same title. The importer verifies the passage exists; entailment still needs review.
- Leave unassessed or inadequately supported families `unknown`. An unknown is not an absence or a low score. Use `not_applicable` only with a grounded reason.
- Keep spoiler-sensitive evidence in the evidence record; browsing descriptions should avoid revealing twists or endings.
- Do not invent measured confidence percentages. Review states distinguish preliminary assessments from accepted ones.

## Review and scale

First inspect a varied pilot. Review factual identity, evidence entailment, nuanced distinctions and potentially misleading matches. Compare profiles within individual families, then inspect candidate pairs and record both their shared qualities and important differences. No connection should be labeled as validated merely because two profiles share a trait string.
