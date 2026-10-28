"""Whole-store basket comparison through unchanged SNAPP matching and optimization."""
from __future__ import annotations
import copy,hashlib,json,threading,time
from collections import OrderedDict,defaultdict
from contextvars import copy_context
from catalog_timing import store_timing, timing
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from basket_quantity import ingredient_aggregation_signature,recipe_ingredients,OPTIMIZER_VERSION
from product_compatibility import MATCHER_VERSION
from product_ontology import ONTOLOGY_VERSION
import deal_optimizer
from pathlib import Path
DEAL_OPTIMIZER_VERSION=hashlib.sha256(Path(deal_optimizer.__file__).read_bytes()).hexdigest()
from deal_presentation import shopping_deal_fields
from store_catalogs import StoreRegistry,CatalogError

ADAPTER_VERSION='whole-store-comparison-v2-quantities'
def money(values):return float(sum((Decimal(str(v)).quantize(Decimal('.01')) for v in values),Decimal(0)))

def validate_recipes(recipes):
    if not isinstance(recipes,list) or not 1<=len(recipes)<=30:raise CatalogError('Supply between 1 and 30 recipes')
    count=0
    for recipe in recipes:
        if not isinstance(recipe,dict):raise CatalogError('Recipe must be an object')
        try:_,lines=recipe_ingredients(recipe)
        except (TypeError,AttributeError,ValueError):raise CatalogError('Invalid recipe ingredient structure')
        if any(len(line)>1000 for line in lines):raise CatalogError('Ingredient is too long')
        count+=len(lines)
    if not 1<=count<=250:raise CatalogError('Supply between 1 and 250 ingredient lines')

