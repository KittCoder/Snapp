"""Offline staging comparison using structural SNAPP matching and unchanged DealOptimizer.

No network, production inventory, vector index, or production configuration is
read for product matching. Each service receives one location's staged features.
"""
from __future__ import annotations
import argparse,json,re
from collections import defaultdict
from pathlib import Path
try: from .common import ROOT,OUT,write_json,parse_price,utcnow
except ImportError: from common import ROOT,OUT,write_json,parse_price,utcnow
from ingredient_normalization import extract_product_features,parse_ingredient
from product_retrieval import ProductCandidateRetriever
from product_compatibility import ProductMatchService
from basket_quantity import BasketBuilder,canonical_quantity
SMOKE=['ground beef','white sugar','rice','olive oil','extra virgin olive oil','red wine vinegar','balsamic vinegar','garlic','fresh mint','cheddar cheese','provolone cheese','black beans','chickpeas','chicken breast','skirt steak','kosher salt','low-sodium broth','tomato sauce','oregano','parsley','pasta']

def feature_for(row):
    # Existing feature parser expects currency strings; do not parse bare numbers
    # through its intentionally narrower public-source interface.
    current=row.get('effective_current_price');source_price=f'${current:.4f}' if parse_price(current) else ''
    if source_price:source_price=f'${current:.2f}'
    raw=row.get('raw_price_text') or ''
    multi=re.fullmatch(r'(\d+)\s*(?:for|/)\s*\$?(\d+(?:\.\d{1,2})?)',raw.strip(),re.I)
    if multi and not row.get('sale_price'):source_price=multi[1]+' for $'+multi[2]
    rate=re.search(r'\$?\s*(\d+(?:\.\d{1,2})?)\s*(?:/|per\s+)(lb|pound|oz|ounce|kg|g)\b',raw,re.I)
    if row.get('price_basis')=='weight' and rate:source_price=f'${current:.2f}/'+rate[2] if parse_price(current) else ''
    size=row.get('raw_size_text') or ''
    f=extract_product_features({'source':row['retailer']+'-public-staging','id':row['source_product_id'],'source_id':row['source_product_id'],'name':row['name'],'price':source_price,'raw_size_text':size,'unit':size,'source_categories':(row.get('source_metadata') or {}).get('category_names', [row.get('category')]),'category':row.get('category'),'subcategory':row.get('subcategory'),'brand':row.get('brand'),'source_url':row['source_url'],'store_id':row.get('store_id'),'availability':row.get('availability'),'original_price':('$%.2f'%row['regular_price']) if row.get('regular_price') else None,'sale_price':('$%.2f'%row['sale_price']) if row.get('sale_price') else None,'is_on_sale':row.get('sale_price') is not None})
    f['verified_label_text']=(row.get('source_metadata') or {}).get('verified_label_text')
    # Staging adapter treats unknown price basis as uncertain economics.
    # Product identity is still available to the matcher.
    if row.get('price_basis')=='unknown' or row.get('price_basis')=='weight' and not rate:
        f['package_parse_confidence']='low';f['package_parse_warnings']=(f.get('package_parse_warnings') or [])+['source price basis unresolved']
    metadata=row.get('source_metadata') or {}
    minimum=metadata.get('minimum_quantity');increment=metadata.get('quantity_increment')
    weight_rules=metadata.get('quantity_attributes_weight') or {}
    if minimum is None:minimum=weight_rules.get('min')
    if increment is None:increment=weight_rules.get('increment')
    constrained=(row.get('price_basis')=='weight' and (parse_price(minimum) is not None or parse_price(increment) is not None)) or (row.get('price_basis')!='weight' and ((parse_price(minimum) or 0)>1 or (parse_price(increment) or 0)>1))
    if metadata.get('estimated_price') is True:
        f['package_parse_confidence']='low'
        f['package_parse_warnings']=(f.get('package_parse_warnings') or [])+['source explicitly marks checkout price as estimated']
    if constrained:
        f['package_parse_confidence']='low'
        f['package_parse_warnings']=(f.get('package_parse_warnings') or [])+['source purchase minimum/increment not supported by staging cost adapter']
    if row.get('price_basis')=='weight' and rate and parse_price(current)!=parse_price(rate[1]) and not row.get('sale_price'):
        f['package_parse_confidence']='low'
        f['package_parse_warnings']=(f.get('package_parse_warnings') or [])+['source weight rate differs from displayed checkout price']
    category=str(row.get('category') or '').casefold()
    memberships=(metadata.get('category_names') or [])+[category]
    # Source department filtering is staging inventory preparation, not matcher tuning.
    nonfood={'pets','pet supplies','household','household supplies','health & beauty','health and beauty','beauty','personal care'}
    if category in nonfood or memberships and all(str(c).casefold() in nonfood for c in memberships):
        f['eligible_for_retrieval']=False
        f['exclusion_reasons']=(f.get('exclusion_reasons') or [])+['source nonfood department excluded from staging recipe inventory']
    if row.get('availability') is False:
        f['eligible_for_retrieval']=False;f['exclusion_reasons']=(f.get('exclusion_reasons') or [])+['explicitly unavailable at source store']
    return f

