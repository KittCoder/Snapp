#!/usr/bin/env python3
"""Compare bounded SQL candidates with saved file baselines; never presents SQLite as Supabase.

Use --sqlite PATH --prepare-sqlite for a local SQL rehearsal, or --supabase for real verification.
"""
from __future__ import annotations
from dataclasses import asdict
import argparse
import gc
import json
import math
import os
import sqlite3
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Model'));sys.path.insert(0,str(ROOT))
from store_catalogs import StoreRegistry,DEFAULT_FEATURES_PATH
from store_comparison import BasketComparison
from supabase_store_catalog import DatabaseStoreRegistry,CandidateCache,SupabaseGateway,FEATURE_VERSION
from scripts.import_store_catalog import version_id
from product_ontology import describe

class SQLiteGateway:
    """Test adapter only: parameterized queries against an on-disk catalog, no RAM inventories."""
    def __init__(self,path):self.path=str(path);self.query_count=0;self.lock=threading.Lock()
    def select(self,table,params):
        clauses=[];args=[]
        columns={'stores':'id,metadata','store_inventory_versions':'id,store_id,source_version,product_count,feature_version'}[table]
        for key,value in params.items():
            if key in ('select','limit'):continue
            if value.startswith('eq.'):
                clauses.append(key+'=?');args.append(True if value[3:]=='true' else value[3:])
        with self.lock:self.query_count+=1
        with sqlite3.connect(self.path) as db:
            db.row_factory=sqlite3.Row
            rows=[dict(r) for r in db.execute('SELECT '+columns+' FROM '+table+(' WHERE '+' AND '.join(clauses) if clauses else '')+' LIMIT ?',args+[params.get('limit',100)])]
        for row in rows:
            if 'metadata' in row:row['metadata']=json.loads(row['metadata'])
        return rows
    def candidates(self,store,version,field,values,limit):
        if not values:return []
        if field not in ('family','subfamily','semantic_head','normalized_name'):raise ValueError(field)
        args=[store,version]
        if field=='normalized_name':
            predicate='normalized_name LIKE ?';args.append('%'+'%'.join(values[0].split())+'%')
        else:
            predicate=field+' IN ('+','.join('?' for _ in values)+')';args.extend(values)
        args.append(limit)
        with self.lock:self.query_count+=1
        with sqlite3.connect(self.path) as db:
            rows=db.execute('SELECT feature_json,identity_json,source_json,source_position FROM store_products WHERE store_id=? AND inventory_version_id=? AND '+predicate+' ORDER BY source_position LIMIT ?',args)
            return [{'feature_json':json.loads(f),'identity_json':json.loads(i),'source_json':json.loads(s),'source_position':p} for f,i,s,p in rows]