class BasketComparison:
    def __init__(self,registry=None):
        self.registry=registry or StoreRegistry();self.cache=OrderedDict();self.cache_lock=threading.Lock();self.pool=ThreadPoolExecutor(max_workers=4,thread_name_prefix='store-basket')
    def key(self,recipes,catalogs,semantic):
        return hashlib.sha256(json.dumps({'recipes':recipes,'stores':sorted((c.metadata.id,c.metadata.inventory_version) for c in catalogs),'overrides':sorted({c.override_hash or 'default' for c in catalogs}),'matcher':MATCHER_VERSION,'ontology':ONTOLOGY_VERSION,'optimizer':DEAL_OPTIMIZER_VERSION,'basket':OPTIMIZER_VERSION,'adapter':ADAPTER_VERSION,'mw_semantic':semantic},sort_keys=True,allow_nan=False).encode()).hexdigest()
    def _plan(self, recipes, catalogs, semantic, pantry_items):
        validate_recipes(recipes)
        from store_requirements import prepare_recipes
        quantities = [(r.get('source_servings') or r.get('servings'), r.get('target_servings')) for r in recipes]
        prepared, pantry = prepare_recipes(recipes, pantry_items)
        key = self.key({'recipes':prepared,'pantry':pantry,'servings':quantities},catalogs,semantic)
        cache_key = (key, tuple(sorted((c.metadata.id, getattr(c, 'cache_version', None)) for c in catalogs)))
        return prepared, pantry, key, cache_key

    def _cached(self, plan):
        with self.cache_lock:
            value = self.cache.get(plan[3])
            if value is None:
                return None
            self.cache.move_to_end(plan[3])
            result = copy.deepcopy(value)
            result['cache_hit'] = True
            return result

    def _current(self, catalogs):
        current = self.registry.all_current(catalogs) if hasattr(self.registry, 'all_current') else all(c.current() for c in catalogs)
        if not current:
            raise CatalogError('Store inventory changed or unavailable; reload registry')

    def compare(self, recipes, store_ids, mw_semantic=False, pantry_items=None):
        catalogs = self.registry.select(store_ids)
        self._current(catalogs)
        plan = self._plan(recipes,catalogs,mw_semantic,pantry_items)
        cached = self._cached(plan)
        return cached if cached is not None else self._calculate(plan,catalogs,mw_semantic)

    def compare_recipes(self, recipes, store_id, mw_semantic=False, pantry_items=None):
        """One version check and one matching/embedding batch; independent purchases."""
        validate_recipes(recipes)
        if len(recipes)>10:
            raise CatalogError('Price at most 10 recipes at once')
        catalogs = self.registry.select([store_id])
        self._current(catalogs)
        catalog = catalogs[0]
        plans = [self._plan([recipe],catalogs,mw_semantic,pantry_items) for recipe in recipes]
        results = [self._cached(plan) for plan in plans]
        missing = [i for i, value in enumerate(results) if value is None]
        if missing:
            from types import SimpleNamespace
            with catalog.lock, store_timing(store_id):
                prepared_recipes = [recipe for i in missing for recipe in plans[i][0]]
                prepared = catalog.request_catalog(prepared_recipes) if hasattr(catalog,'request_catalog') else catalog
                builder = prepared.builder()
                lines = list(dict.fromkeys(line for recipe in prepared_recipes for line in recipe_ingredients(recipe)[1]))
                semantic = mw_semantic if catalog.metadata.retailer=='morton_williams' else False
                # The matcher deduplicates quantity-independent identities internally and
                # batches all missing embeddings in this single call.
                with timing('batch_match'):
                    matched = builder.match_service.match_recipe_ingredients(lines,limit=15,use_semantic=semantic)
                matches = dict(zip(lines,matched))
                snapshot = SimpleNamespace(metadata=prepared.metadata,lock=threading.RLock(),
                    builder=prepared.builder,source_row=prepared.source_row,_rows=prepared._rows)
                try:
                    for i in missing:
                        results[i] = self._calculate(plans[i],[snapshot],mw_semantic,matches)
                finally:
                    builder._basket_cache.clear()
        return [dict(result['stores'][0],recipe_id=str(recipe.get('id')),basket_id=result['basket_id'],
                     versions=result['versions'],cache_hit=result['cache_hit']) for recipe,result in zip(recipes,results)]

    def _calculate(self, plan, catalogs, mw_semantic, matches=None):
        recipes, pantry, key, cache_key = plan
        started=time.perf_counter();futures=[self.pool.submit(copy_context().run,self.store_basket,c,recipes,mw_semantic,matches) for c in catalogs];results=[f.result() for f in futures]
        for result in results:
            result['pantry_items'] = pantry
            if not result['ingredients_requested']:
                result.update(complete=True,basket_total=0.0)
        # Equal coverage alone is insufficient. Only complete, reliably costed baskets compare.
        complete=[r for r in results if r['complete']];best=min((r['basket_total'] for r in complete),default=None)
        for r in results:
            r['best_basket']=bool(len(complete)>=2 and r['complete'] and r['basket_total']==best)
            r['savings_vs_other_stores']={o['id']:round(o['basket_total']-r['basket_total'],2) for o in complete if r['complete'] and o['id']!=r['id']}
        results.sort(key=lambda r:(not r['complete'],-r['coverage_count'],r['basket_total'] if r['basket_total'] is not None else float('inf'),r['id']))
        result={'basket_id':key,'stores':results,'comparable_store_count':len(complete),'cache_hit':False,'elapsed_ms':round((time.perf_counter()-started)*1000,2),'fees_taxes_excluded':True,'versions':{'matcher':MATCHER_VERSION,'ontology':ONTOLOGY_VERSION,'deal_optimizer':DEAL_OPTIMIZER_VERSION,'basket':OPTIMIZER_VERSION,'adapter':ADAPTER_VERSION}}
        with self.cache_lock:
            self.cache[cache_key]=copy.deepcopy(result)
            while len(self.cache)>64:self.cache.popitem(last=False)
        return result
    @staticmethod
    def store_basket(catalog,recipes,mw_semantic=False,matches=None):
        with catalog.lock, store_timing(catalog.metadata.id), timing('store_basket'):
            catalog=catalog.request_catalog(recipes) if hasattr(catalog,'request_catalog') else catalog
            builder=catalog.builder()
            kwargs = {'matched_results':[matches[line] for recipe in recipes for line in recipe_ingredients(recipe)[1]]} if matches is not None else {}
            basket=builder.build_multi_recipe_basket(recipes,use_semantic=mw_semantic if catalog.metadata.retailer=='morton_williams' else False,**kwargs)
            # Every candidate and selected product must belong to this catalog.
            owned=set(builder.match_service.feature_by_id)
            if catalog.metadata.retailer=='ctown' and owned!=set(catalog._rows):raise CatalogError('Cross-store feature inventory rejected')
            requested=defaultdict(list);matched=defaultdict(list)
            for index,recipe in enumerate(recipes):
                for line in recipe_ingredients(recipe,index)[1]:requested[ingredient_aggregation_signature(line)[0]].append(line)
            for item in basket.matched_ingredients:
                if item.product_id and item.product_id not in owned:raise CatalogError('Cross-store candidate rejected')
                matched[ingredient_aggregation_signature(item.raw_ingredient)[0]].append(item)
            purchases={ingredient_aggregation_signature(item.ingredients[0])[0]:item for item in basket.shopping_basket}
            selections=[];unmatched=[];unknown=[];matched_count=0;known=[]
            for signature,lines in requested.items():
                observations=matched.get(signature,[]);has_match=bool(observations and all(m.product_id for m in observations));matched_count+=has_match
                if not has_match:unmatched.append({'ingredients':lines,'reason':'NO_SAFE_MATCH'})
                purchase=purchases.get(signature);cost=None;deal={};row=None
                if purchase:
                    if purchase.product_id not in owned:raise CatalogError('Cross-store selection rejected')
                    optimized=purchase.optimized_purchase
                    for candidate in ([optimized.selected] if optimized and optimized.selected else [])+(optimized.alternatives if optimized else []):
                        if candidate.product_id not in owned:raise CatalogError('Cross-store optimizer input rejected')
                    selected=optimized.selected if optimized else None;deal=shopping_deal_fields(optimized)
                    quantities_safe=bool(observations and all(m.required_quantity.base_quantity is not None for m in observations) and len({m.required_quantity.base_unit for m in observations})==1)
                    reliable=bool(has_match and quantities_safe and selected and selected.deal_confidence=='high' and not selected.exclusion_reasons and selected.cost.checkout_cost is not None)
                    cost=purchase.checkout_cost if reliable else None
                    if not reliable:deal=dict(deal,best_deal=False,savings_vs_closest_match=None,effective_cost=None,packages_needed=None,deal_confidence='unknown')
                    from ingredient_normalization import parse_ingredient
                    label = parse_ingredient(lines[0]).canonical_name
                    row={'display_name':label,'product_id':purchase.product_id,'product_name':purchase.product_name,'ingredients':lines,'total_required':purchase.total_required.to_dict(),'package_size':f'{selected.package.package_quantity:g} {selected.package.package_unit}' if selected and selected.package.package_quantity and selected.package.package_unit else None,'packages_needed':deal.get('packages_needed'),'checkout_cost':cost,'effective_cost':deal.get('effective_cost') if reliable else None,'deal':deal,'snap_eligible':None,'warnings':purchase.warnings,**{k:v for k,v in catalog.metadata.public().items() if k in ('retailer','store_id','store_name','address','borough')}}
                    source=catalog.source_row(purchase.product_id)
                    if source:row.update(source_url=source['source_url'],availability=source.get('availability'))
                    selections.append(row)
                if cost is not None:known.append(cost)
                else:unknown.append({'ingredients':lines,'reason':'NO_SAFE_MATCH' if not has_match else 'UNKNOWN_COST'})
            count=len(requested);complete=bool(count and matched_count==count and not unknown);meta=catalog.metadata.public()
            return dict(meta,ingredients_requested=[{'signature':k,'ingredients':v} for k,v in requested.items()],ingredients_matched=matched_count,ingredients_unmatched=unmatched,coverage_count=matched_count,coverage_percent=round(100*matched_count/count,2) if count else 0,product_selections=selections,checkout_total_known=money(known),unknown_cost_items=unknown,basket_total=money(known) if complete else None,complete=complete,latency_ms=basket.latency_ms)