class StagingAggregator:
    def __init__(self,root=OUT,retailers=None):
        self.root=Path(root);self.rows=defaultdict(list);self.services={};self.builders={}
        for path in sorted(self.root.glob('*/products.jsonl')):
            if retailers and path.parent.name not in retailers:continue
            for line in path.read_text().splitlines():
                if not line.strip():continue
                r=json.loads(line);key=(r['retailer'],r.get('store_id') or r.get('service_area_id'));self.rows[key].append(r)
    def service(self,key):
        if key not in self.services:
            rows=self.rows[key];safeid=re.sub('[^a-zA-Z0-9_-]','_',str(key[1]))
            path=self.root/key[0]/'normalized'/('matcher_features_'+safeid+'.json')
            features=[feature_for(r) for r in rows];write_json(path,{'metadata':{'staging_only':True,'generated_at':utcnow(),'store_id':key[1]},'features':features})
            retriever=ProductCandidateRetriever(features_path=path,index_dir=path.parent/'no_vector_index')
            self.services[key]=ProductMatchService(retriever=retriever);self.builders[key]=BasketBuilder(self.services[key])
        return self.services[key]
    def ingredient(self,text):
        results=[]
        for key,rows in self.rows.items():
            service=self.service(key);match=service.match_recipe_ingredients([text],limit=15,use_semantic=False)[0]
            # Stronger source-claim verification for staging qualification. The
            # established single-store matcher still accepts relative sodium claims.
            candidates=([match.selected_match] if match.selected_match else [])+match.compatible_alternatives
            blocked=[]
            if re.search(r'\blow[ -]sodium\b',text,re.I):
                for c in candidates:
                    name=service.feature_by_id[c.product_id].get('original_product_name','')
                    if re.search(r'\b(?:lower|less|reduced)[ -]sodium\b',name,re.I) and not re.search(r'\blow[ -]sodium\b',name,re.I):blocked.append(c.product_id)
            candidates=[c for c in candidates if c.product_id not in blocked]
            optimizer_input_ids=[c.product_id for c in candidates]
            selected=candidates[0] if candidates else None
            match.compatible_alternatives=candidates[1:]
            deal=None
            if selected:
                parsed=parse_ingredient(text);required=canonical_quantity(parsed.quantity,parsed.unit,parsed.canonical_name)
                deal=self.builders[key].optimize_ingredient_purchase(required,parsed.canonical_name,[selected]+match.compatible_alternatives,top1_product_id=selected.product_id,rejected_candidates=match.rejected_candidates)
            chosen=deal.selected if deal and deal.selected else None
            source=next((r for r in rows if chosen and r['source_product_id']==chosen.product_id),None)
            results.append({'retailer':key[0],'store_id':key[1],'store_name':rows[0].get('store_name'),'ingredient':text,'selected_product':source,'optimizer_input_ids':optimizer_input_ids,'pre_optimizer_withheld_ids':blocked,'identity_match':selected.to_dict() if selected else None,'valid_candidates':[c.to_dict() for c in ([selected] if selected else [])+match.compatible_alternatives],'deal':deal.to_dict() if deal else None,'estimated_ingredient_cost':chosen.effective_cost if chosen and chosen.deal_confidence=='high' else None,'cost_note':'Only an explicit requested quantity with reliable package/rate data yields an estimate. No-quantity smoke queries may retain identity with unknown economics.'})
        from scripts.store_scrapers.structural_review import review
        for result in results:
            # Report the unchanged matcher's output; quarantine its economics when
            # independent audit evidence shows an obvious structural mismatch.
            # No matcher thresholds, decisions, or DealOptimizer logic are changed.
            parsed_review=parse_ingredient(result['ingredient'])
            audit_result=dict(result,ingredient=parsed_review.canonical_name) if parsed_review.quantity is not None else result
            flags=review([audit_result]);result['structural_review_flags']=flags
            result['requires_structural_review']=bool(flags)
            result['candidate_validation_status']='provisional; matcher compatibility is not independent correctness verification'
            result['matcher_compatible_candidates']=result['valid_candidates']
            valid=[]
            source_by_id={r['source_product_id']:r for r in self.rows[(result['retailer'],result['store_id'])]}
            for candidate in result['matcher_compatible_candidates']:
                candidate_review=review([dict(audit_result,selected_product=source_by_id.get(candidate['product_id']))])
                if not any(f['classification']=='FAILURE' for f in candidate_review):valid.append(candidate)
            result['valid_candidates']=valid
            if result['requires_structural_review']:
                result['estimated_ingredient_cost']=None
                result['cost_note']='Withheld: independent structural audit found a mismatch or unresolved ingredient equivalence in the unchanged matcher output.'
        return results
    def basket(self,ingredients):
        bystore=defaultdict(list)
        for ingredient in ingredients:
            for row in self.ingredient(ingredient):bystore[(row['retailer'],row['store_id'])].append(row)
        return [{'retailer':key[0],'store_id':key[1],'ingredients':rows,'priced_ingredients':sum(r['estimated_ingredient_cost'] is not None for r in rows),'ingredient_count':len(rows),'estimated_total':round(sum(r['estimated_ingredient_cost'] for r in rows),2) if all(r['estimated_ingredient_cost'] is not None for r in rows) else None,'known_subtotal':round(sum(r['estimated_ingredient_cost'] or 0 for r in rows),2),'complete_estimate':all(r['estimated_ingredient_cost'] is not None for r in rows),'fees_taxes_excluded':True} for key,rows in bystore.items()]

def main():
    p=argparse.ArgumentParser();p.add_argument('--ingredient',action='append');p.add_argument('--basket',type=Path,help='JSON array of quantity-bearing ingredient strings');p.add_argument('--smoke',action='store_true');p.add_argument('--retailer',action='append');a=p.parse_args()
    agg=StagingAggregator(retailers=a.retailer)
    if a.smoke:
        results=[r for q in SMOKE for r in agg.ingredient(q)];path=OUT/'audit/matcher_smoke.json';write_json(path,{'generated_at':utcnow(),'mode':'structural production matcher, staging-only lexical retrieval','queries':SMOKE,'stores_tested':len(agg.rows),'results':results,'structural_flags':[{'retailer':r['retailer'],'store_id':r['store_id'],'ingredient':r['ingredient'],'reasons':r['deal']['selected']['exclusion_reasons']} for r in results if r.get('deal') and r['deal'].get('selected') and r['deal']['selected'].get('exclusion_reasons')]});print(path)
    elif a.basket:print(json.dumps(agg.basket(json.loads(a.basket.read_text())),indent=2))
    else:print(json.dumps([r for q in a.ingredient or ['rice'] for r in agg.ingredient(q)],indent=2))
if __name__=='__main__':main()
