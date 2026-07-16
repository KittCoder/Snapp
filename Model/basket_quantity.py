from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ingredient_normalization import normalize_package_text, normalize_text, normalize_unit, parse_ingredient, parse_number
from product_compatibility import (
    LOW,
    NO_SAFE_MATCH,
    SUBSTITUTION_ONLY,
    ProductMatchService,
    RankedCandidate,
    profile_from_query,
)


UNKNOWN = "UNKNOWN"

MASS_TO_GRAM = {
    "gram": 1.0,
    "kilogram": 1000.0,
    "ounce": 28.3495,
    "pound": 453.592,
}

VOLUME_TO_MILLILITER = {
    "teaspoon": 4.92892,
    "tablespoon": 14.7868,
    "cup": 236.588,
    "fluid ounce": 29.5735,
    "pint": 473.176,
    "quart": 946.353,
    "gallon": 3785.41,
    "milliliter": 1.0,
    "liter": 1000.0,
}

COUNT_UNITS = {
    "count",
    "each",
    "egg",
    "onion",
    "carrot",
    "potato",
    "cabbage",
    "pepper",
    "tomato",
    "lemon",
    "avocado",
    "package",
    "can",
    "bunch",
    "clove",
    "stick",
    "head",
    "stalk",
    "pack",
    "jar",
}

COUNT_ALIASES = {
    "eggs": "egg",
    "egg": "egg",
    "onions": "onion",
    "onion": "onion",
    "carrots": "carrot",
    "carrot": "carrot",
    "potatoes": "potato",
    "potato": "potato",
    "cabbages": "cabbage",
    "cabbage": "cabbage",
    "peppers": "pepper",
    "pepper": "pepper",
    "tomatoes": "tomato",
    "tomato": "tomato",
    "lemons": "lemon",
    "lemon": "lemon",
    "avocados": "avocado",
    "avocado": "avocado",
    "packages": "package",
    "package": "package",
    "pkg": "package",
    "cans": "can",
    "can": "can",
    "bunches": "bunch",
    "bunch": "bunch",
    "cloves": "clove",
    "clove": "clove",
    "sticks": "stick",
    "stick": "stick",
    "heads": "head",
    "head": "head",
    "stalks": "stalk",
    "stalk": "stalk",
    "dozen": "count",
    "ct": "count",
    "count": "count",
    "each": "each",
    "ea": "each",
    "pack": "pack",
    "packs": "pack",
    "jar": "jar",
    "jars": "jar",
}

DENSITY_G_PER_ML = {
    "milk": 1.03,
    "water": 1.0,
    "heavy cream": 0.99,
    "olive oil": 0.91,
    "vegetable oil": 0.92,
    "butter": 0.96,
    "broth": 1.0,
    "chicken broth": 1.0,
    "vegetable broth": 1.0,
    "beef broth": 1.0,
    "stock": 1.0,
    "chicken stock": 1.0,
    "vegetable stock": 1.0,
    "beef stock": 1.0,
}


@dataclass
class Quantity:
    quantity: float | None
    unit: str | None
    dimension: str | None = None
    base_quantity: float | None = None
    base_unit: str | None = None
    status: str = "known"
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PackageInfo:
    package_quantity: float | None
    package_unit: str | None
    package_count: float = 1.0
    base_quantity: float | None = None
    base_unit: str | None = None
    sold_by_weight: bool = False
    variable_weight: bool = False
    source: str = "unknown"
    confidence: str = "unknown"
    source_text: str | None = None
    eligible_for_optimization: bool = True
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PriceInfo:
    checkout_price: float | None
    unit_price: float | None
    price_unit: str | None = None
    deal_quantity: int = 1
    deal_price: float | None = None
    bogo: bool = False
    source: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QuantityCoverage:
    amount_required: Quantity
    package: PackageInfo
    packages_required: float | None
    coverage: float | None
    used: Quantity
    leftover: Quantity
    leftover_percentage: float | None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CostBreakdown:
    checkout_cost: float | None
    effective_ingredient_cost: float | None
    cost_per_base_unit: float | None
    leftover_value: float | None
    waste_value: float | None
    pricing: PriceInfo
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PurchaseEvaluation:
    product_id: str
    product_name: str
    required_quantity: Quantity
    package: PackageInfo
    coverage: QuantityCoverage
    cost: CostBreakdown
    matcher_confidence: str
    matcher_score: float
    compatibility_confidence: str
    compatibility_conflicts: list[dict[str, str]]
    optimization_mode: str
    optimization_score: tuple[Any, ...]
    exclusion_reasons: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)
    source_quality_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["optimization_score"] = list(self.optimization_score)
        return payload


