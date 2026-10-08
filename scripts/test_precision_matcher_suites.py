#!/usr/bin/env python3
import unittest,re,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
loader=unittest.TestLoader();suite=loader.discover(str(ROOT/'Model/tests'))
def flatten(s):
 for test in s:
  if isinstance(test,unittest.TestSuite):yield from flatten(test)
  else:yield test
cases=list(flatten(suite));patterns={'ontology':r'^test_product_ontology\.','compatibility':r'^test_product_compatibility\.','retrieval':r'^test_product_retrieval\.','cheese':r'cheese|parmesan|pecorino|mozzarella|neufchatel|feta|ricotta|cheddar','meat_cut':r'meat|cut|species|chicken|beef|pork|bacon|ground|ham','prepared_food':r'prepared|semantic_head|derivative|component|nonfood|pastry|grocery','nonfood':r'nonfood|food_domain','tomato':r'tomato|salsa|ketchup','historical_regressions':r'regression|test_real_recipe_regressions\.'};counts={}
for group,pattern in patterns.items():
 chosen=[c for c in cases if re.search(pattern,c.id())];assert chosen
 with (ROOT/('data/matcher_precision_hardening/'+group+'_tests.log')).open('w') as f:r=unittest.TextTestRunner(stream=f,verbosity=1).run(unittest.TestSuite(chosen))
 counts[group]={'tests':r.testsRun,'passed':r.wasSuccessful(),'failures':len(r.failures),'errors':len(r.errors)}
(ROOT/'data/matcher_precision_hardening/separate_test_results.json').write_text(json.dumps(counts,indent=2)+'\n');print(json.dumps(counts,indent=2));assert all(r['passed'] for r in counts.values())