def prepare(path):
    if Path(path).exists():raise RuntimeError('Refusing to overwrite existing rehearsal database')
    registry=StoreRegistry()
    if registry.errors:raise RuntimeError(str(registry.errors))
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE stores(id TEXT PRIMARY KEY,metadata TEXT,verified BOOLEAN,active BOOLEAN);
        CREATE TABLE store_inventory_versions(id TEXT PRIMARY KEY,store_id TEXT,source_version TEXT,product_count INTEGER,feature_version TEXT,active BOOLEAN);
        CREATE TABLE store_products(store_id TEXT,inventory_version_id TEXT,family TEXT,subfamily TEXT,semantic_head TEXT,normalized_name TEXT,feature_json TEXT,identity_json TEXT,source_json TEXT,source_position INTEGER);
        CREATE INDEX family_lookup ON store_products(store_id,inventory_version_id,family);
        CREATE INDEX head_lookup ON store_products(store_id,inventory_version_id,semantic_head);''')
        for catalog in registry.stores.values():
            m=catalog.metadata;vid=version_id(m)
            db.execute('INSERT INTO stores VALUES(?,?,1,1)',(m.id,json.dumps(m.public())))
            db.execute('INSERT INTO store_inventory_versions VALUES(?,?,?,?,?,1)',(vid,m.id,m.inventory_version,m.product_count,FEATURE_VERSION))
            builder=None
            if m.retailer=='ctown':
                # Validate the deterministic feature cache through the production file adapter.
                builder=catalog.builder();features=builder.match_service.retriever.features
                identities=builder.match_service.identity_catalog.identities;sources=catalog._rows
            else:
                features=json.loads(DEFAULT_FEATURES_PATH.read_text())['features'];sources={};identities={}
            def records():
                for position,f in enumerate(features):
                    identity=identities.get(f['product_id']) or describe(f.get('original_product_name') or f.get('normalized_name'),feature=f,product=True)
                    yield (m.id,vid,identity.family,identity.subfamily,identity.semantic_head,f.get('normalized_name') or '',json.dumps(f),json.dumps(asdict(identity)),json.dumps(sources.get(f['product_id'],{})),position)
            db.executemany('INSERT INTO store_products VALUES(?,?,?,?,?,?,?,?,?,?)',records());db.commit()
            print(json.dumps({'prepared':m.id,'rows':len(features)}),flush=True)
            catalog._builder=None;catalog._rows=None
            del features,identities,sources,builder
            gc.collect()

def stable(value):
    if isinstance(value,dict):return {k:stable(v) for k,v in value.items() if k not in ('latency_ms','elapsed_ms','cache_hit')}
    if isinstance(value,list):return [stable(v) for v in value]
    return value

def rss():
    return int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())]).strip())/1024

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--sqlite',type=Path);group.add_argument('--supabase',action='store_true');group.add_argument('--file-baseline',action='store_true')
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--prepare-sqlite',action='store_true');parser.add_argument('--samples',type=int,default=5)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.prepare_sqlite:
        if not args.sqlite:parser.error('--prepare-sqlite requires --sqlite')
        prepare(args.sqlite);return
    baseline_root=ROOT/'data/store_scrapes/audit/multi_store_review'
    before=rss()
    saved=json.loads((baseline_root/'recipe_comparisons.json').read_text())
    chosen=[r for r in saved if any(s in r['recipe']['name'].lower() for s in ('patty melts','lamb in pitas','tuscan salad'))]
    example=json.loads((baseline_root/'example.json').read_text())
    cases=[(r['recipe']['name'],[r['recipe']],r['comparison']) for r in chosen]
    cases.append(('rice + butter',example['recipes'],example['comparison']))
    if args.file_baseline:
        engine=BasketComparison()
        current=[]
        for name,recipes,expected in cases:
            result=engine.compare(recipes,[s['id'] for s in expected['stores']])
            current.append({'name':name,'recipes':recipes,'comparison':result})
            print(json.dumps({'baseline':name,'store_count':len(result['stores'])}),flush=True)
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps({'cases':current,'rss_before_registry_mib':before,'rss_after_all_stores_mib':rss()},indent=2)+'\n')
        engine.pool.shutdown();return
    if args.baseline:
        cases=[(c['name'],c['recipes'],c['comparison']) for c in json.loads(args.baseline.read_text())['cases']]
    gateway=SQLiteGateway(args.sqlite) if args.sqlite else SupabaseGateway()
    cache=CandidateCache();engine=BasketComparison(DatabaseStoreRegistry(gateway,cache));registered=rss()
    output={'backend':'SQLite SQL rehearsal (NOT Supabase)' if args.sqlite else 'Supabase',
            'live_supabase_verified':not bool(args.sqlite),'parity':[], 'rss_before_registry_mib':before,
            'rss_registry_mib':registered,'performance':{}}
    for name,recipes,expected in cases:
        ids=[s['id'] for s in expected['stores']]
        q0=gateway.query_count;h0=cache.hits;m0=cache.misses
        actual=engine.compare(recipes,ids)
        passed=stable(actual)==stable(expected)
        changes=[a['id'] for a,e in zip(actual['stores'],expected['stores']) if stable(a)!=stable(e)]
        output['parity'].append({'recipe':name,'store_count':len(ids),'equivalent':passed,'different_stores':changes,'database_queries':gateway.query_count-q0,'candidate_cache_hits':cache.hits-h0,'candidate_cache_misses':cache.misses-m0})
        print(json.dumps(output['parity'][-1]),flush=True)
        if not passed:
            args.report.parent.mkdir(parents=True,exist_ok=True)
            (args.report.parent/('parity_difference_'+str(len(output['parity']))+'.json')).write_text(json.dumps({'actual':actual,'expected':expected},indent=2))
    all_ids=list(engine.registry.stores)
    for label,ids in [('single',['ctown:PS41_311']),('three',['ctown:PS41_311','ctown:U41_131','ctown:U41_205']),('all',all_ids)]:
        times=[];cached=[];q0=gateway.query_count;h0=cache.hits;m0=cache.misses
        for i in range(args.samples):
            recipes=[dict(chosen[0]['recipe'],id='sql-bench-'+label+'-'+str(i))]
            start=time.perf_counter();engine.compare(recipes,ids);times.append((time.perf_counter()-start)*1000)
            start=time.perf_counter();engine.compare(recipes,ids);cached.append((time.perf_counter()-start)*1000)
        def stats(values):return {'samples':len(values),'median_ms':statistics.median(values),'p95_ms':sorted(values)[math.ceil(.95*len(values))-1]}
        output['performance'][label]={'uncached_basket':stats(times),'basket_cache':stats(cached),
                  'database_queries':gateway.query_count-q0,'candidate_cache_hits':cache.hits-h0,'candidate_cache_misses':cache.misses-m0}
        print(json.dumps({label:output['performance'][label]}),flush=True)
    engine.cache.clear();gc.collect();output['rss_after_all_stores_mib']=rss()
    output['database_queries_total']=gateway.query_count;output['redis_enabled']=cache.client is not None
    output['last_candidate_pool_by_store']={key:getattr(catalog,'last_candidate_count',None) for key,catalog in engine.registry.stores.items()}
    output['equivalent']=all(c['equivalent'] for c in output['parity'])
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(output,indent=2)+'\n')
    engine.pool.shutdown()
    if not output['equivalent']:sys.exit(1)
if __name__=='__main__':main()
