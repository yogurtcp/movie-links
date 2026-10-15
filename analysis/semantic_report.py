#!/usr/bin/env python3
"""Report completed semantic assessments separately from support and review."""
import json
import sqlite3
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def report():
    db=sqlite3.connect(ROOT/'data'/'watch-map.sqlite3');db.row_factory=sqlite3.Row
    scope=db.execute('SELECT COUNT(*) FROM titles WHERE in_scope=1').fetchone()[0]
    statuses=dict(db.execute('''SELECT p.status,COUNT(*) FROM title_profiles p JOIN titles t ON t.imdb_id=p.imdb_id
        WHERE t.in_scope=1 GROUP BY p.status'''))
    families=[]
    for d in db.execute('SELECT slug,name FROM dimensions ORDER BY name').fetchall():
        counts=dict(db.execute('''SELECT p.status,COUNT(*) FROM profile_dimensions p JOIN titles t ON t.imdb_id=p.imdb_id
            WHERE t.in_scope=1 AND p.dimension_slug=? GROUP BY p.status''',(d['slug'],)))
        families.append({'dimension':d['slug'],'name':d['name'],'counts':counts})
    current_claims=db.execute('''SELECT COUNT(*) FROM title_attributes a JOIN title_profiles p
        ON p.imdb_id=a.imdb_id AND p.current_run_id=a.analysis_run_id''').fetchone()[0]
    cited_claims=db.execute('''SELECT COUNT(*) FROM title_attributes a JOIN title_profiles p
        ON p.imdb_id=a.imdb_id AND p.current_run_id=a.analysis_run_id
        WHERE EXISTS(SELECT 1 FROM attribute_evidence e WHERE e.attribute_id=a.id)''').fetchone()[0]
    all_unknown=db.execute('''SELECT COUNT(*) FROM title_profiles p JOIN titles t ON t.imdb_id=p.imdb_id
        WHERE t.in_scope=1 AND NOT EXISTS(SELECT 1 FROM profile_dimensions d WHERE d.imdb_id=p.imdb_id AND d.status!='unknown')''').fetchone()[0]
    total_positions=db.execute('''SELECT COUNT(*) FROM profile_dimensions p JOIN titles t ON t.imdb_id=p.imdb_id WHERE t.in_scope=1''').fetchone()[0]
    processed=db.execute('''SELECT COUNT(*) FROM profile_dimensions p JOIN titles t ON t.imdb_id=p.imdb_id
        WHERE t.in_scope=1 AND p.analysis_run_id IS NOT NULL''').fetchone()[0]
    value={'generated_at':datetime.now(timezone.utc).isoformat(),'scope_titles':scope,'profile_status_counts':statuses,
           'dimension_records':total_positions,'processed_title_dimension_records':processed,'expected_title_dimension_records':scope*len(families),
           'titles_with_all_dimensions_unknown':all_unknown,'current_claims':current_claims,'claims_with_cited_passages':cited_claims,
           'families':families,'review_note':'A completed pass includes unknown assessments. Generated positions are provisional model interpretations, not source-verified ratings. Connections require separate review.'}
    (ROOT/'output'/'semantic-coverage.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps(value,indent=2));db.close()

if __name__=='__main__':report()