@dataclass
class OptimizedPurchase:
    selected: PurchaseEvaluation | None
    alternatives: list[PurchaseEvaluation]
    rejected: list[PurchaseEvaluation]
    optimization_mode: str
    changed_from_matcher_top1: bool
    explanation: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MatchedIngredient:
    recipe_id: str
    raw_ingredient: str
    normalized_ingredient: str
    product_id: str | None
    product_name: str | None
    match_confidence: str
    required_quantity: Quantity
    coverage: QuantityCoverage | None
    cost: CostBreakdown | None
    optimized_purchase: OptimizedPurchase | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BasketItem:
    product_id: str
    product_name: str
    ingredients: list[str]
    total_required: Quantity
    package: PackageInfo
    packages_required: float | None
    checkout_cost: float | None
    effective_ingredient_cost: float | None
    leftover: Quantity
    leftover_value: float | None
    optimized_purchase: OptimizedPurchase | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecipeBasket:
    recipes: list[dict[str, Any]]
    matched_ingredients: list[MatchedIngredient]
    shopping_basket: list[BasketItem]
    checkout_cost: float | None
    effective_ingredient_cost: float | None
    warnings: list[str]
    latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def unit_dimension(unit: str | None) -> str | None:
    unit = normalize_count_unit(unit) or normalize_unit(unit)
    if unit in MASS_TO_GRAM:
        return "mass"
    if unit in VOLUME_TO_MILLILITER:
        return "volume"
    if unit in COUNT_UNITS:
        return "count"
    return None


def normalize_count_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    normalized = normalize_text(unit)
    return COUNT_ALIASES.get(normalized)


def canonical_quantity(quantity: float | None, unit: str | None, ingredient_key: str | None = None) -> Quantity:
    if quantity is None:
        return Quantity(None, unit, status=UNKNOWN, reason="missing quantity")
    normalized_unit = normalize_count_unit(unit) or normalize_unit(unit)
    if normalized_unit is None:
        return Quantity(quantity, None, status=UNKNOWN, reason="missing unit")
    if normalized_unit == "dozen":
        normalized_unit = "count"
        quantity *= 12
    dimension = unit_dimension(normalized_unit)
    if dimension == "mass":
        return Quantity(quantity, normalized_unit, dimension, round(quantity * MASS_TO_GRAM[normalized_unit], 3), "gram")
    if dimension == "volume":
        return Quantity(quantity, normalized_unit, dimension, round(quantity * VOLUME_TO_MILLILITER[normalized_unit], 3), "milliliter")
    if dimension == "count":
        if normalized_unit == "dozen":
            quantity *= 12
        return Quantity(quantity, normalized_unit, dimension, float(quantity), normalized_unit)
    return Quantity(quantity, normalized_unit, status=UNKNOWN, reason="unsupported unit")


def convert_quantity(quantity: Quantity, target_unit: str, ingredient_key: str | None = None) -> Quantity:
    target_unit = normalize_count_unit(target_unit) or normalize_unit(target_unit) or target_unit
    target_dimension = unit_dimension(target_unit)
    if quantity.status == UNKNOWN or quantity.base_quantity is None:
        return Quantity(None, target_unit, target_dimension, status=UNKNOWN, reason=quantity.reason or "unknown source quantity")
    if quantity.dimension == target_dimension:
        if target_dimension == "mass":
            return Quantity(round(quantity.base_quantity / MASS_TO_GRAM[target_unit], 4), target_unit, target_dimension, quantity.base_quantity, "gram")
        if target_dimension == "volume":
            return Quantity(round(quantity.base_quantity / VOLUME_TO_MILLILITER[target_unit], 4), target_unit, target_dimension, quantity.base_quantity, "milliliter")
        if target_dimension == "count" and (quantity.base_unit == target_unit or target_unit in {"count", "each"}):
            return Quantity(quantity.base_quantity, target_unit, target_dimension, quantity.base_quantity, target_unit)
        if target_dimension == "count":
            return Quantity(None, target_unit, target_dimension, status=UNKNOWN, reason="count unit identity differs")
    if quantity.dimension == "volume" and target_dimension == "mass":
        density = density_for_ingredient(ingredient_key)
        if density:
            grams = quantity.base_quantity * density
            return Quantity(round(grams / MASS_TO_GRAM[target_unit], 4), target_unit, target_dimension, round(grams, 3), "gram")
    if quantity.dimension == "mass" and target_dimension == "volume":
        density = density_for_ingredient(ingredient_key)
        if density:
            milliliters = quantity.base_quantity / density
            return Quantity(round(milliliters / VOLUME_TO_MILLILITER[target_unit], 4), target_unit, target_dimension, round(milliliters, 3), "milliliter")
    return Quantity(None, target_unit, target_dimension, status=UNKNOWN, reason="unsafe conversion")


def density_for_ingredient(ingredient_key: str | None) -> float | None:
    normalized = normalize_text(ingredient_key or "")
    if normalized in DENSITY_G_PER_ML:
        return DENSITY_G_PER_ML[normalized]
    for key, density in DENSITY_G_PER_ML.items():
        if key in normalized:
            return density
    return None


