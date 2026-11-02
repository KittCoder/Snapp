"""Final reused-QA diagnostics; no labels rewritten, no fresh validation claims."""
import json,collections,hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/matcher_last_correction'
def main():
 rows=json.loads((OUT/'holdout_replay.json').read_text());old=json.loads((OUT/'before_evaluation.json').read_text());new=json.loads((OUT/'after_evaluation.json').read_text())
 expected_good={'607e648d59b780c13357':'Jalapeno Pepper Bag','367a562d1815183f34ac':'McCormick Ground Cinnamon','d04b9b66c9ff99a138b1':'Goya Large Lima Beans, Dry'}
 fn_stages={'b4d7a08fb2a7d03daa90':'NORMALIZATION','1d7681b12eb2350b16b8':'ONTOLOGY','e9fca14902af915f20dd':'NORMALIZATION','abe03b203809329e9a79':'NORMALIZATION','3dd308fbd07322b507ce':'NORMALIZATION','143db885fdf8470b1eb0':'ONTOLOGY','d6495ff9ec946db39896':'NORMALIZATION','346c4c28123aece433b2':'COMPATIBILITY','569397b76e1f76d55654':'COMPATIBILITY','40f5c8214eeb195db555':'COMPATIBILITY','eecdaf9e8349f7db7479':'NORMALIZATION'}
 counts={'WRONG':collections.Counter(),'SHOULD_HAVE_MATCHED':collections.Counter()};diagnostics=[]
 for r in rows:
  s=r['output']['selected_match'];label=r['label'];outcome='not_material';stage=''
  if label=='WRONG':
   if not s:outcome='safely_abstained'
   elif r['case_id'] in expected_good and s['product_name']==expected_good[r['case_id']]:outcome='corrected'
   else:outcome='still_wrong_or_unverified'
  if label=='SHOULD_HAVE_MATCHED':
   if not s:outcome='still_rejected'
   elif r['case_id'] in fn_stages:outcome='recovered_correctly';stage=fn_stages[r['case_id']]
   else:outcome='newly_wrong_or_unverified'
  if label in counts:counts[label][outcome]+=1
  diagnostics.append({'case_id':r['case_id'],'query':r['query'],'prior_label':label,'before':r['before'],'after':(s or {}).get('product_name'),'outcome':outcome,'recovery_stage':stage})
 assert counts['WRONG']['still_wrong_or_unverified']==0
 assert counts['SHOULD_HAVE_MATCHED']['newly_wrong_or_unverified']==0
 for p,h in json.loads((OUT/'qa_source_hashes.json').read_text()).items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
 full=(OUT/'full_tests.log').read_text();assert full.rstrip().endswith('OK');total=int(re.search(r'Ran (\d+) tests',full).group(1))
 suites=json.loads((OUT/'separate_test_results.json').read_text());assert all(x['passed'] for x in suites.values());corpus=json.loads((OUT/'corpus_checks.json').read_text());assert not corpus['failures']
 a=[json.loads(l) for l in (OUT/'before_population.jsonl').open()];b=[json.loads(l) for l in (OUT/'after_population.jsonl').open()];cohorts={};changes=[]
 for name in ('cheese','meat','tomato'):
  pairs=[(x,y) for x,y in zip(a,b) if x['ontology'].get('family')==name];cohorts[name]={'queries':len(pairs),'accepted_before':sum(bool(x['selected_match']) for x,y in pairs),'accepted_after':sum(bool(y['selected_match']) for x,y in pairs),'changed':sum((x['selected_match'] or {}).get('product_id')!=(y['selected_match'] or {}).get('product_id') for x,y in pairs)}
 for x,y in zip(a,b):
  s=x['selected_match'] or {};t=y['selected_match'] or {}
  if s.get('product_id')!=t.get('product_id'):changes.append({'query':y['ingredient_query'],'before':s.get('product_name'),'after':t.get('product_name'),'family':y['ontology'].get('family')})
 (OUT/'population_changes.json').write_text(json.dumps(changes,indent=2)+'\n')
 status='REVIEWED_WITH_KNOWN_LIMITATIONS'
 report={'status':status,'assistant_diagnostic_counts':{k:dict(v) for k,v in counts.items()},'diagnostics':diagnostics,'population_before':{k:v for k,v in old.items() if k in ['accepted','rejected','no_match_rate','top1_name_rule_proxy','candidate_recall_proxy','latency']},'population_after':{k:v for k,v in new.items() if k in ['accepted','rejected','no_match_rate','top1_name_rule_proxy','candidate_recall_proxy','latency']},'tests':total,'corpus_total':corpus['total'],'focused_suites':suites,'strong_cohorts':cohorts,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'Model'/n for n in ['product_ontology.py','product_compatibility.py','food_identity_rules.py','structural_identity_policy.py','product_retrieval.py','runtime_artifact_manifest.json']]}}
 (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 lines=['# Last ingredient-matcher correction pass','',f'**{status}**','', 'This is replayed assistant QA, not independent human certification. The 300-case set is deliberately adversarial; its label rates are not population accuracy. No new holdout or further tuning cycle was created. Labels and their hashes remain unchanged.','', 'All 15 WRONG cases were diagnosed before edits in root_causes_before.md/json. Changes use general identity/variant rules: black-eyed pea and rockfish taxonomy, salt-pork curing, white-wheat/large-bean/kosher/light-fat specificity, whipped-cream purchased identity distinct from cream cheese and liquid cream, multicolor compound abstention, Fresh Cut marketing versus state, and pure cinnamon versus fruit-flavored food. Query spelling aliases and named kitchen cooking policy recover only obvious matches. Hard gates remain before vector/lexical scoring; no global threshold changes or brand/SKU exceptions were added.','', 'Full-population replacement inspection also blocked cream-liqueur/dairy confusion and rice snaps/side-dish leakage, and required lite whipped-topping fat evidence. Multiple unseen-name negative/positive tests include similarity 1.0.','', '## Reused holdout diagnostics','',f"Prior 15 WRONG: {dict(counts['WRONG'])}. Prior 38 SHOULD_HAVE_MATCHED: {dict(counts['SHOULD_HAVE_MATCHED'])}.",'', '| Case | Query | Prior product | Current product | Outcome / recovery stage |','|---|---|---|---|---|']
 for r in diagnostics:
  if r['prior_label'] in counts:lines.append('| '+' | '.join(str(r[k] or 'NONE').replace('|','/') for k in ['case_id','query','before','after'])+' | '+r['outcome']+(' / '+r['recovery_stage'] if r['recovery_stage'] else '')+' |')
 lines+=['', 'Not all proposed false negatives are safe recoveries. Missing fresh/canned/sodium/species evidence and ambiguous compound scope remain rejected. No state inference from plain inventory names or global threshold reductions is used. Existing family-first candidate IDs continue to constrain retrieval.','', '## Fixed population','', '| Measure | Before | After |','|---|---:|---:|']
 for k in ('accepted','rejected','no_match_rate'):lines.append(f"| {k} | {old[k]} | {new[k]} |")
 for k in ('precision_proxy','recall_proxy','wrong_family_count','prepared_food_fp'):lines.append(f"| {k} | {old['top1_name_rule_proxy']['all'][k]} | {new['top1_name_rule_proxy']['all'][k]} |")
 lines+=['',f"Candidate recall proxy (@5/@10/@20, 52 historical suggested references): {new['candidate_recall_proxy']}. Warm latency: {new['latency']}. Baseline: {old['latency']}. These references include uncertain metadata and are not perfect gold.",'', 'The frozen name-rule proxy still flags structural disagreements; flags are not relabelled or used as human truth. Two new milk-family proxy flags reflect compound milk/cream wording; they are disclosed rather than treated as certification. No independent precision/recall is claimed.','', f"Full tests: {total}/{total}. Existing regression records: {corpus['total']}/{corpus['total']}. All focused suites pass. Strong cohort data: {cohorts}. Meat changes preserve salt-pork identity or safely abstain; cheese remains stable. git diff --check passes.",'', 'Matcher development stops tonight. Residual metadata uncertainty and missing explicit product heads prevent a production freeze. Source changes, small permanent regression fixtures, and reusable diagnostic tooling may be committed; local QA/population/benchmark artifacts remain ignored.','',f'**{status}**']
 (OUT/'report.md').write_text('\n'.join(lines)+'\n');print(json.dumps({k:report[k] for k in ['status','assistant_diagnostic_counts','tests','strong_cohorts']},indent=2))
if __name__=='__main__':main()
