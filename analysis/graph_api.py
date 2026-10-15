"""Read graph neighborhoods, compare exact title pairs, and record local feedback."""
import json
from collections import defaultdict

SPOILER_FAMILIES = ('resolution','character_arc','mystery','tragedy')

def title(db, identifier):
    row=db.execute('''SELECT t.imdb_id,t.title,t.title_type,t.start_year,t.rating_tenths/10.0 AS rating,t.num_votes,
        COALESCE(p.status,'awaiting_analysis') AS profile_status,COALESCE(p.profile_summary,'') AS profile_summary,
        COALESCE(l.seen,0) AS seen,COALESCE(l.watchlist,0) AS watchlist
        FROM titles t LEFT JOIN title_profiles p ON p.imdb_id=t.imdb_id
        LEFT JOIN personal_library l ON l.imdb_id=t.imdb_id WHERE t.imdb_id=? AND t.in_scope=1''',(identifier,)).fetchone()
    return dict(row) if row else None


def edge(db,row):
    value=dict(row)
    value['evidence']=[]
    for r in db.execute('''SELECT a.imdb_id,a.description,a.evidence_type,e.supporting_excerpt,d.source_url,d.provider
        FROM connection_evidence ce JOIN title_attributes a ON a.id=ce.attribute_id
        LEFT JOIN attribute_evidence e ON e.attribute_id=a.id LEFT JOIN source_documents d ON d.id=e.document_id
        WHERE ce.connection_id=? ORDER BY a.imdb_id,a.id''',(row['id'],)):
        # Never send plot excerpts across the graph API. The UI can link to a
        # source on request without rendering potentially revealing passages.
        value['evidence'].append({'imdb_id':r['imdb_id'],'source_url':r['source_url'],'provider':r['provider']})
    return value


