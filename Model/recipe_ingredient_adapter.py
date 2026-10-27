from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from ingredient_normalization import extract_quantity_and_unit, normalize_text, normalize_unit, parse_ingredient, parse_number


SMALL_NUMBERS = {
    "a": 1.0,
    "an": 1.0,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
    "eleven": 11.0,
    "twelve": 12.0,
}

COUNT_CONTAINER_UNITS = {
    "bunch",
    "can",
    "clove",
    "egg",
    "head",
    "jar",
    "package",
    "pack",
    "stick",
    "stalk",
}

SCHEMA_STRUCTURED_DICT = "structured_ingredient_dict"
SCHEMA_SPOONACULAR_EXTENDED = "spoonacular_extended_ingredient"
SCHEMA_TEXT_LINE = "raw_text_line"


@dataclass
class CanonicalRecipeIngredient:
    raw_text: str
    quantity: float | None
    quantity_min: float | None
    quantity_max: float | None
    unit: str | None
    ingredient_name: str
    note: str = ""
    source_fields: dict[str, Any] = field(default_factory=dict)
    source_recipe_id: str = ""
    source_schema: str = ""
    parser_provenance: dict[str, str] = field(default_factory=dict)
    confidence: str = "medium"
    warnings: list[str] = field(default_factory=list)
    package_quantity: float | None = None
    package_unit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def matcher_text(self) -> str:
        parts = []
        if self.quantity is not None:
            parts.append(f"{self.quantity:g}")
        if self.unit:
            parts.append(self.unit)
        name = self.ingredient_name
        # Source labels may be broad (e.g. nameClean="oil"). Preserve the
        # structural identity in the original line before appending preparation.
        from product_ontology import describe
        original = self.raw_text
        source_note = str(self.source_fields.get("note") or "")
        if source_note:
            original = original.replace(source_note, "")
        original, _, _ = split_package_descriptor(original)
        original_name = extract_quantity_and_unit(original)[-1]
        raw_identity = describe(original_name)
        label_identity = describe(" ".join((name, self.note)))
        if raw_identity.family and any(
            getattr(raw_identity, key) and getattr(raw_identity, key) != getattr(label_identity, key)
            for key in ("family", "subfamily", "species", "cut", "grade", "state", "form",
                        "fat_level", "salt_level", "dietary_identity", "flavor", "purchase_variants")
        ):
            name = original_name
        if name:
            parts.append(name)
        # Notes remain separate; preparation already in the identity is not
        # appended a second time ("minced garlic minced").
        for note in re.split(r",\s*", self.note):
            if note and not re.search(rf"\b{re.escape(note)}\b", name, re.I):
                parts.append(note)
        return re.sub(r"\s+", " ", " ".join(parts)).strip() or self.raw_text


def parse_small_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    parsed = parse_number(text)
    if parsed is not None:
        return parsed
    return SMALL_NUMBERS.get(normalize_text(text))


def split_package_descriptor(text: str) -> tuple[str, float | None, str | None]:
    pattern = re.compile(
        r"^\s*(?P<count>a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|\d+(?:\.\d+)?)\s+"
        r"(?P<pkg_qty>\d+(?:\.\d+)?(?:\s+\d+/\d+|/\d+)?)\s*[- ]\s*"
        r"(?P<pkg_unit>ounces?|oz|pounds?|lbs?|grams?|g|cups?|fluid ounces?|fl oz)\s+"
        r"(?P<container>cans?|packages?|pkg|jars?|packs?)\b\s*(?P<rest>.*)$",
        re.I,
    )
    match = pattern.match(text or "")
    if not match:
        return text, None, None
    count = parse_small_number(match.group("count"))
    container = normalize_unit(match.group("container")) or normalize_text(match.group("container"))
    rest = match.group("rest").strip(" ,")
    rewritten = f"{count:g} {container} {rest}".strip() if count is not None else text
    return rewritten, parse_number(match.group("pkg_qty")), normalize_unit(match.group("pkg_unit"))


