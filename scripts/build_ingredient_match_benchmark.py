#!/usr/bin/env python3
"""Freeze a rule-labelled, real-inventory benchmark BEFORE matcher tuning.

Labels are conservative independent name rules, NOT matcher predictions or human
QA. Keep ambiguous records unscored; these proxy metrics cannot justify freeze.
"""
import argparse, hashlib, json, random, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
# Independent review tags. Do not import product ontology or compatibility.
TAGS = {
 'cream_cheese': r'cream cheese', 'cottage_cheese': r'cottage cheese',
 'cheddar': r'cheddar', 'mozzarella': r'mozzarella', 'parmesan': r'parmesan|parmigiano',
 'pecorino': r'pecorino|romano', 'feta': r'feta', 'goat_cheese': r'goat cheese|chevre',
 'ricotta': r'ricotta', 'swiss': r'swiss cheese', 'provolone': r'provolone',
 'monterey_jack': r'monterey jack', 'pepper_jack': r'pepper jack',
 'blue_cheese': r'blue cheese|gorgonzola|roquefort', 'brie': r'brie', 'gouda': r'gouda',
 'ground_beef': r'ground beef|hamburger meat', 'beef_ribeye': r'rib ?eye',
 'beef_sirloin': r'sirloin', 'beef_flank': r'flank', 'beef_skirt': r'skirt',
 'beef_chuck': r'chuck', 'beef_strip': r'new york strip|strip steak',
 'beef_tenderloin': r'beef tenderloin|filet mignon',
 'chicken_breast': r'chicken breast', 'chicken_thigh': r'chicken thigh',
 'chicken_wing': r'chicken wing', 'chicken_drumstick': r'chicken drumstick',
 'ground_chicken': r'ground chicken', 'ground_turkey': r'ground turkey',
 'pork_shoulder': r'pork shoulder|pork butt', 'pork_tenderloin': r'pork tenderloin',
 'pork_loin': r'pork loin', 'pork_chop': r'pork chop', 'ground_pork': r'ground pork',
 'salmon': r'salmon', 'cod': r'\bcod\b', 'tilapia': r'tilapia', 'shrimp': r'shrimp',
 'chicken_broth': r'(?:chicken|chkn).*(?:broth|stock)|(?:broth|stock).*chicken',
 'beef_broth': r'beef.*(?:broth|stock)|(?:broth|stock).*beef',
 'vegetable_broth': r'vegetable.*(?:broth|stock)|(?:broth|stock).*vegetable',
 'tomato_paste': r'tomato paste', 'tomato_sauce': r'tomato sauce',
 'diced_tomato': r'diced tomatoes|tomatoes diced', 'crushed_tomato': r'crushed tomatoes|tomatoes crushed',
 'condensed_milk': r'condensed.*milk', 'evaporated_milk': r'evaporated.*milk',
 'almond_milk': r'almond ?milk', 'oat_milk': r'oat ?milk',
 'milk': r'\bmilk\b', 'heavy_cream': r'heavy.*cream|heavy whipping cream',
 'half_and_half': r'half[- ](?:and|&)[- ]half', 'butter': r'\bbutter\b',
 'yogurt': r'yogurt|yoghurt', 'peanut_butter': r'peanut butter', 'peanuts': r'peanuts',
 'flour': r'all[- ]purpose flour|\bflour\b', 'corn': r'\bcorn\b',
 'spinach': r'spinach', 'basil': r'basil', 'onion': r'onions?',
 'lemon': r'lemons?', 'lime': r'limes?', 'garlic': r'garlic', 'eggs': r'\beggs?\b',
}
PREPARED = re.compile(r'\b(crackers?|cookies?|soup|salad|pizza|entree|sandwich|nuggets?|breaded|'
 r'icing|frosting|cereal|pancake|waffles?|muffins?|cake|pie|simmer|franks?|dogs?|sausage|'
 r'cat|dog|pet|dinner|ready[- ]to[- ]eat|cooked|rotisserie|deli|chocolate|cocoa)\b',re.I)
AMBIGUOUS = re.compile(r'all varieties|select varieties|\bor\b|style|blend|filled|seasoned|stuffed|smoked',re.I)
FAMILIES = {**{k:'cheese' for k in list(TAGS)[:16]},
 **{k:'meat' for k in list(TAGS)[16:34]}, **{k:'fish' for k in ['salmon','cod','tilapia']},'shrimp':'shellfish'}