def run_graph(request,db):
    action=request.get('action')
    family_placeholders=','.join('?' for _ in SPOILER_FAMILIES)
    if action=='graph_titles':
        return {'titles':[dict(r) for r in db.execute('''SELECT imdb_id,title,title_type,start_year FROM titles WHERE in_scope=1 ORDER BY title COLLATE NOCASE,start_year''')],
                'dimensions':[dict(r) for r in db.execute(f"SELECT slug,name FROM dimensions WHERE slug NOT IN ({family_placeholders}) ORDER BY name",SPOILER_FAMILIES)]}
    if action=='graph_feedback':
        status=request.get('status')
        if status not in ('accepted','rejected','unreviewed'):
            raise ValueError('Invalid feedback state')
        identifier=int(request['connection_id'])
        expected=request.get('connection',{})
        keys=('title_a','title_b','dimension_slug','shared_quality')
        if any(key not in expected for key in keys):
            raise ValueError('Reload the graph before reviewing this connection')
        with db:
            changed=db.execute('''UPDATE connections SET review_status=? WHERE id=? AND title_a=? AND title_b=?
                AND dimension_slug=? AND shared_quality=?''',(status,identifier,*(expected[k] for k in keys))).rowcount
        if not changed:
            raise ValueError('This connection changed during a graph rebuild. Reload before reviewing it.')
        return {'connection_id':identifier,'status':status}
    identifier=request.get('seed')
    source=title(db,identifier)
    if not source:
        raise ValueError('Choose a title from the catalog')
    graph_ready=bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='graph_candidate_metadata'").fetchone())
    completed=db.execute("SELECT COUNT(*) FROM title_profiles WHERE status!='awaiting_analysis'").fetchone()[0]
    scope=db.execute('SELECT COUNT(*) FROM titles WHERE in_scope=1').fetchone()[0]
    result={'seed':source,'progress':{'profiled':completed,'total':scope},'neighbors':[],'pair':None}
    if not graph_ready:
        result['state']='graph_not_built'
        return result
    other_id=request.get('compare')
    if other_id:
        if other_id==identifier:
            raise ValueError('Choose two different titles to compare')
        other=title(db,other_id)
        if not other:
            raise ValueError('Choose the comparison title from the catalog')
        rows=db.execute('''SELECT c.*,d.name AS dimension_name,m.origin,m.ranking_weight FROM connections c
            JOIN dimensions d ON d.slug=c.dimension_slug LEFT JOIN graph_candidate_metadata m ON m.connection_id=c.id
            WHERE ((c.title_a=? AND c.title_b=?) OR (c.title_a=? AND c.title_b=?))
            AND c.review_status!='rejected' AND c.dimension_slug NOT IN (?,?,?,?) ORDER BY (c.review_status='accepted') DESC,m.ranking_weight DESC,c.id''',
            (identifier,other_id,other_id,identifier,*SPOILER_FAMILIES)).fetchall()
        # A pair search examines all shared positions, even when the pair was not
        # retained among a title's top graph neighbors.
        saved_dimensions={r['dimension_slug'] for r in rows}
        # A rejected saved link must not reappear as a synthetic pair result.
        saved_dimensions.update(r[0] for r in db.execute(f'''SELECT dimension_slug FROM connections
            WHERE ((title_a=? AND title_b=?) OR (title_a=? AND title_b=?)) AND review_status='rejected'
            AND dimension_slug NOT IN ({family_placeholders}) ''',
            (identifier,other_id,other_id,identifier,*SPOILER_FAMILIES)))
        shared_by_dimension=defaultdict(list)
        for r in db.execute('''SELECT DISTINCT a.dimension_slug,tr.label,d.name FROM title_attributes a
            JOIN title_profiles pa ON pa.imdb_id=a.imdb_id AND pa.current_run_id=a.analysis_run_id
            JOIN title_attributes b ON b.trait_id=a.trait_id AND b.imdb_id=?
            JOIN title_profiles pb ON pb.imdb_id=b.imdb_id AND pb.current_run_id=b.analysis_run_id
            JOIN traits tr ON tr.id=a.trait_id JOIN dimensions d ON d.slug=a.dimension_slug
            WHERE a.imdb_id=? AND a.dimension_slug NOT IN (?,?,?,?) AND tr.label NOT IN ('minimal','linear','grounded-realism','emotional-investment','clear-answers','completed-arcs','continuing-story')
            ORDER BY d.name,tr.label''',(other_id,identifier,*SPOILER_FAMILIES)):
            if r['dimension_slug'] not in saved_dimensions:
                shared_by_dimension[(r['dimension_slug'],r['name'])].append(r['label'].replace('-',' '))
        comparison=[]
        for dimension in db.execute(f"SELECT slug,name FROM dimensions WHERE slug NOT IN ({family_placeholders}) ORDER BY name",SPOILER_FAMILIES).fetchall():
            item={'slug':dimension['slug'],'name':dimension['name']}
            for key,which in [('left',identifier),('right',other_id)]:
                status=db.execute('SELECT status FROM profile_dimensions WHERE imdb_id=? AND dimension_slug=?',(which,dimension['slug'])).fetchone()
                attributes=db.execute('''SELECT a.description,tr.label FROM title_attributes a
                    JOIN title_profiles p ON p.imdb_id=a.imdb_id AND p.current_run_id=a.analysis_run_id
                    LEFT JOIN traits tr ON tr.id=a.trait_id WHERE a.imdb_id=? AND a.dimension_slug=? ORDER BY a.id''',(which,dimension['slug'])).fetchall()
                item[key]={'status':status[0] if status else 'unknown','positions':[dict(a) for a in attributes]}
            comparison.append(item)
        shared=[]
        for (slug,name),labels in shared_by_dimension.items():
            positions=next(d for d in comparison if d['slug']==slug)
            differences='\n'.join(t['title']+': '+', '.join(p['description'] for p in positions[key]['positions'])
                                  for t,key in [(source,'left'),(other,'right')])
            shared.append({'dimension_slug':slug,'dimension_name':name,'shared_quality':', '.join(labels),
                           'explanation':'Both current profiles have these provisional positions. This pair has not been individually reviewed.',
                           'differences':differences,'review_status':'unreviewed','origin':'on_demand_shared_traits','id':None,'evidence':[]})
        result['pair']={'title':other,'connections':[edge(db,r) for r in rows]+shared,
                        'dimensions':comparison,
                        'note':'A connection describes a particular shared quality. It is not a prediction of overall enjoyment.'}
    dimension=request.get('dimension','')
    conditions=["(c.title_a=? OR c.title_b=?)","c.review_status!='rejected'"]
    conditions.append(f"c.dimension_slug NOT IN ({family_placeholders})")
    params=[identifier,identifier,*SPOILER_FAMILIES]
    if dimension:
        conditions.append('c.dimension_slug=?');params.append(dimension)
    if request.get('unseen')=='1':
        conditions.append('COALESCE(l.seen,0)=0')
    rows=db.execute('''SELECT c.*,d.name AS dimension_name,m.origin,m.ranking_weight,
        CASE WHEN c.title_a=? THEN c.title_b ELSE c.title_a END AS other_id
        FROM connections c JOIN dimensions d ON d.slug=c.dimension_slug
        LEFT JOIN graph_candidate_metadata m ON m.connection_id=c.id
        LEFT JOIN personal_library l ON l.imdb_id=CASE WHEN c.title_a=? THEN c.title_b ELSE c.title_a END
        WHERE '''+' AND '.join(conditions)+''' ORDER BY (c.review_status='accepted') DESC,COALESCE(m.ranking_weight,0) DESC,c.id''',
        [identifier,identifier]+params).fetchall()
    grouped=defaultdict(list)
    for row in rows:
        grouped[row['other_id']].append(row)
    ranked=sorted(grouped,key=lambda other:(-any(r['review_status']=='accepted' for r in grouped[other]),-len({r['dimension_slug'] for r in grouped[other]}),-sum(r['ranking_weight'] or 0 for r in grouped[other]),other))
    used=set()
    chosen=[]
    # Show several routes when no particular family is selected.
    if not dimension:
        for other in ranked:
            families={r['dimension_slug'] for r in grouped[other]}
            if not families-used:
                continue
            chosen.append(other);used.update(families)
            if len(chosen)>=6:
                break
    chosen.extend(other for other in ranked if other not in chosen)
    pages=max(1,(len(chosen)+7)//8)
    page=max(1,min(int(request.get('page',1)),pages))
    for other in chosen[(page-1)*8:page*8]:
        entries=grouped[other]
        result['neighbors'].append({'title':title(db,other),'connections':[edge(db,r) for r in entries],
                                    'route':entries[0]['dimension_name'],'shared_quality':entries[0]['shared_quality']})
    result['state']='ready'
    result['total_neighbors']=len(grouped)
    result['page']=page
    result['pages']=pages
    return result
