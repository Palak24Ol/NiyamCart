from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .models import Product

_STOP_WORDS = {
    "a",
    "all",
    "also",
    "and",
    "any",
    "anything",
    "colour",
    "color",
    "find",
    "for",
    "give",
    "i",
    "in",
    "is",
    "it",
    "looking",
    "maybe",
    "me",
    "need",
    "of",
    "please",
    "product",
    "products",
    "range",
    "recommend",
    "show",
    "some",
    "something",
    "that",
    "the",
    "to",
    "want",
    "with",
}

_ALIASES = [
    {"blue", "indigo", "navy", "azure", "cobalt"},
    {"red", "maroon", "berry", "rose", "burgundy", "crimson"},
    {"green", "emerald", "olive", "mint"},
    {"yellow", "saffron", "mustard", "gold"},
    {"purple", "violet", "plum", "lavender"},
    {"pink", "rose", "blush", "magenta"},
    {"black", "charcoal", "ebony"},
    {"white", "ivory", "cream"},
    {"washable", "wash", "washing"},
    {"bedsheet", "bedlinen", "sheet"},
    {"kids", "kid", "children", "child"},
    {"women", "woman", "female"},
    {"men", "man", "male"},
]

_MAX_PRICE = re.compile(
    r"\b(?:under|below|less\s+than|up\s+to|upto|max(?:imum)?|within|budget(?:\s+of)?)\s*"
    r"(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
_MIN_PRICE = re.compile(
    r"\b(?:above|over|more\s+than|at\s+least|min(?:imum)?)\s*"
    r"(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
_BETWEEN_PRICE = re.compile(
    r"\bbetween\s*(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*"
    r"(?:and|to|-)\s*(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SearchMatch:
    product: Product
    score: float
    matched_fields: list[str]


def _normalise(value: object) -> str:
    text = str(value).casefold().replace("&", " and ")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _rupees_to_paise(value: str) -> int:
    return round(float(value.replace(",", "")) * 100)


def parse_price_constraints(query: str) -> tuple[str, int | None, int | None]:
    minimum: int | None = None
    maximum: int | None = None
    cleaned = query

    between = _BETWEEN_PRICE.search(cleaned)
    if between:
        first, second = (_rupees_to_paise(value) for value in between.groups())
        minimum, maximum = sorted((first, second))
        cleaned = _BETWEEN_PRICE.sub(" ", cleaned)

    maximum_match = _MAX_PRICE.search(cleaned)
    if maximum_match:
        maximum = _rupees_to_paise(maximum_match.group(1))
        cleaned = _MAX_PRICE.sub(" ", cleaned)

    minimum_match = _MIN_PRICE.search(cleaned)
    if minimum_match:
        minimum = _rupees_to_paise(minimum_match.group(1))
        cleaned = _MIN_PRICE.sub(" ", cleaned)

    return cleaned, minimum, maximum


def _variants(token: str) -> set[str]:
    variants = {token}
    for aliases in _ALIASES:
        if token in aliases:
            variants.update(aliases)
    if len(token) > 4 and token.endswith("ies"):
        variants.add(f"{token[:-3]}y")
    if len(token) > 4 and token.endswith("es"):
        variants.add(token[:-2])
    if len(token) > 3 and token.endswith("s"):
        variants.add(token[:-1])
    return variants


def _query_groups(query: str) -> list[set[str]]:
    tokens = _normalise(query).split()
    groups: list[set[str]] = []
    seen: set[frozenset[str]] = set()
    for token in tokens:
        if token in _STOP_WORDS:
            continue
        variants = _variants(token)
        marker = frozenset(variants)
        if marker not in seen:
            groups.append(variants)
            seen.add(marker)
    return groups


def _field_values(product: Product) -> dict[str, str]:
    return {
        "name": product.name,
        "product_id": product.id,
        "brand": product.brand,
        "category": product.category,
        "audience": product.audience,
        "description": product.description,
        "occasion": product.occasion,
        "material": product.material,
        "highlights": " ".join(product.highlights),
        "badges": " ".join(product.badges),
        "specifications": json.dumps(product.specs, ensure_ascii=False),
        "size_chart": f"size chart {json.dumps(product.size_chart or {}, ensure_ascii=False)}",
        "price": f"{product.price_paise // 100} rupees {product.price_paise} paise",
        "original_price": (
            f"{product.original_price_paise // 100} rupees {product.original_price_paise} paise"
        ),
        "rating": f"{product.rating} rating {product.reviews} reviews",
        "stock": f"{product.stock} in stock",
        "delivery": (
            f"{product.delivery_days} days "
            f"{'free delivery' if product.free_delivery else 'paid delivery'}"
        ),
        "returns": f"{product.return_window_days} day returns",
    }


def _matches_variant(variant: str, text: str, words: set[str]) -> bool:
    if variant in words or f" {variant} " in f" {text} ":
        return True
    if len(variant) < 6 or " " in variant:
        return False
    return any(
        len(word) >= 6 and SequenceMatcher(None, variant, word).ratio() >= 0.84
        for word in words
    )


def match_product(product: Product, query: str) -> tuple[float, list[str]] | None:
    searchable_query, _, _ = parse_price_constraints(query)
    groups = _query_groups(searchable_query)
    if not groups:
        return 0.0, []

    weights = {
        "name": 12.0,
        "product_id": 12.0,
        "category": 9.0,
        "material": 9.0,
        "occasion": 8.0,
        "specifications": 8.0,
        "size_chart": 8.0,
        "brand": 7.0,
        "audience": 7.0,
        "highlights": 5.0,
        "badges": 5.0,
        "description": 4.0,
        "price": 4.0,
        "original_price": 2.0,
        "rating": 2.0,
        "stock": 2.0,
        "delivery": 3.0,
        "returns": 3.0,
    }
    fields = {name: _normalise(value) for name, value in _field_values(product).items()}
    field_words = {name: set(value.split()) for name, value in fields.items()}
    matched_fields: list[str] = []
    score = 0.0

    for group in groups:
        matches = [
            name
            for name, value in fields.items()
            if any(_matches_variant(variant, value, field_words[name]) for variant in group)
        ]
        if not matches:
            return None
        best_field = max(matches, key=lambda name: weights[name])
        score += weights[best_field]
        matched_fields.extend(name for name in matches if name not in matched_fields)

    phrase = _normalise(searchable_query)
    if phrase and phrase in fields["name"]:
        score += 15.0
    return score, matched_fields


def search_products(
    products: list[Product],
    query: str,
    *,
    category: str | None = None,
    min_price_paise: int | None = None,
    max_price_paise: int | None = None,
) -> list[SearchMatch]:
    searchable_query, query_minimum, query_maximum = parse_price_constraints(query)
    minimum = max(value for value in (min_price_paise, query_minimum) if value is not None) if any(
        value is not None for value in (min_price_paise, query_minimum)
    ) else None
    maximum = min(value for value in (max_price_paise, query_maximum) if value is not None) if any(
        value is not None for value in (max_price_paise, query_maximum)
    ) else None
    normalised_category = _normalise(category) if category else None
    matches: list[SearchMatch] = []

    for product in products:
        if normalised_category and _normalise(product.category) != normalised_category:
            continue
        if minimum is not None and product.price_paise < minimum:
            continue
        if maximum is not None and product.price_paise > maximum:
            continue
        matched = match_product(product, query)
        if matched is None:
            continue
        score, matched_fields = matched
        matches.append(SearchMatch(product, score, matched_fields))

    exact_name = _normalise(searchable_query)
    exact_matches = [
        match for match in matches if _normalise(match.product.name) == exact_name
    ]
    if exact_matches:
        return exact_matches
    return sorted(
        matches,
        key=lambda match: (match.score, match.product.rating, match.product.reviews),
        reverse=True,
    )