def tag(text, product=False):
 text=text.lower().replace('’',"'")
 if product and AMBIGUOUS.search(text): return None
 if PREPARED.search(text): return 'prepared'
 found=[k for k,p in TAGS.items() if re.search(p,text,re.I)]
 # Specific identities dominate generic tokens, independent of production code.
 for generic,specifics in [('milk',['condensed_milk','evaporated_milk','almond_milk','oat_milk']),
                          ('butter',['peanut_butter']),('flour',[])]:
  if any(x in found for x in specifics) and generic in found:found.remove(generic)
 if len(found)!=1:return None
 return found[0]

def attributes(text):
 out={};t=text.lower()
 for key,rules in {
  'salt': [('unsalted',r'unsalted|no salt added|salt free'),('low',r'low sodium|less sodium|reduced sodium'),('salted',r'(?<!un)salted')],
  'flavor': [('plain',r'plain|unflavored'),('flavored',r'vanilla|strawberry|banana|blueberry|chocolate|peach')],
  'fat': [('skim',r'skim|fat[- ]free|nonfat'),('whole',r'whole milk'),('2%',r'2\s*%|two percent'),('1%',r'1\s*%|one percent')],
  'state':[('frozen',r'frozen'),('dried',r'dried|\bdry\b'),('canned',r'canned'),('fresh',r'fresh')],
  'bone':[('boneless',r'boneless'),('bone_in',r'bone[- ]in')],
  'skin':[('skinless',r'skinless'),('skin_on',r'skin[- ]on')],
  'greek':[('greek',r'greek')],
 }.items():
  values=[value for value,pattern in rules if re.search(pattern,t)]
  if len(values)==1:out[key]=values[0]
 return out

def compatible(query, product):
 if query['identity']!=product['identity']:return False
 for key,value in query['attributes'].items():
  other=product['attributes'].get(key)
  if other!=value:return False
 return True

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'Model/evaluation/ingredient_inventory_benchmark.json')
 args=parser.parse_args();fp=ROOT/'Model/morton_williams_product_features.json'
 payload=json.loads(fp.read_text());fs=payload['features']
 products=[]
 for f in fs:
  if not f.get('eligible_for_retrieval'):continue
  identity=tag(f['original_product_name'],True)
  if identity: products.append({'id':f['product_id'],'name':f['original_product_name'],'identity':identity,
    'family':FAMILIES.get(identity,identity),'attributes':attributes(f['original_product_name'])})
 ingredient_rows=json.loads((ROOT/'Model/all_recipes.json').read_text())['recipes']
 queries=[];seen=set()
 for r in ingredient_rows:
  for i in r.get('ingredients',[]):
   text=i.get('raw') or i.get('name') or ''
   identity=tag(i.get('name') or text)
   if identity and identity!='prepared' and text not in seen:
    seen.add(text);queries.append({'text':text,'identity':identity,'family':FAMILIES.get(identity,identity),'attributes':attributes(text),'source_recipe_id':r['id']})
 rng=random.Random(20261006);rng.shuffle(queries);queries=queries[:2500]
 for q in queries:q['acceptable_ids']=[p['id'] for p in products if compatible(q,p)]
 pairs=[]
 for q in queries:
  same=[p for p in products if p['family']==q['family']]
  confusing=[p for p in products if p['identity']=='prepared' and any(w in p['name'].lower() for w in q['identity'].split('_'))]
  pool=same+confusing
  rng.shuffle(pool)
  positive=[p for p in pool if p['id'] in q['acceptable_ids']][:3]
  negative=[p for p in pool if p['id'] not in q['acceptable_ids']][:5]
  for p in positive+negative:pairs.append({'ingredient':q['text'],'product_id':p['id'],'product_name':p['name'],
    'expected':p['id'] in q['acceptable_ids'],'group':q['family'],'kind':'true_match' if p['id'] in q['acceptable_ids'] else 'prepared_negative' if p['identity']=='prepared' else 'hard_negative'})
 report={'label_provenance':'Independent conservative name-rule proxy labels frozen before tuning. NOT human gold; ambiguous products unlabelled; cannot justify freeze.',
  'inventory_sha256':hashlib.sha256(fp.read_bytes()).hexdigest(),'inventory_metadata':payload['metadata'],
  'seed':20261006,'queries':queries,'products':products,'pairs':pairs}
 args.output.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'queries':len(queries),'annotated_products':len(products),'pairs':len(pairs),'cheese_pairs':sum(p['group']=='cheese' for p in pairs),'meat_pairs':sum(p['group']=='meat' for p in pairs)},indent=2))
if __name__=='__main__':main()
