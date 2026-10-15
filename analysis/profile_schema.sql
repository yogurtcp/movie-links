CREATE TABLE IF NOT EXISTS title_profiles (
    imdb_id TEXT PRIMARY KEY REFERENCES titles(imdb_id),
    current_run_id INTEGER REFERENCES analysis_runs(id),
    updated_at TEXT NOT NULL,
    profile_summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'awaiting_analysis'
        CHECK(status IN ('awaiting_analysis','provisional','source_assessed','reviewed'))
);
CREATE TABLE IF NOT EXISTS profile_dimensions (
    imdb_id TEXT NOT NULL REFERENCES title_profiles(imdb_id),
    dimension_slug TEXT NOT NULL REFERENCES dimensions(slug),
    status TEXT NOT NULL DEFAULT 'unknown'
        CHECK(status IN ('unknown','provisional','source_supported','not_applicable')),
    reason TEXT NOT NULL DEFAULT '',
    analysis_run_id INTEGER REFERENCES analysis_runs(id),
    PRIMARY KEY(imdb_id, dimension_slug)
);
CREATE INDEX IF NOT EXISTS profile_dimensions_status ON profile_dimensions(status, dimension_slug);
