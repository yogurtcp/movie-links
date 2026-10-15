#!/usr/bin/env python3
"""Export/import authored semantic positions without raw IMDb/source/personal data."""
import argparse
import json
import sqlite3
import tempfile
from datetime import datetime,timezone
from pathlib import Path
from profiles import import_batch

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'analysis'/'annotations'/'catalog-profiles.jsonl'
TAXONOMY=json.loads((ROOT/'analysis'/'taxonomy.json').read_text())
VISIBLE_TAXONOMY={d:tags for d,tags in TAXONOMY.items() if d not in ('resolution','character_arc','mystery','tragedy')}

def export():
    db=sqlite3.connect(ROOT/'data'/'watch-map.sqlite3')
    db.row_factory=sqlite3.Row
    lines=[]
    for p in db.execute('''SELECT p.* FROM title_profiles p JOIN titles t ON t.imdb_id=p.imdb_id
        WHERE t.in_scope=1 AND p.status!='awaiting_analysis' ORDER BY p.imdb_id'''):
        positions={d:None for d in VISIBLE_TAXONOMY}
        for a in db.execute('''SELECT a.dimension_slug,tr.label FROM title_attributes a JOIN traits tr ON tr.id=a.trait_id
            WHERE a.imdb_id=? AND a.analysis_run_id=?''',(p['imdb_id'],p['current_run_id'])):
            d,tag=a['dimension_slug'],a['label']
            if d in VISIBLE_TAXONOMY and tag in VISIBLE_TAXONOMY[d]:
                if positions[d] is None:positions[d]=[]
                if tag not in positions[d]:positions[d].append(tag)
        lines.append(json.dumps({'imdb_id':p['imdb_id'],'summary':p['profile_summary'],'positions':positions},ensure_ascii=False,separators=(',',':')))
    FILE.write_text('\n'.join(lines)+'\n')
    metadata={'exported_at':datetime.now(timezone.utc).isoformat(),'profiles':len(lines),'families':len(VISIBLE_TAXONOMY),
              'basis':'Provisional model interpretations using supplied source context and knowledge; no verification claimed.',
              'unknown':'null means insufficient knowledge or material in this pass.',
              'spoiler_policy':'Ending, character-arc, mystery/revelation, and tragedy detail families are omitted.',
              'contents':'Profile summaries and semantic tags keyed by IMDb ID; four spoiler-sensitive tag families are omitted. Summaries may contain plot details and the UI keeps them collapsed with a warning. No IMDb ratings, votes, source article text, or personal library entries.'}
    FILE.with_suffix('.meta.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2))

def restore():
    db=sqlite3.connect(ROOT/'data'/'watch-map.sqlite3');db.row_factory=sqlite3.Row
    profiles=[]
    for line in FILE.read_text().splitlines():
        row=json.loads(line);identifier=row['imdb_id'];dimensions=[]
        if set(row['positions'])!=set(VISIBLE_TAXONOMY):raise ValueError('Unexpected dimension set')
        current=db.execute('SELECT current_run_id FROM title_profiles WHERE imdb_id=?',(identifier,)).fetchone()
        if not current:raise ValueError('Initialize the selected catalog and profiles first: '+identifier)
        for d,tags in row['positions'].items():
            if tags is not None and (not isinstance(tags,list) or any(t not in VISIBLE_TAXONOMY[d] for t in tags)):
                raise ValueError('Invalid position: '+identifier+'/'+d)
            claims=[]
            # A snapshot restores generated positions; earlier cited pilot work is
            # kept when already present in this database.
            for a in db.execute('''SELECT a.*,tr.label FROM title_attributes a LEFT JOIN traits tr ON tr.id=a.trait_id
                WHERE a.imdb_id=? AND a.analysis_run_id=? AND a.dimension_slug=?
                AND EXISTS(SELECT 1 FROM attribute_evidence e WHERE e.attribute_id=a.id)''',(identifier,current[0],d)):
                citations=[{'source_url':e['source_url'],'excerpt':e['supporting_excerpt'],'locator':e['locator']}
                  for e in db.execute('''SELECT d.source_url,e.supporting_excerpt,e.locator FROM attribute_evidence e
                    JOIN source_documents d ON d.id=e.document_id WHERE e.attribute_id=?''',(a['id'],))]
                claims.append({'trait':a['label'],'description':a['description'],'evidence_type':a['evidence_type'],'evidence':citations})
            for tag in tags or []:
                claims.append({'trait':tag,'description':tag.replace('-',' ').capitalize(),'evidence_type':'inferred','evidence':[]})
            dimensions.append({'dimension':d,'status':'provisional' if tags else 'source_supported' if claims else 'unknown',
               'reason':'Restored provisional model interpretation; unverified.' if tags else 'Preserved cited assessment.' if claims else 'Insufficient knowledge or material in the original pass.','claims':claims})
        profiles.append({'imdb_id':identifier,'summary':row['summary'],'dimensions':dimensions})
    db.close()
    for offset in range(0,len(profiles),100):
        batch={'basis':'source_analysis','model':'conversation-agent-batch','prompt_version':'catalog-provisional-v1',
               'notes':'Restored original provisional model positions; existing cited pilot assertions preserved separately.',
               'profiles':profiles[offset:offset+100]}
        with tempfile.NamedTemporaryFile(mode='w',suffix='.json') as f:
            json.dump(batch,f);f.flush();import_batch(f.name)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('export','import'));args=parser.parse_args()
    export() if args.action=='export' else restore()
