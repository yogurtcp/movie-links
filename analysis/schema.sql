PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS dataset_snapshots (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    selection_json TEXT NOT NULL,
    UNIQUE(name, selection_json)
);
CREATE TABLE IF NOT EXISTS titles (
    imdb_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    title_type TEXT NOT NULL CHECK(title_type IN ('movie','tvSeries','tvMiniSeries')),
    start_year INTEGER,
    rating_tenths INTEGER NOT NULL CHECK(rating_tenths BETWEEN 10 AND 100),
    num_votes INTEGER NOT NULL CHECK(num_votes >= 0),
    snapshot_id INTEGER NOT NULL REFERENCES dataset_snapshots(id),
    in_scope INTEGER NOT NULL DEFAULT 1 CHECK(in_scope IN (0,1))
);
CREATE INDEX IF NOT EXISTS titles_type_scope ON titles(title_type, in_scope);
CREATE TABLE IF NOT EXISTS title_genres (
    imdb_id TEXT NOT NULL REFERENCES titles(imdb_id),
    genre TEXT NOT NULL,
    PRIMARY KEY(imdb_id, genre)
);
CREATE TABLE IF NOT EXISTS external_ids (
    imdb_id TEXT NOT NULL REFERENCES titles(imdb_id),
    provider TEXT NOT NULL,
    external_id TEXT NOT NULL,
    PRIMARY KEY(imdb_id, provider),
    UNIQUE(provider, external_id)
);
CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY,
    imdb_id TEXT NOT NULL REFERENCES titles(imdb_id),
    provider TEXT NOT NULL,
    source_url TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    content_json TEXT NOT NULL,
    summary_text TEXT NOT NULL DEFAULT '',
    rights TEXT NOT NULL,
    UNIQUE(imdb_id, provider, content_sha256)
);
CREATE TABLE IF NOT EXISTS source_fetches (
    imdb_id TEXT NOT NULL REFERENCES titles(imdb_id),
    provider TEXT NOT NULL,
    requested_url TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('found','not_found','error')),
    http_status INTEGER,
    error TEXT,
    document_id INTEGER REFERENCES source_documents(id),
    attempts INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(imdb_id, provider)
);
CREATE TABLE IF NOT EXISTS dimensions (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS traits (
    id INTEGER PRIMARY KEY,
    dimension_slug TEXT NOT NULL REFERENCES dimensions(slug),
    label TEXT NOT NULL,
    definition TEXT NOT NULL,
    UNIQUE(dimension_slug, label)
);
CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    method TEXT NOT NULL,
    model TEXT,
    prompt_version TEXT,
    parameters_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS title_attributes (
    id INTEGER PRIMARY KEY,
    imdb_id TEXT NOT NULL REFERENCES titles(imdb_id),
    dimension_slug TEXT NOT NULL REFERENCES dimensions(slug),
    trait_id INTEGER REFERENCES traits(id),
    description TEXT NOT NULL,
    season_number INTEGER CHECK(season_number IS NULL OR season_number >= 0),
    evidence_type TEXT NOT NULL CHECK(evidence_type IN ('explicit','inferred')),
    review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK(review_status IN ('unreviewed','accepted','rejected')),
    analysis_run_id INTEGER NOT NULL REFERENCES analysis_runs(id)
);
CREATE TABLE IF NOT EXISTS attribute_evidence (
    attribute_id INTEGER NOT NULL REFERENCES title_attributes(id),
    document_id INTEGER NOT NULL REFERENCES source_documents(id),
    locator TEXT NOT NULL DEFAULT '',
    supporting_excerpt TEXT NOT NULL,
    PRIMARY KEY(attribute_id, document_id, locator)
);
CREATE TABLE IF NOT EXISTS connections (
    id INTEGER PRIMARY KEY,
    title_a TEXT NOT NULL REFERENCES titles(imdb_id),
    title_b TEXT NOT NULL REFERENCES titles(imdb_id),
    dimension_slug TEXT NOT NULL REFERENCES dimensions(slug),
    shared_quality TEXT NOT NULL,
    explanation TEXT NOT NULL,
    differences TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK(review_status IN ('unreviewed','accepted','rejected')),
    analysis_run_id INTEGER NOT NULL REFERENCES analysis_runs(id),
    CHECK(title_a < title_b),
    UNIQUE(title_a, title_b, dimension_slug, shared_quality, analysis_run_id)
);
CREATE TABLE IF NOT EXISTS connection_evidence (
    connection_id INTEGER NOT NULL REFERENCES connections(id),
    attribute_id INTEGER NOT NULL REFERENCES title_attributes(id),
    PRIMARY KEY(connection_id, attribute_id)
);
CREATE TABLE IF NOT EXISTS personal_library (
    imdb_id TEXT PRIMARY KEY REFERENCES titles(imdb_id),
    seen INTEGER NOT NULL DEFAULT 0 CHECK(seen IN (0,1)),
    watchlist INTEGER NOT NULL DEFAULT 0 CHECK(watchlist IN (0,1)),
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TRIGGER IF NOT EXISTS attribute_evidence_title_insert
BEFORE INSERT ON attribute_evidence
WHEN (SELECT imdb_id FROM title_attributes WHERE id=NEW.attribute_id)
     != (SELECT imdb_id FROM source_documents WHERE id=NEW.document_id)
BEGIN SELECT RAISE(ABORT, 'Attribute evidence must describe the same title'); END;
CREATE TRIGGER IF NOT EXISTS attribute_evidence_title_update
BEFORE UPDATE ON attribute_evidence
WHEN (SELECT imdb_id FROM title_attributes WHERE id=NEW.attribute_id)
     != (SELECT imdb_id FROM source_documents WHERE id=NEW.document_id)
BEGIN SELECT RAISE(ABORT, 'Attribute evidence must describe the same title'); END;
CREATE TRIGGER IF NOT EXISTS connection_evidence_title_insert
BEFORE INSERT ON connection_evidence
WHEN (SELECT imdb_id FROM title_attributes WHERE id=NEW.attribute_id)
     NOT IN (SELECT title_a FROM connections WHERE id=NEW.connection_id
             UNION ALL SELECT title_b FROM connections WHERE id=NEW.connection_id)
BEGIN SELECT RAISE(ABORT, 'Connection evidence must describe one of its titles'); END;
CREATE TRIGGER IF NOT EXISTS connection_evidence_title_update
BEFORE UPDATE ON connection_evidence
WHEN (SELECT imdb_id FROM title_attributes WHERE id=NEW.attribute_id)
     NOT IN (SELECT title_a FROM connections WHERE id=NEW.connection_id
             UNION ALL SELECT title_b FROM connections WHERE id=NEW.connection_id)
BEGIN SELECT RAISE(ABORT, 'Connection evidence must describe one of its titles'); END;
CREATE VIEW IF NOT EXISTS title_source_coverage AS
SELECT t.imdb_id, t.title, t.title_type, t.rating_tenths / 10.0 AS rating, t.num_votes,
       COALESCE(f.status, 'not_attempted') AS tvmaze_status,
       LENGTH(COALESCE(d.summary_text, '')) AS summary_characters
FROM titles t
LEFT JOIN source_fetches f ON f.imdb_id = t.imdb_id AND f.provider = 'tvmaze'
LEFT JOIN source_documents d ON d.id = f.document_id
WHERE t.in_scope = 1;
PRAGMA user_version = 1;
