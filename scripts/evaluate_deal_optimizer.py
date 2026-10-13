#!/usr/bin/env python3
"""Real population replay: identity baseline versus constrained purchase selection."""
import json, statistics, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Model'))
from product_compatibility import ProductMatchService, profile_from_query
from basket_quantity import BasketBuilder, canonical_quantity
from ingredient_normalization import parse_ingredient
from product_ontology import compatibility

def percentile(xs,p): return sorted(xs)[int((len(xs)-1)*p)] if xs else None

def main():
    out=ROOT/'data/deal_optimizer_audit';out.mkdir(exist_ok=True)
    texts=[json.loads(line)['ingredient_query'] for line in (ROOT/'data/matcher_validation/population.jsonl').open()]
    benchmark=json.loads((ROOT/'Model/evaluation/ingredient_inventory_benchmark.json').read_text())
    labels={q['text']:q for q in benchmark['queries']}; labelled_ids={p['id'] for p in benchmark['products']}
    service=ProductMatchService();builder=BasketBuilder(service)
    rows=[];added=[];matching=[];savings=[];unsafe=lower=changed=multi=accepted=0;good=wrong=fn=positive=unknown=0
    for offset in range(0,len(texts),200):
        batch=texts[offset:offset+200];start=time.perf_counter()
        results=service.match_recipe_ingredients(batch,limit=15,use_semantic=True)
        matching.extend(r.total_timing_ms for r in results)
        for text,result in zip(batch,results):
            chosen=result.selected_match;deal=None;baseline=None;valid=[]
            if chosen:
                accepted+=1
                parsed=parse_ingredient(text);required=canonical_quantity(parsed.quantity,parsed.unit,parsed.canonical_name)
                start=time.perf_counter()
                deal=builder.optimize_ingredient_purchase(required,parsed.canonical_name,[chosen]+result.compatible_alternatives,top1_product_id=chosen.product_id,rejected_candidates=result.rejected_candidates)
                added.append((time.perf_counter()-start)*1000)
                valid=[e for e in ([deal.selected] if deal.selected else [])+deal.alternatives if not e.exclusion_reasons]
                multi+=len(valid)>=2
                baseline=next((e for e in valid+deal.rejected if e.product_id==chosen.product_id),None)
                if deal.selected:
                    selected=deal.selected
                    changed+=selected.product_id!=chosen.product_id
                    query=profile_from_query(text,service.overrides)[0]
                    decision=compatibility(query.ontology,service.product_profile(service.feature_by_id[selected.product_id]).ontology)
                    unsafe+=not decision.allowed
                    if baseline and baseline.quality_tier and selected.quality_tier:
                        lower+=selected.quality_tier>baseline.quality_tier
                    if baseline and baseline.effective_cost is not None and selected.effective_cost is not None and baseline.deal_confidence=='high' and selected.deal_confidence=='high':
                        savings.append(baseline.effective_cost-selected.effective_cost)
                    chosen=next(c for c in [result.selected_match]+result.compatible_alternatives if c.product_id==selected.product_id)
            label=labels.get(text)
            if label:
                positive+=bool(label['acceptable_ids'])
                if chosen:
                    good+=chosen.product_id in label['acceptable_ids']
                    wrong+=chosen.product_id not in label['acceptable_ids'] and chosen.product_id in labelled_ids
                    unknown+=chosen.product_id not in labelled_ids
                else: fn+=bool(label['acceptable_ids'])
            rows.append({'ingredient_query':text,'baseline':result.selected_match.to_dict() if result.selected_match else None,'deal':deal.to_dict() if deal else None,'selected_product_id':chosen.product_id if chosen else None,'valid_count':len(valid)})
        print(f'evaluated {len(rows)}/{len(texts)}',flush=True)
    report={'population':len(rows),'accepted':accepted,'rejected':len(rows)-accepted,'no_match_rate':(len(rows)-accepted)/len(rows),'proxy_precision':good/(good+wrong) if good+wrong else None,'proxy_recall':good/positive if positive else None,'proxy_unknown_selected':unknown,'proxy_false_negatives':fn,'proxy_note':'Historical inventory name-rule labels; not independent human gold. Unknown IDs excluded from precision.','accepted_with_multiple_valid_pct':100*multi/accepted,'average_valid_candidates':sum(r['valid_count'] for r in rows)/accepted,'changed_selections':changed,'changed_pct':100*changed/accepted,'cost_comparable_cases':len(savings),'average_savings':statistics.mean(savings) if savings else None,'median_savings':statistics.median(savings) if savings else None,'p90_savings':percentile(savings,.9),'lower_tier_selections':lower,'unsafe_selections_introduced':unsafe,'matcher_median_ms':statistics.median(matching),'matcher_p95_ms':percentile(matching,.95),'added_median_ms':statistics.median(added),'added_p95_ms':percentile(added,.95),'latency_note':'Population batch matching, including startup; optimizer measured separately per accepted query.'}
    (out/'population.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
