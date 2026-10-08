#!/usr/bin/env python3
"""Analyze manual labels only. Incomplete review requires explicit --partial."""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path
from matcher_review_store import ReviewStore

ROOT = Path(__file__).resolve().parents[1]
GOOD = {'CORRECT', 'ACCEPTABLE_SUBSTITUTE'}


def rate(numerator, denominator):
    return numerator / denominator if denominator else None


def accepted_summary(rows):
    labeled = [r for r in rows if r['review_label']]
    counts = collections.Counter(r['review_label'] for r in labeled)
    return {'total': len(rows), 'reviewed': len(labeled), 'correct': counts['CORRECT'],
            'acceptable_substitute': counts['ACCEPTABLE_SUBSTITUTE'], 'wrong': counts['WRONG'],
            'ambiguous': counts['AMBIGUOUS'], 'nonstandard_should_have_matched': counts['SHOULD_HAVE_MATCHED'],
            'precision': rate(sum(counts[k] for k in GOOD), len(labeled)),
            'false_positive_rate': rate(counts['WRONG'], len(labeled))}


def rejected_summary(rows):
    labeled = [r for r in rows if r['review_label']]
    counts = collections.Counter(r['review_label'] for r in labeled)
    return {'total': len(rows), 'reviewed': len(labeled), 'correct_rejection': counts['CORRECT'],
            'should_have_matched': counts['SHOULD_HAVE_MATCHED'], 'ambiguous': counts['AMBIGUOUS'],
            'nonstandard_wrong': counts['WRONG'], 'nonstandard_acceptable_substitute': counts['ACCEPTABLE_SUBSTITUTE'],
            'false_negative_rate': rate(counts['SHOULD_HAVE_MATCHED'], len(labeled)),
            'rate_definition': 'SHOULD_HAVE_MATCHED / reviewed rejected cases (rejection miss rate); not population FN/(TP+FN)'}


def flag_count(rows, field):
    if not rows or any(r[field] not in ('yes', 'no') for r in rows):
        return None
    return sum(r[field] == 'yes' for r in rows)


def structural_accuracy(rows):
    if not rows or any(r['structurally_correct'] not in ('yes', 'no') for r in rows):
        return None
    return rate(sum(r['structurally_correct'] == 'yes' and r['review_label'] in GOOD for r in rows), len(rows))


def zero_medium(directory):
    selected = []; alternatives = []; rejected = 0; confidence_counts = collections.Counter()
    for line in (directory / 'population.jsonl').open():
        row = json.loads(line); confidence_counts[row['confidence']] += 1
        if row['selected_match']:
            selected.append(row['selected_match'])
        else:
            rejected += 1
        alternatives.extend(row['compatible_alternatives'])
    return {'population': sum(confidence_counts.values()), 'confidence_counts': dict(confidence_counts),
            'selected_score_min': min((c['final_score'] for c in selected), default=None),
            'selected_score_max': max((c['final_score'] for c in selected), default=None),
            'compatible_alternatives': len(alternatives),
            'alternative_score_min': min((c['final_score'] for c in alternatives), default=None),
            'medium_compatible_alternatives': sum(c['confidence'] == 'medium' for c in alternatives),
            'explanation': [
                'identity_confidence explicitly returns Medium below 0.90 for a structurally allowed non-substitute candidate; it does not skip Medium.',
                'High starts at 0.90; Exact additionally requires lexical exactness, exact match type and score >= 0.94. Minimum selection score defaults to 0.45, leaving a real Medium interval.',
                'Compatible candidates receive 0.88 structural score before up to 0.07 lexical and 0.05 semantic support. An unrequested dairy variant can subtract 0.04. Medium is mathematically possible but no stored selected or returned compatible alternative scored below 0.90.',
                'The corpus therefore clusters above High after strict compatibility gates or abstains. Selection takes the highest-scoring compatible candidate; there is no later confidence-based gate eliminating Medium.',
                'This explains the observed outputs, not all unreturned inventory candidates or future queries. Frozen outputs do not expose every pre-retrieval exclusion. Human review is still needed to judge calibration; thresholds remain unchanged.'
            ], 'code_references': ['Model/product_compatibility.py:2231 rank_identity_candidate', 'Model/product_compatibility.py:2273 identity_confidence', 'Model/product_compatibility.py:2440 selection', 'Model/product_compatibility.py:73 minimum_selection_score']}


