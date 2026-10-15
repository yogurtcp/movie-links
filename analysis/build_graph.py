#!/usr/bin/env python3
"""Build provisional graph candidates from explicitly shared semantic positions.

Edges are candidates based on shared model-assigned traits, not independently
validated recommendations. Their evidence comes from the current title profiles.
"""
import argparse
import json
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'data' / 'watch-map.sqlite3'
SKIP = {'minimal','linear','grounded-realism','emotional-investment','clear-answers','completed-arcs','continuing-story'}
# Endings, character destinations, turning-point revelations, and specific
# tragic events can reveal what a viewer is meant to discover. Keep these local
# for analysis, but never expose them in profiles or recommendation links.
SPOILER_FAMILIES = {'resolution','character_arc','mystery','tragedy'}


def build():
    db=sqlite3.connect(DB,timeout=30)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''CREATE TABLE IF NOT EXISTS graph_candidate_metadata(
        connection_id INTEGER PRIMARY KEY REFERENCES connections(id) ON DELETE CASCADE,
        ranking_weight REAL NOT NULL,shared_traits_json TEXT NOT NULL,origin TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS connections_a_dim ON connections(title_a,dimension_slug);
        CREATE INDEX IF NOT EXISTS connections_b_dim ON connections(title_b,dimension_slug);
        CREATE INDEX IF NOT EXISTS attributes_profile ON title_attributes(imdb_id,analysis_run_id,dimension_slug);''')
    titles={r['imdb_id']:dict(r) for r in db.execute('''SELECT t.imdb_id,t.title,p.profile_summary FROM titles t
        JOIN title_profiles p ON p.imdb_id=t.imdb_id WHERE t.in_scope=1 AND p.current_run_id IS NOT NULL''')}
    dimensions={r['slug']:r['name'] for r in db.execute('SELECT * FROM dimensions')}
    by_trait=defaultdict(dict)
    positions=defaultdict(lambda:defaultdict(list))
    evidence_ids=defaultdict(list)
    for r in db.execute('''SELECT a.id,a.imdb_id,a.dimension_slug,tr.label FROM title_attributes a
        JOIN title_profiles p ON p.imdb_id=a.imdb_id AND p.current_run_id=a.analysis_run_id
        JOIN titles t ON t.imdb_id=a.imdb_id AND t.in_scope=1 JOIN traits tr ON tr.id=a.trait_id'''):
        if r['dimension_slug'] in SPOILER_FAMILIES or r['label'] in SKIP:
            continue
        key=(r['dimension_slug'],r['label'])
        by_trait[key][r['imdb_id']]=r['id']
        positions[r['imdb_id']][r['dimension_slug']].append(r['label'])
        evidence_ids[(r['imdb_id'],r['dimension_slug'])].append(r['id'])
    n=max(1,len(titles))
    keep=set()
    all_tags={identifier:{(d,tag) for d,tags in dims.items() for tag in tags} for identifier,dims in positions.items()}
    for identifier,dims in positions.items():
        overlap_cache={}
        for dimension,tags in dims.items():
            neighbors=defaultdict(float)
            for tag in tags:
                members=by_trait[(dimension,tag)]
                if len(members)<2:
                    continue
                weight=math.log1p(n/len(members))
                for other in members:
                    if other!=identifier:
                        neighbors[other]+=weight
            for other in neighbors:
                if other not in overlap_cache:
                    overlap_cache[other]=len(all_tags[identifier]&all_tags[other])
            ranked=sorted(neighbors,key=lambda other:(-neighbors[other],-overlap_cache[other],other))
            for other in ranked[:3]:
                left,right=sorted((identifier,other))
                keep.add((left,right,dimension))
    with db:
        feedback={(r['title_a'],r['title_b'],r['dimension_slug'],r['shared_quality']):r['review_status'] for r in db.execute('''
            SELECT c.* FROM connections c JOIN analysis_runs r ON r.id=c.analysis_run_id
            WHERE r.method='shared_semantic_trait_candidates_v1' AND c.review_status!='unreviewed' ''')}
        previous=[r[0] for r in db.execute("SELECT id FROM analysis_runs WHERE method='shared_semantic_trait_candidates_v1'")]
        for run in previous:
            db.execute('DELETE FROM graph_candidate_metadata WHERE connection_id IN (SELECT id FROM connections WHERE analysis_run_id=?)',(run,))
            db.execute('DELETE FROM connection_evidence WHERE connection_id IN (SELECT id FROM connections WHERE analysis_run_id=?)',(run,))
            db.execute('DELETE FROM connections WHERE analysis_run_id=?',(run,))
        run=db.execute('''INSERT INTO analysis_runs(created_at,method,model,prompt_version,parameters_json) VALUES(?,?,?,?,?)''',
            (datetime.now(timezone.utc).isoformat(),'shared_semantic_trait_candidates_v1',None,None,
             json.dumps({'neighbors_per_dimension':3,'skip_traits':sorted(SKIP),'note':'Candidate edges; no probability or independently verified similarity is implied.'}))).lastrowid
        for left,right,dimension in sorted(keep):
            tags=sorted(set(positions[left][dimension])&set(positions[right][dimension]))
            readable=', '.join(tag.replace('-',' ') for tag in tags)
            left_positions=positions[left][dimension]
            right_positions=positions[right][dimension]
            left_extra=[v.replace('-',' ') for v in left_positions if v not in tags]
            right_extra=[v.replace('-',' ') for v in right_positions if v not in tags]
            differences=(f"{titles[left]['title']}: {titles[left]['profile_summary']}\n"
                         f"{titles[right]['title']}: {titles[right]['profile_summary']}")
            if left_extra or right_extra:
                differences+='\nOther positions in this family: '+titles[left]['title']+' — '+(', '.join(left_extra) or 'none assigned')+'; '+titles[right]['title']+' — '+(', '.join(right_extra) or 'none assigned')+'.'
            explanation=f"Both current profiles include {readable} under {dimensions[dimension].lower()}. This is a provisional candidate connection; its usefulness still needs review."
            connection_id=db.execute('''INSERT INTO connections(title_a,title_b,dimension_slug,shared_quality,explanation,differences,analysis_run_id,review_status)
                VALUES(?,?,?,?,?,?,?,?)''',(left,right,dimension,readable,explanation,differences,run,feedback.get((left,right,dimension,readable),'unreviewed'))).lastrowid
            weight=sum(math.log1p(n/len(by_trait[(dimension,tag)])) for tag in tags)
            db.execute('INSERT INTO graph_candidate_metadata(connection_id,ranking_weight,shared_traits_json,origin) VALUES(?,?,?,?)',
                       (connection_id,weight,json.dumps(tags),'shared_profile_traits'))
            for identifier in (left,right):
                for attribute_id in evidence_ids[(identifier,dimension)]:
                    db.execute('INSERT OR IGNORE INTO connection_evidence(connection_id,attribute_id) VALUES(?,?)',(connection_id,attribute_id))
    stats={'generated_at':datetime.now(timezone.utc).isoformat(),'profiled_titles':len(titles),'candidate_connections':len(keep),
           'dimensions':len(dimensions)-len(SPOILER_FAMILIES),'hidden_spoiler_families':sorted(SPOILER_FAMILIES),
           'method':'Shared provisional semantic positions; up to three ranked neighbors per title per family. Ending outcomes are excluded.',
           'note':'Rankings are not probabilities. Unreviewed candidates are not validated recommendations.'}
    (ROOT/'output'/'graph-coverage.json').write_text(json.dumps(stats,indent=2)+'\n')
    print(json.dumps(stats,indent=2),flush=True)
    db.close()


if __name__=='__main__':
    build()
