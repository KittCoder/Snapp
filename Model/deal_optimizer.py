"""Constrained economics over already structurally eligible matcher candidates.

Scores reuse the identity matcher's normalized evidence; bands are policy,
not claims of human calibration. No price can cross a quality band.
"""
import math


def quality_tier(score):
    if not math.isfinite(score):
        return None
    return 'A' if score >= .97 else 'B' if score >= .93 else 'C' if score >= .88 else None


class DealOptimizer:
    def select(self, evaluations, top1_id, mode='balanced'):
        safe = [e for e in evaluations if not e.exclusion_reasons]
        if not safe:
            return None, 'no candidate clears structural and quality requirements'
        best = min(({'A': 0, 'B': 1, 'C': 2, 'S': 3}[e.quality_tier],
                    {'EXACT': 0, 'EQUIVALENT': 1, 'SUBSTITUTE': 2}[e.match_type]) for e in safe)
        pool = [e for e in safe if ({'A': 0, 'B': 1, 'C': 2, 'S': 3}[e.quality_tier],
                    {'EXACT': 0, 'EQUIVALENT': 1, 'SUBSTITUTE': 2}[e.match_type]) == best]
        top = next((e for e in pool if e.product_id == top1_id), None)
        # Uncertain economics do not invalidate identity or justify a price switch.
        priced = [e for e in pool if e.deal_confidence == 'high']
        if not priced:
            chosen = top or max(pool, key=lambda e: e.match_score)
            return chosen, 'highest-quality match retained: quantity or price comparison is uncertain'
        pool = priced
        cheapest = min(e.effective_cost for e in pool)
        # Waste only resolves small (<= five cents) checkout differences.
        close = [e for e in pool if e.effective_cost <= cheapest + .05]
        chosen = min(close, key=lambda e: (e.waste_ratio if e.waste_ratio is not None else 1,
                                          e.effective_cost, -e.match_score, e.product_id))
        savings = (top.effective_cost - chosen.effective_cost) if top and top.effective_cost is not None else 0
        reason = f'Selected Tier {chosen.quality_tier}; lowers checkout cost by ${savings:.2f} within comparable match quality' if savings > 0 else f'Selected Tier {chosen.quality_tier} by recipe checkout cost and waste'
        return chosen, reason