def currency_round(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _first_number(text: str) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?(?:\s+\d+/\d+|/\d+)?", text)
    return parse_number(match.group(0)) if match else None


def parse_package_info(feature: dict[str, Any] | None) -> PackageInfo:
    feature = feature or {}
    warnings: list[str] = list(feature.get("package_parse_warnings") or [])
    confidence = feature.get("package_parse_confidence") or "unknown"
    source_text = feature.get("raw_unit_text") or feature.get("package_size") or feature.get("unit")
    if confidence == "low":
        return PackageInfo(
            feature.get("package_quantity"),
            feature.get("package_unit"),
            1.0,
            feature.get("package_quantity_base"),
            feature.get("base_unit"),
            source=feature.get("package_parse_source") or "structured",
            confidence=confidence,
            source_text=source_text,
            eligible_for_optimization=False,
            warnings=warnings or ["low-confidence package metadata"],
        )
    structured_quantity = feature.get("package_quantity")
    structured_unit = feature.get("package_unit")
    if structured_quantity and structured_unit:
        quantity = canonical_quantity(float(structured_quantity), structured_unit)
        if quantity.base_quantity is not None:
            return PackageInfo(
                package_quantity=float(structured_quantity),
                package_unit=structured_unit,
                package_count=1.0,
                base_quantity=quantity.base_quantity,
                base_unit=quantity.base_unit,
                source="structured",
                confidence=confidence if confidence != "unknown" else "high",
                source_text=source_text,
            )

    text = normalize_package_text(
        " ".join(
            str(value or "")
            for value in (
                feature.get("package_size"),
                feature.get("unit"),
                feature.get("raw_unit_text"),
                feature.get("original_product_name"),
                feature.get("normalized_name"),
            )
        )
    )
    if not text:
        return PackageInfo(None, None, confidence="none", source_text=source_text, eligible_for_optimization=False, warnings=["missing package size"])
    if re.search(r"\b(sold by weight|variable weight|per pound|per lb|lb avg|average weight|family pack)\b", text):
        return PackageInfo(None, "pound", 1.0, None, "gram", sold_by_weight=True, variable_weight=True, source="name", confidence="low", source_text=source_text or text, eligible_for_optimization=False, warnings=["variable weight package"])
    dozen = re.search(r"\b(?:(\d+(?:\.\d+)?)\s*)?dozen\b", text)
    if dozen:
        count = float(dozen.group(1) or 1) * 12
        return PackageInfo(count, "count", 1.0, count, "count", source="name", confidence="high", source_text=source_text or text)
    multi = re.search(r"\b(?P<count>\d+(?:\.\d+)?)\s*(?:x|ct of|pack of)\s*(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>fl oz|fluid ounce|oz|lb|pound|g|gram|kg|ml|l|liter|ct|count|each|can|pack)\b", text)
    if multi:
        package_count = float(multi.group("count"))
        amount = float(multi.group("amount"))
        unit = normalize_count_unit(multi.group("unit")) or normalize_unit(multi.group("unit"))
        item_quantity = canonical_quantity(amount, unit)
        base_quantity = item_quantity.base_quantity * package_count if item_quantity.base_quantity is not None else None
        return PackageInfo(amount, unit, package_count, round(base_quantity, 3) if base_quantity is not None else None, item_quantity.base_unit, source="name", confidence="high", source_text=source_text or text)
    match = re.search(r"\b(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>fl oz|fluid ounce|oz|lb|pound|g|gram|kg|ml|l|liter|ct|count|each|can|pack|pkg|bunch|clove|stick)\b", text)
    if match:
        amount = float(match.group("amount"))
        unit = normalize_count_unit(match.group("unit")) or normalize_unit(match.group("unit"))
        if unit == "pack":
            unit = "count"
        quantity = canonical_quantity(amount, unit)
        return PackageInfo(amount, unit, 1.0, quantity.base_quantity, quantity.base_unit, source="name", confidence="high", source_text=source_text or text)
    count = _first_number(text)
    if count and re.search(r"\b(eggs?|avocados?|lemons?|onions?|garlic|bunch)\b", text):
        return PackageInfo(count, "count", 1.0, count, "count", source="name", confidence="medium", source_text=source_text or text)
    warnings.append("package size unavailable")
    return PackageInfo(None, None, confidence="none", source_text=source_text or text, eligible_for_optimization=False, warnings=warnings)


def parse_price_info(value: Any, feature: dict[str, Any] | None = None) -> PriceInfo:
    raw = str(value if value not in (None, "") else (feature or {}).get("price") or "")
    text = raw.replace(",", "")
    if isinstance(value, (int, float)):
        return PriceInfo(round(float(value), 2), round(float(value), 2), source=str(value))
    if re.search(r"\bbuy\s*one\s*get\s*one\b|\bbogo\b", text, flags=re.I):
        price_match = re.search(r"\$(\d+(?:\.\d{1,2})?)", text)
        price = float(price_match.group(1)) if price_match else None
        return PriceInfo(price, price / 2 if price else None, deal_quantity=2, deal_price=price, bogo=True, source=raw, warnings=[] if price else ["BOGO missing base price"])
    multi = re.search(r"\b(\d+)\s+for\s+\$(\d+(?:\.\d{1,2})?)\b", text, flags=re.I)
    if multi:
        count = int(multi.group(1))
        deal_price = float(multi.group(2))
        return PriceInfo(round(deal_price, 2), round(deal_price / count, 4), deal_quantity=count, deal_price=round(deal_price, 2), source=raw)
    per = re.search(r"\$(\d+(?:\.\d{1,2})?)\s*(?:/|\bper\b)\s*(lb|pound|oz|ounce|kg|g|gram)", text, flags=re.I)
    if per:
        unit = normalize_unit(per.group(2))
        return PriceInfo(None, round(float(per.group(1)), 4), unit, source=raw)
    match = re.search(r"\$(\d+(?:\.\d{1,2})?)", text)
    if match:
        price = round(float(match.group(1)), 2)
        return PriceInfo(price, price, source=raw)
    return PriceInfo(None, None, source=raw, warnings=["price unavailable"])


def _checkout_cost_for_packages(packages_required: float | None, price: PriceInfo) -> float | None:
    if packages_required is None:
        return None
    if price.price_unit:
        return None
    if price.deal_price is not None and price.deal_quantity > 1:
        deal_groups = math.ceil(packages_required / price.deal_quantity)
        return currency_round(deal_groups * price.deal_price)
    if price.checkout_price is None:
        return None
    return currency_round(math.ceil(packages_required) * price.checkout_price)


def calculate_coverage(required: Quantity, package: PackageInfo, ingredient_key: str | None = None) -> QuantityCoverage:
    warnings = list(package.warnings)
    if required.status == UNKNOWN or required.base_quantity is None:
        warnings.append("unknown required quantity")
        return QuantityCoverage(required, package, None, None, required, Quantity(None, required.unit, status=UNKNOWN), None, warnings)
    if package.sold_by_weight or package.variable_weight:
        return QuantityCoverage(required, package, required.base_quantity, 1.0, required, Quantity(0, required.unit, required.dimension, 0, required.base_unit), 0.0, warnings)
    if not package.eligible_for_optimization:
        warnings.append("package metadata excluded from optimization")
        return QuantityCoverage(required, package, None, None, required, Quantity(None, required.unit, status=UNKNOWN, reason="low-confidence package metadata"), None, warnings)
    if package.base_quantity is None or package.base_unit is None:
        warnings.append("insufficient package size")
        return QuantityCoverage(required, package, None, None, required, Quantity(None, required.unit, status=UNKNOWN), None, warnings)
    comparable_required = required
    if required.base_unit != package.base_unit:
        comparable_required = convert_quantity(required, package.base_unit, ingredient_key)
    if comparable_required.base_quantity is None:
        warnings.append("unknown conversions")
        return QuantityCoverage(required, package, None, None, required, Quantity(None, package.package_unit, status=UNKNOWN, reason="unsafe conversion"), None, warnings)
    packages_required = max(1, math.ceil(comparable_required.base_quantity / package.base_quantity))
    purchased_base = packages_required * package.base_quantity
    leftover_base = round(max(0.0, purchased_base - comparable_required.base_quantity), 3)
    used = comparable_required
    if package.package_unit:
        converted_used = convert_quantity(comparable_required, package.package_unit, ingredient_key)
        if converted_used.status != UNKNOWN:
            used = converted_used
    leftover = Quantity(None, package.package_unit, unit_dimension(package.package_unit), leftover_base, package.base_unit)
    if package.package_unit and package.base_unit:
        leftover = convert_quantity(Quantity(leftover_base, package.base_unit, unit_dimension(package.base_unit), leftover_base, package.base_unit), package.package_unit, ingredient_key)
        if leftover.status == UNKNOWN:
            leftover = Quantity(None, package.package_unit, unit_dimension(package.package_unit), leftover_base, package.base_unit)
    coverage = 1.0 if purchased_base >= comparable_required.base_quantity else purchased_base / comparable_required.base_quantity
    leftover_percentage = leftover_base / purchased_base if purchased_base else None
    if packages_required > 1:
        warnings.append("multiple packages required")
    return QuantityCoverage(required, package, packages_required, round(coverage, 4), used, leftover, round(leftover_percentage, 4) if leftover_percentage is not None else None, warnings)


def calculate_cost(coverage: QuantityCoverage, price: PriceInfo) -> CostBreakdown:
    warnings = list(price.warnings) + list(coverage.warnings)
    if coverage.package.sold_by_weight and price.unit_price is not None:
        required = coverage.amount_required
        if price.price_unit and required.base_quantity is not None:
            converted = convert_quantity(required, price.price_unit)
            if converted.quantity is not None:
                checkout = currency_round(converted.quantity * price.unit_price)
                return CostBreakdown(checkout, checkout, round(price.unit_price, 4), 0.0, 0.0, price, warnings)
        warnings.append("unknown conversions")
        return CostBreakdown(None, None, None, None, None, price, warnings)
    if coverage.package.sold_by_weight or coverage.package.variable_weight:
        warnings.append("variable weight price unavailable")
        return CostBreakdown(None, None, None, None, None, price, warnings)
    checkout = _checkout_cost_for_packages(coverage.packages_required, price)
    cost_per_base = None
    effective = None
    leftover_value = None
    if checkout is not None and coverage.package.base_quantity and coverage.packages_required:
        purchased_base = coverage.package.base_quantity * math.ceil(coverage.packages_required)
        cost_per_base = checkout / purchased_base if purchased_base else None
        if coverage.used.base_quantity is not None and cost_per_base is not None:
            effective = currency_round(coverage.used.base_quantity * cost_per_base)
        if coverage.leftover.base_quantity is not None and cost_per_base is not None:
            leftover_value = currency_round(coverage.leftover.base_quantity * cost_per_base)
    return CostBreakdown(checkout, effective, round(cost_per_base, 6) if cost_per_base is not None else None, leftover_value, leftover_value, price, warnings)


def confidence_rank(value: str) -> int:
    return {
        "exact": 5,
        "high": 4,
        "medium": 3,
        "low": 2,
        SUBSTITUTION_ONLY: 1,
        NO_SAFE_MATCH: 0,
    }.get(value, 0)


def ingredient_aggregation_signature(ingredient_text: str) -> tuple[str, dict[str, Any]]:
    profile, parsed = profile_from_query(ingredient_text)
    parts = [
        profile.family or profile.canonical or normalize_text(parsed.get("canonical_name") or ingredient_text),
        profile.canonical or "",
        profile.freshness or "",
        profile.fat_level or "",
        profile.fat_percent or "",
        profile.salted_status or "",
        profile.sweetened_status or "",
        profile.dairy_type or "",
        profile.milk_kind or "",
        profile.flour_type or "",
        profile.tomato_type or "",
        profile.broth_type or "",
        profile.broth_species or "",
        profile.soup_type or "",
        profile.produce_type or "",
        profile.meat_species or "",
        profile.meat_cut or "",
        profile.flavor or "",
        ",".join(sorted(profile.dietary_requirements)),
    ]
    return "|".join(parts), parsed


def candidate_purchase_evaluation(
    ranked: RankedCandidate,
    feature: dict[str, Any],
    required: Quantity,
    ingredient_key: str,
    optimization_mode: str,
    top1_product_id: str | None = None,
) -> PurchaseEvaluation:
    package = parse_package_info(feature)
    coverage = calculate_coverage(required, package, ingredient_key)
    price = parse_price_info(feature.get("raw_price") or feature.get("price"), feature)
    cost = calculate_cost(coverage, price)
    exclusion_reasons = []
    if ranked.conflicts and any(conflict.get("classification") == "hard_reject" for conflict in ranked.conflicts):
        exclusion_reasons.append("hard compatibility conflict")
    if ranked.confidence in {LOW, NO_SAFE_MATCH, SUBSTITUTION_ONLY}:
        exclusion_reasons.append("below minimum compatibility confidence")
    if feature.get("eligible_for_retrieval") is False:
        exclusion_reasons.append("not eligible for retrieval")
    if feature.get("source_quality_score") is not None and feature.get("source_quality_score") < 35:
        exclusion_reasons.append("insufficient source quality")
    if not package.eligible_for_optimization and not package.sold_by_weight:
        exclusion_reasons.append("package metadata is not trustworthy for optimization")
    if cost.checkout_cost is None:
        exclusion_reasons.append("checkout cost unavailable")
    if coverage.coverage is None or coverage.coverage < 1.0:
        exclusion_reasons.append("insufficient quantity coverage")
    waste = coverage.leftover_percentage if coverage.leftover_percentage is not None else 1.0
    checkout = cost.checkout_cost if cost.checkout_cost is not None else float("inf")
    effective = cost.effective_ingredient_cost if cost.effective_ingredient_cost is not None else float("inf")
    trusted_package = 0 if package.eligible_for_optimization or package.sold_by_weight else 1
    changed_penalty = 0 if ranked.product_id == top1_product_id else 1
    if optimization_mode == "lowest_checkout_cost":
        score = (checkout, trusted_package, waste, effective, -confidence_rank(ranked.confidence), -ranked.final_score)
    elif optimization_mode == "lowest_effective_cost":
        score = (effective, trusted_package, checkout, waste, -confidence_rank(ranked.confidence), -ranked.final_score)
    elif optimization_mode == "least_waste":
        score = (waste, checkout, effective, trusted_package, -confidence_rank(ranked.confidence), -ranked.final_score)
    else:
        score = (
            bool(exclusion_reasons),
            trusted_package,
            checkout,
            waste,
            effective,
            changed_penalty,
            -confidence_rank(ranked.confidence),
            -ranked.final_score,
            -(feature.get("source_quality_score") if feature.get("source_quality_score") is not None else 100),
        )
    if package.variable_weight or package.sold_by_weight:
        exclusion_reasons = [reason for reason in exclusion_reasons if reason != "package metadata is not trustworthy for optimization"]
    return PurchaseEvaluation(
        ranked.product_id,
        ranked.product_name,
        required,
        package,
        coverage,
        cost,
        ranked.confidence,
        ranked.final_score,
        ranked.confidence,
        ranked.conflicts,
        optimization_mode,
        score,
        sorted(set(exclusion_reasons)),
        ranked.reason_codes,
        feature.get("source_quality_score"),
    )


def material_improvement(selected: PurchaseEvaluation, top1: PurchaseEvaluation | None, mode: str) -> tuple[bool, str]:
    if top1 is None or selected.product_id == top1.product_id:
        return False, "matcher top-1 retained"
    if selected.exclusion_reasons:
        return False, "selected alternative has exclusions"
    if top1.cost.checkout_cost is None:
        return True, "selected product has trustworthy checkout cost while top-1 does not"
    if selected.cost.checkout_cost is None:
        return False, "selected product lacks checkout cost"
    checkout_savings = top1.cost.checkout_cost - selected.cost.checkout_cost
    waste_delta = (top1.coverage.leftover_percentage or 1.0) - (selected.coverage.leftover_percentage or 1.0)
    if mode == "least_waste" and waste_delta > 0.05:
        return True, "selected product materially reduces waste"
    if checkout_savings >= 0.50:
        return True, "selected product materially lowers checkout cost"
    if mode == "lowest_effective_cost" and top1.cost.effective_ingredient_cost and selected.cost.effective_ingredient_cost:
        if top1.cost.effective_ingredient_cost - selected.cost.effective_ingredient_cost >= 0.25:
            return True, "selected product materially lowers effective ingredient cost"
    return False, "matcher top-1 retained because alternative improvement was not material"


def recipe_ingredients(recipe: Any, recipe_index: int = 0) -> tuple[str, list[str]]:
    if isinstance(recipe, dict):
        recipe_id = str(recipe.get("id") or recipe.get("name") or f"recipe-{recipe_index + 1}")
        ingredients = recipe.get("ingredients") or recipe.get("ingredient_lines") or []
    else:
        recipe_id = f"recipe-{recipe_index + 1}"
        ingredients = recipe
    if isinstance(ingredients, str):
        ingredients = [line.strip() for line in re.split(r"[\n;]+", ingredients) if line.strip()]
    return recipe_id, [str(item) for item in ingredients if str(item).strip()]


class BasketBuilder:
    def __init__(self, match_service: ProductMatchService | None = None):
        self.match_service = match_service or ProductMatchService()
        self._package_cache: dict[str, PackageInfo] = {}
        self._basket_cache: dict[str, RecipeBasket] = {}

    def build_recipe_basket(self, recipe: Any, optimization_mode: str = "balanced") -> RecipeBasket:
        return self.build_multi_recipe_basket([recipe], optimization_mode=optimization_mode)

    def build_multi_recipe_basket(self, recipes: list[Any], optimization_mode: str = "balanced") -> RecipeBasket:
        started = time.perf_counter()
        cache_key = self._basket_cache_key(recipes, optimization_mode)
        cached = self._basket_cache.get(cache_key)
        if cached is not None:
            result = copy.deepcopy(cached)
            result.latency_ms = round((time.perf_counter() - started) * 1000, 2)
            return result
        matched: list[MatchedIngredient] = []
        aggregate: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        recipe_refs = []
        prepared_recipes: list[tuple[int, str, list[str]]] = []
        all_ingredients: list[str] = []
        for recipe_index, recipe in enumerate(recipes):
            recipe_id, ingredients = recipe_ingredients(recipe, recipe_index)
            recipe_refs.append({"recipe_id": recipe_id, "ingredient_count": len(ingredients)})
            prepared_recipes.append((recipe_index, recipe_id, ingredients))
            all_ingredients.extend(ingredients)
        all_results = self.match_service.match_recipe_ingredients(all_ingredients, limit=5)
        result_offset = 0
        for _recipe_index, recipe_id, ingredients in prepared_recipes:
            results = all_results[result_offset : result_offset + len(ingredients)]
            result_offset += len(ingredients)
            for raw, result in zip(ingredients, results):
                parsed = parse_ingredient(raw)
                required = canonical_quantity(parsed.quantity, parsed.unit, parsed.canonical_name)
                signature, _signature_parsed = ingredient_aggregation_signature(raw)
                item_warnings = []
                if required.status == UNKNOWN:
                    item_warnings.append(required.reason or "unknown required quantity")
                if result.confidence in {LOW, NO_SAFE_MATCH, SUBSTITUTION_ONLY}:
                    item_warnings.append("low-confidence match" if result.confidence == LOW else result.confidence)
                if result.substitution_candidates and not result.selected_match:
                    item_warnings.append("substitution available only")
                if not result.selected_match:
                    warnings.extend(item_warnings or ["missing products"])
                    matched.append(MatchedIngredient(recipe_id, raw, parsed.canonical_name, None, None, result.confidence, required, None, None, None, item_warnings or ["missing products"]))
                    continue
                feature = self.match_service.feature_by_id.get(result.selected_match.product_id, {})
                package = self._package_for_feature(result.selected_match.product_id, feature)
                coverage = calculate_coverage(required, package, parsed.canonical_name)
                price = parse_price_info(feature.get("raw_price") or feature.get("price"), feature)
                cost = calculate_cost(coverage, price)
                item_warnings.extend(coverage.warnings)
                item_warnings.extend(cost.warnings)
                product_id = result.selected_match.product_id
                matched.append(
                    MatchedIngredient(
                        recipe_id,
                        raw,
                        parsed.canonical_name,
                        product_id,
                        result.selected_match.product_name,
                        result.confidence,
                        required,
                        coverage,
                        cost,
                        None,
                        sorted(set(item_warnings)),
                    )
                )
                if required.base_quantity is not None:
                    bucket = aggregate.setdefault(
                        signature,
                        {
                            "signature": signature,
                            "feature": feature,
                            "product_name": result.selected_match.product_name,
                            "top1_product_id": product_id,
                            "top1_ranked": result.selected_match,
                            "ranked_candidates": [result.selected_match] + result.compatible_alternatives,
                            "rejected_candidates": result.rejected_candidates,
                            "ingredients": [],
                            "matched_indexes": [],
                            "required_base": 0.0,
                            "base_unit": required.base_unit,
                            "dimension": required.dimension,
                            "unit": required.unit,
                            "ingredient_key": parsed.canonical_name,
                            "warnings": [],
                        },
                    )
                    if bucket["base_unit"] == required.base_unit:
                        bucket["required_base"] += required.base_quantity
                        bucket["ingredients"].append(raw)
                        bucket["matched_indexes"].append(len(matched) - 1)
                        existing_ids = {candidate.product_id for candidate in bucket["ranked_candidates"]}
                        for candidate in [result.selected_match] + result.compatible_alternatives:
                            if candidate.product_id not in existing_ids:
                                bucket["ranked_candidates"].append(candidate)
                                existing_ids.add(candidate.product_id)
                        for candidate in result.rejected_candidates:
                            if candidate.product_id not in existing_ids:
                                bucket["rejected_candidates"].append(candidate)
                                existing_ids.add(candidate.product_id)
                    else:
                        bucket["warnings"].append("unknown conversions")
                else:
                    warnings.append("unknown required quantity")
        basket_items = []
        for signature, data in aggregate.items():
            item = self._basket_item(signature, data, optimization_mode)
            basket_items.append(item)
            if item.optimized_purchase:
                for index in data.get("matched_indexes", []):
                    matched[index].product_id = item.product_id
                    matched[index].product_name = item.product_name
                    matched[index].coverage = item.optimized_purchase.selected.coverage if item.optimized_purchase.selected else matched[index].coverage
                    matched[index].cost = item.optimized_purchase.selected.cost if item.optimized_purchase.selected else matched[index].cost
                    matched[index].optimized_purchase = item.optimized_purchase
        checkout_values = [item.checkout_cost for item in basket_items if item.checkout_cost is not None]
        effective_values = [item.effective_ingredient_cost for item in basket_items if item.effective_ingredient_cost is not None]
        if len(checkout_values) != len(basket_items):
            warnings.append("some checkout costs unavailable")
        all_warnings = sorted(set(warnings + [warning for item in basket_items for warning in item.warnings]))
        result = RecipeBasket(
            recipe_refs,
            matched,
            basket_items,
            round(sum(checkout_values), 2) if checkout_values else None,
            round(sum(effective_values), 2) if effective_values else None,
            all_warnings,
            round((time.perf_counter() - started) * 1000, 2),
        )
        self._basket_cache[cache_key] = copy.deepcopy(result)
        if len(self._basket_cache) > 128:
            self._basket_cache.pop(next(iter(self._basket_cache)))
        return result

    def _basket_cache_key(self, recipes: list[Any], optimization_mode: str) -> str:
        payload = json.dumps(recipes, sort_keys=True, default=str, separators=(",", ":"))
        version = "|".join(
            [
                "basket-optimizer-v1",
                optimization_mode,
                self.match_service.product_index_version() or "no-index",
                self.match_service.overrides.version,
            ]
        )
        return hashlib.sha256(f"{version}|{payload}".encode("utf-8")).hexdigest()

    def _package_for_feature(self, product_id: str, feature: dict[str, Any]) -> PackageInfo:
        cached = self._package_cache.get(product_id)
        if cached is None:
            cached = parse_package_info(feature)
            self._package_cache[product_id] = cached
        return cached

    def optimize_ingredient_purchase(
        self,
        required: Quantity,
        ingredient_key: str,
        ranked_candidates: list[RankedCandidate],
        optimization_mode: str = "balanced",
        top1_product_id: str | None = None,
        rejected_candidates: list[RankedCandidate] | None = None,
    ) -> OptimizedPurchase:
        evaluations: list[PurchaseEvaluation] = []
        rejected: list[PurchaseEvaluation] = []
        seen = set()
        for ranked in ranked_candidates:
            if ranked.product_id in seen:
                continue
            seen.add(ranked.product_id)
            feature = self.match_service.feature_by_id.get(ranked.product_id, {})
            if not feature:
                continue
            evaluation = candidate_purchase_evaluation(ranked, feature, required, ingredient_key, optimization_mode, top1_product_id)
            if evaluation.exclusion_reasons:
                rejected.append(evaluation)
            else:
                evaluations.append(evaluation)
        for ranked in rejected_candidates or []:
            if ranked.product_id in seen:
                continue
            seen.add(ranked.product_id)
            feature = self.match_service.feature_by_id.get(ranked.product_id, {})
            if not feature:
                continue
            evaluation = candidate_purchase_evaluation(ranked, feature, required, ingredient_key, optimization_mode, top1_product_id)
            if not evaluation.exclusion_reasons:
                evaluation.exclusion_reasons.append("not compatible with ingredient requirements")
            rejected.append(evaluation)
        top1_eval = next((item for item in evaluations + rejected if item.product_id == top1_product_id), None)
        viable = sorted(evaluations, key=lambda item: item.optimization_score)
        provisional = viable[0] if viable else top1_eval
        changed, explanation = material_improvement(provisional, top1_eval, optimization_mode) if provisional else (False, "no viable optimized purchase")
        selected = provisional if changed or top1_eval is None else top1_eval
        if selected and selected.exclusion_reasons and viable:
            selected = viable[0]
            changed = selected.product_id != top1_product_id
            explanation = "matcher top-1 unavailable for package optimization; selected best trusted compatible package"
        alternatives = [item for item in viable if not selected or item.product_id != selected.product_id]
        warnings = sorted(set(w for item in evaluations + rejected for w in item.coverage.warnings + item.cost.warnings))
        return OptimizedPurchase(selected, alternatives, rejected, optimization_mode, changed, explanation, warnings)

    def _basket_item(self, signature: str, data: dict[str, Any], optimization_mode: str) -> BasketItem:
        required = Quantity(
            round(data["required_base"], 3),
            data["base_unit"],
            unit_dimension(data["base_unit"]),
            round(data["required_base"], 3),
            data["base_unit"],
        )
        optimized = self.optimize_ingredient_purchase(
            required,
            data.get("ingredient_key") or signature,
            data.get("ranked_candidates") or [data["top1_ranked"]],
            optimization_mode,
            data.get("top1_product_id"),
            data.get("rejected_candidates") or [],
        )
        selected = optimized.selected
        if selected:
            product_id = selected.product_id
            product_name = selected.product_name
            package = selected.package
            coverage = selected.coverage
            cost = selected.cost
        else:
            product_id = data["top1_product_id"]
            product_name = data["product_name"]
            package = self._package_for_feature(product_id, data["feature"])
            coverage = calculate_coverage(required, package, data.get("ingredient_key"))
            price = parse_price_info(data["feature"].get("raw_price") or data["feature"].get("price"), data["feature"])
            cost = calculate_cost(coverage, price)
        return BasketItem(
            product_id,
            product_name,
            data["ingredients"],
            required,
            package,
            coverage.packages_required,
            cost.checkout_cost,
            cost.effective_ingredient_cost,
            coverage.leftover,
            cost.leftover_value,
            optimized,
            sorted(set(data["warnings"] + coverage.warnings + cost.warnings)),
        )


_basket_builder_singleton: BasketBuilder | None = None


def get_basket_builder() -> BasketBuilder:
    global _basket_builder_singleton
    if _basket_builder_singleton is None:
        _basket_builder_singleton = BasketBuilder()
    return _basket_builder_singleton


def build_recipe_basket(recipe: Any, optimization_mode: str = "balanced") -> RecipeBasket:
    return get_basket_builder().build_recipe_basket(recipe, optimization_mode=optimization_mode)


def build_multi_recipe_basket(recipes: list[Any], optimization_mode: str = "balanced") -> RecipeBasket:
    return get_basket_builder().build_multi_recipe_basket(recipes, optimization_mode=optimization_mode)