def clean_structured_note_for_identity(note: str) -> str:
    cleaned = str(note or "")
    cleaned = re.sub(r"\(?\b\d+(?:\.\d+)?(?:\s+\d+/\d+|/\d+)?\s*(?:ounces?|oz|pounds?|lbs?|grams?|g|cups?|fluid ounces?|fl oz)\)?", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\bor\s+any\b.*$", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\bor\s+[^,]+$", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,()")
    return cleaned


def canonical_ingredient_from_structured(
    ingredient: dict[str, Any],
    *,
    source_recipe_id: str = "",
) -> CanonicalRecipeIngredient:
    raw_text = re.sub(r"\s+", " ", str(ingredient.get("raw") or ingredient.get("display") or ingredient.get("measure") or ingredient.get("original") or "").strip())
    name = re.sub(r"\s+", " ", str(ingredient.get("name") or "").strip())
    source_note = re.sub(r"\s+", " ", str(ingredient.get("note") or "").strip())
    note = clean_structured_note_for_identity(source_note)
    quantity = parse_small_number(ingredient.get("quantity") if ingredient.get("quantity") is not None else ingredient.get("amount") or ingredient.get("quantity_text"))
    unit = normalize_unit(ingredient.get("unit"))
    warnings = []
    provenance = {
        "quantity": "source.quantity" if quantity is not None else "parser",
        "unit": "source.unit" if unit else "parser",
        "ingredient_name": "source.name" if name else "parser",
        "note": "source.note" if note else "missing",
    }

    parse_text = raw_text or " ".join(part for part in (str(ingredient.get("quantity") or ""), str(ingredient.get("unit") or ""), name, note) if part)
    package_quantity = None
    package_unit = None
    if quantity is None or not unit or not name:
        rewritten, package_quantity, package_unit = split_package_descriptor(parse_text)
        parsed = parse_ingredient(rewritten)
        if quantity is None:
            quantity = parsed.quantity
        if not unit:
            unit = parsed.unit
        if not name:
            name = parsed.canonical_name
        if parsed.quantity_max is not None:
            warnings.append("quantity range parsed from raw text")
    else:
        parsed = parse_ingredient(name)

    if unit in COUNT_CONTAINER_UNITS and not name:
        warnings.append("container unit has no ingredient name")
    if raw_text and quantity is not None and re.match(r"^\s*\d", raw_text) and provenance["quantity"] == "source.quantity":
        warnings.append("source quantity trusted; raw text not reparsed for main quantity")

    return CanonicalRecipeIngredient(
        raw_text=parse_text,
        quantity=quantity,
        quantity_min=getattr(parsed, "quantity_min", None),
        quantity_max=getattr(parsed, "quantity_max", None),
        unit=unit,
        ingredient_name=name or getattr(parsed, "canonical_name", ""),
        note=note,
        source_fields=dict(ingredient),
        source_recipe_id=source_recipe_id,
        source_schema=SCHEMA_STRUCTURED_DICT,
        parser_provenance=provenance,
        confidence="high" if name and (quantity is not None or unit is None) else "medium",
        warnings=warnings,
        package_quantity=package_quantity,
        package_unit=package_unit,
    )


def canonical_ingredient_from_spoonacular(
    ingredient: dict[str, Any],
    *,
    source_recipe_id: str = "",
) -> CanonicalRecipeIngredient:
    raw_text = re.sub(r"\s+", " ", str(ingredient.get("original") or ingredient.get("display") or "").strip())
    name = re.sub(
        r"\s+",
        " ",
        str(ingredient.get("nameClean") or ingredient.get("name") or ingredient.get("originalName") or "").strip(),
    )
    rewritten, package_quantity, package_unit = split_package_descriptor(raw_text)
    parsed = parse_ingredient(rewritten or name)
    return CanonicalRecipeIngredient(
        raw_text=raw_text or name,
        quantity=parsed.quantity,
        quantity_min=parsed.quantity_min,
        quantity_max=parsed.quantity_max,
        unit=parsed.unit,
        ingredient_name=name or parsed.canonical_name,
        note=", ".join(parsed.preparation),
        source_fields=dict(ingredient),
        source_recipe_id=source_recipe_id,
        source_schema=SCHEMA_SPOONACULAR_EXTENDED,
        parser_provenance={
            "quantity": "parser",
            "unit": "parser",
            "ingredient_name": "source.name" if name else "parser",
            "note": "parser.preparation",
        },
        confidence="medium",
        warnings=[],
        package_quantity=package_quantity,
        package_unit=package_unit,
    )


def canonical_ingredient_from_text(value: Any, *, source_recipe_id: str = "") -> CanonicalRecipeIngredient:
    raw_text = re.sub(r"\s+", " ", str(value or "").strip())
    juice_match = re.match(
        r"^\s*juice of\s+(?P<count>a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|\d+(?:\.\d+)?)\s+lemons?\b",
        raw_text,
        flags=re.I,
    )
    if juice_match:
        return CanonicalRecipeIngredient(
            raw_text=raw_text,
            quantity=parse_small_number(juice_match.group("count")),
            quantity_min=None,
            quantity_max=None,
            unit="lemon",
            ingredient_name="lemon",
            note="juice",
            source_fields={"value": value},
            source_recipe_id=source_recipe_id,
            source_schema=SCHEMA_TEXT_LINE,
            parser_provenance={
                "quantity": "parser.juice_of_count",
                "unit": "parser.juice_of_count",
                "ingredient_name": "parser.juice_of_count",
                "note": "parser.juice_of_count",
            },
            confidence="medium",
            warnings=["juice quantity is represented as count of lemons, not liquid volume"],
        )
    rewritten, package_quantity, package_unit = split_package_descriptor(raw_text)
    parsed = parse_ingredient(rewritten)
    ingredient_name = parsed.canonical_name
    if parsed.form and parsed.canonical_name and parsed.form not in parsed.canonical_name:
        ingredient_name = f"{parsed.form} {parsed.canonical_name}".strip()
    return CanonicalRecipeIngredient(
        raw_text=raw_text,
        quantity=parsed.quantity,
        quantity_min=parsed.quantity_min,
        quantity_max=parsed.quantity_max,
        unit=parsed.unit,
        ingredient_name=ingredient_name,
        note=", ".join(parsed.preparation),
        source_fields={"value": value},
        source_recipe_id=source_recipe_id,
        source_schema=SCHEMA_TEXT_LINE,
        parser_provenance={
            "quantity": "parser",
            "unit": "parser",
            "ingredient_name": "parser",
            "note": "parser.preparation",
        },
        confidence="medium",
        warnings=[],
        package_quantity=package_quantity,
        package_unit=package_unit,
    )


def is_recipe_section_heading(value: Any) -> bool:
    """Recognize recipe structure before punctuation/quantity normalization."""
    if isinstance(value, dict):
        kind = str(value.get("type") or value.get("kind") or value.get("role") or "").lower()
        if kind in {"heading", "section", "section_heading", "header"} or value.get("is_heading") is True:
            return True
        texts = [value.get(key) for key in ("raw", "original", "display", "name", "nameClean")]
        if (parse_small_number(value.get("quantity", value.get("amount"))) or 0) > 0 or value.get("unit"):
            return False
    else:
        texts = [value]
    for text in texts:
        text = str(text or "").strip()
        if not text or extract_quantity_and_unit(text)[0] is not None:
            continue
        if text.endswith(":") or re.match(r"^for\s+(?:the\s+)?[^:]+:?$", text, re.I):
            return True
    return False


def canonical_recipe_ingredients(recipe: Any) -> list[CanonicalRecipeIngredient]:
    recipe_id = ""
    if isinstance(recipe, dict):
        recipe_id = str(recipe.get("id") or recipe.get("name") or recipe.get("title") or "")
        extended = bool(recipe.get("extendedIngredients"))
        values = recipe.get("extendedIngredients") or recipe.get("ingredients") or recipe.get("ingredient_lines") or []
    else:
        extended = False
        values = recipe if isinstance(recipe, list) else [recipe]
    if isinstance(values, str):
        values = re.split(r"[\n;]+", values)
    result = []
    for value in values:
        if not str(value or "").strip() or is_recipe_section_heading(value):
            continue
        if isinstance(value, dict):
            adapter = canonical_ingredient_from_spoonacular if extended else canonical_ingredient_from_structured
            result.append(adapter(value, source_recipe_id=recipe_id))
        else:
            result.append(canonical_ingredient_from_text(value, source_recipe_id=recipe_id))
    return result


def ingredient_with_quantity(text: str, quantity: float, unit: str | None) -> str:
    """Change only the amount; never rebuild identity from a broad parser name."""
    remainder = extract_quantity_and_unit(text)[-1]
    remainder = re.sub(r"\bper person\b", "", remainder, flags=re.I).strip()
    from product_ontology import describe
    parsed = parse_ingredient(text)
    def identity(value):
        result = describe(value).to_dict()
        for key in ("normalized_text", "evidence"):
            result.pop(key, None)
        return result
    # A canonical spelling is safe only if it retains the complete ontology
    # identity and no preparation is removed. Otherwise keep the source head.
    preparation = [term for term in parsed.preparation if term != "per person"]
    if not preparation and identity(remainder) == identity(parsed.canonical_name):
        remainder = parsed.canonical_name
    remainder = re.sub(r"\s*,\s*", " ", remainder).strip()
    if unit and re.search(rf"\b{re.escape(unit)}s?\b", normalize_text(remainder)):
        unit = None
    return " ".join(part for part in (f"{quantity:g}", unit or "", remainder) if part)
