"""Additive shopping presentation; never changes purchase selection."""
import math


def shopping_deal_fields(purchase):
    selected = purchase.selected if purchase else None
    if selected is None:
        return {}
    def reliable(candidate):
        return (not candidate.exclusion_reasons and candidate.deal_confidence == 'high'
                and candidate.effective_cost is not None
                and math.isfinite(candidate.effective_cost) and candidate.effective_cost >= 0)
    comparable = [c for c in purchase.alternatives
                  if c.quality_tier == selected.quality_tier and c.match_type == selected.match_type
                  and reliable(c)]
    compared = reliable(selected) and bool(comparable)
    closest = max(comparable, key=lambda c: c.match_score) if comparable else selected
    savings = round(closest.effective_cost - selected.effective_cost, 2) if compared else None
    best = compared and selected.effective_cost <= min(c.effective_cost for c in comparable) + .05
    return {
        'match_score': selected.match_score, 'match_type': selected.match_type,
        'quality_tier': selected.quality_tier, 'effective_cost': selected.effective_cost,
        'packages_needed': selected.packages_needed if not selected.package.sold_by_weight and not selected.package.variable_weight else None,
        'package_price': selected.package_price, 'package_quantity': selected.package.package_quantity,
        'package_unit': selected.package.package_unit, 'deal_confidence': selected.deal_confidence,
        'best_deal': bool(best), 'comparable_candidate_count': 1 + len(comparable) if reliable(selected) else 0,
        'savings_vs_closest_match': savings if savings is not None and savings >= .50 else None,
        'deal_reason': 'closest_quality_lowest_cost' if best else 'best_available_safe_match',
    }