def analyze(rows, manifest, partial=False):
    missing = [r['case_id'] for r in rows if not r['review_label']]
    if missing and not partial:
        raise ValueError(f'Refusing final analysis: {len(missing)} of {len(rows)} required cases remain unlabeled. Use --partial for provisional results.')
    accepted = [r for r in rows if r['current_matcher_decision'] == 'accepted']
    rejected = [r for r in rows if r['current_matcher_decision'] == 'rejected']
    reviewed_accepted = [r for r in accepted if r['review_label']]
    hard = {}
    for group in sorted({r['sample_group'] for r in rows if r['sample_group'].startswith('hard: ')}):
        group_rows = [r for r in rows if r['sample_group'] == group]
        a = [r for r in group_rows if r['current_matcher_decision'] == 'accepted']
        n = [r for r in group_rows if r['current_matcher_decision'] == 'rejected']
        hard[group.removeprefix('hard: ') if hasattr(str, 'removeprefix') else group[6:]] = {'total': len(group_rows), 'accepted': accepted_summary(a), 'rejected': rejected_summary(n), 'structural_accuracy_accepted': structural_accuracy([r for r in a if r['review_label']])}
    source_cases = {r['case_id']: r for r in manifest['cases']}
    from human_qa_ingredient_matcher import category
    cheese = [r for r in reviewed_accepted if 'cheese' in category(source_cases[r['case_id']])]
    meat = [r for r in reviewed_accepted if 'meat/cuts' in category(source_cases[r['case_id']])]
    errors = [r for r in rows if r['review_label'] in ('WRONG', 'SHOULD_HAVE_MATCHED')]
    result = {'mode': 'PARTIAL — provisional, never freeze' if partial else 'COMPLETE EXPORTED SAMPLE',
              'total': len(rows), 'reviewed': len(rows)-len(missing), 'remaining': len(missing),
              'exact_high': accepted_summary([r for r in rows if r['sample_group'] == 'Exact/High']),
              'all_accepted_exact_high': accepted_summary([r for r in accepted if r['confidence'] in ('exact', 'high')]),
              'medium': accepted_summary([r for r in accepted if r['confidence'] == 'medium']),
              'rejected': rejected_summary([r for r in rows if r['sample_group'] == 'Rejected']),
              'all_rejected': rejected_summary(rejected), 'hard_categories': hard,
              'wrong_family_count': flag_count(reviewed_accepted, 'wrong_family'),
              'prepared_food_false_positives': flag_count(reviewed_accepted, 'prepared_food_false_positive'),
              'cheese_accuracy': structural_accuracy(cheese), 'meat_cut_accuracy': structural_accuracy(meat),
              'false_positive_rate': accepted_summary(accepted)['false_positive_rate'],
              'false_negative_rate': rejected_summary(rejected)['false_negative_rate'],
              'false_negative_rate_definition': 'Conditional rejection miss rate; population recall/FNR is not identifiable from these stratified samples.',
              'ambiguous_policy': 'Included in reviewed denominators; never counted correct.',
              'sample_counts': manifest['sample_counts'],
              'material_human_errors': [{'case_id': r['case_id'], 'query': r['ingredient_query'], 'product': r['selected_product'], 'decision': r['current_matcher_decision'], 'label': r['review_label'], 'cause': r['failure_cause'], 'notes': r['review_notes'], 'handling': 'No matcher change by this tool; human-observed general errors require investigation, regression test and fresh holdout.'} for r in errors],
              'accepted_wrong_missing_investigation': [r['case_id'] for r in accepted if r['review_label']=='WRONG' and (not r['failure_cause'] or not r['review_notes'])],
              'nonstandard_labels': [r['case_id'] for r in rows if (r['current_matcher_decision']=='accepted' and r['review_label']=='SHOULD_HAVE_MATCHED') or (r['current_matcher_decision']=='rejected' and r['review_label'] in ('WRONG','ACCEPTABLE_SUBSTITUTE'))],
              'freeze_recommendation': 'DO_NOT_FREEZE_MATCHER',
              'freeze_reason': 'This analysis is not a freeze certification; incomplete, unassessed or nonstandard reviews require adjudication. Follow the applicable holdout coverage criteria.'}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=ROOT/'data/matcher_validation')
    parser.add_argument('--partial', action='store_true')
    args = parser.parse_args()
    store = ReviewStore(args.directory)
    manifest = json.loads((args.directory/'sample.json').read_text())
    rows = store.snapshot()['cases']
    # Validate the frozen source and sample membership, without importing matcher code.
    from human_qa_ingredient_matcher import immutable_hash
    if set(manifest['immutable_review_hashes']) != {r['case_id'] for r in rows} or any(immutable_hash(r) != manifest['immutable_review_hashes'].get(r['case_id']) for r in rows):
        parser.exit(2, 'Frozen review columns or sample membership changed; refusing analysis.\n')
    try:
        result = analyze(rows, manifest, args.partial)
    except ValueError as error:
        parser.exit(2, str(error)+'\n')
    result['zero_medium_analysis'] = zero_medium(args.directory)
    result['no_match_rate'] = manifest['no_match_rate']; result['latency'] = manifest['latency']
    result['source_fingerprints_current'] = all(hashlib_file(ROOT/p)==h for p,h in manifest['source_hashes'].items())
    prefix = 'human_review_partial' if args.partial else 'human_review_analysis'
    (args.directory/(prefix+'.json')).write_text(json.dumps(result, indent=2)+'\n')
    (args.directory/(prefix+'.md')).write_text('# Human review analysis\n\n**'+result['mode']+'**\n\nDO_NOT_FREEZE_MATCHER. Null means not assessed, not zero. See zero_medium_analysis for score evidence and unchanged confidence logic.\n\n```json\n'+json.dumps(result, indent=2)+'\n```\n')
    print(f"{result['reviewed']}/{result['total']} reviewed. {result['freeze_recommendation']}. Saved {prefix}.json and .md")


def hashlib_file(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


if __name__ == '__main__':
    main()
