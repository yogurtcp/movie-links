#!/usr/bin/env python3
"""Persist the qualitative AoT/Death Note comparison the user endorsed.

Acceptance records the user's response to the comparison, not verified facts or
a general recommendation score. Re-running refreshes attached current attributes.
"""
import json
import sqlite3
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PAIR=sorted(('tt2560140','tt0877057'))
ROWS=[
 ('worldview','Moral conviction makes extreme choices feel justified',
  'Both invite you to follow people who see their own severe choices as justified, then question the human cost and the boundary between conviction and cruelty.',
  'Attack on Titan places these questions within collective survival, war and competing communities. Death Note concentrates them in a self-appointed judge and the investigators trying to stop him.',
  ['character','worldview','conflict','themes']),
 ('power','Information changes who holds power',
  'What a person knows can change the power they can wield and the choices available to them.',
  'Attack on Titan connects knowledge to a larger political order. Death Note centers it on a strategic contest between individuals.',
  ['power','story_engine']),
 ('viewer_contract','Suspense from anticipating the next strategic move',
  'Both reward tracking plans, incomplete information and countermoves rather than watching action alone.',
  'Death Note centers an intimate intellectual pursuit. Attack on Titan mixes strategic suspense with ensemble conflict, military danger and large-scale spectacle.',
  ['viewer_contract','pacing','story_engine'])]

def save():
    db=sqlite3.connect(ROOT/'data'/'watch-map.sqlite3',timeout=30)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    with db:
        old=db.execute("SELECT id FROM analysis_runs WHERE method='user_validated_pair_example_v1' ORDER BY id LIMIT 1").fetchone()
        run=old[0] if old else db.execute('''INSERT INTO analysis_runs(created_at,method,model,parameters_json) VALUES(?,?,?,?)''',
          (datetime.now(timezone.utc).isoformat(),'user_validated_pair_example_v1','conversation',json.dumps({'review_basis':'User endorsed qualitative comparison in conversation. Interpretive model knowledge; no passage-level verification claimed.'}))).lastrowid
        for dimension,quality,explanation,differences,families in ROWS:
            found=db.execute('''SELECT id FROM connections WHERE title_a=? AND title_b=? AND dimension_slug=? AND shared_quality=? AND analysis_run_id=?''',(*PAIR,dimension,quality,run)).fetchone()
            cid=found[0] if found else db.execute('''INSERT INTO connections(title_a,title_b,dimension_slug,shared_quality,explanation,differences,review_status,analysis_run_id) VALUES(?,?,?,?,?,?,'accepted',?)''',(*PAIR,dimension,quality,explanation,differences,run)).lastrowid
            db.execute('DELETE FROM connection_evidence WHERE connection_id=?',(cid,))
            for identifier in PAIR:
                marks=','.join('?' for _ in families)
                for attribute in db.execute('''SELECT a.id FROM title_attributes a JOIN title_profiles p
                    ON p.imdb_id=a.imdb_id AND p.current_run_id=a.analysis_run_id
                    WHERE a.imdb_id=? AND a.dimension_slug IN ('''+marks+')',(identifier,*families)).fetchall():
                    db.execute('INSERT OR IGNORE INTO connection_evidence VALUES(?,?)',(cid,attribute[0]))
    print(json.dumps({'user_validated_pair':PAIR,'connections':len(ROWS)}))
    db.close()

if __name__=='__main__':
    save()
