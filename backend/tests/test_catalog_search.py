from pathlib import Path

import pytest
from app.agent_schemas import SearchCatalogArgs
from app.agent_tools import search_catalog
from app.catalog import load_catalog, seed_catalog
from app.database import Database


@pytest.fixture
def catalog_db(tmp_path: Path) -> Database:
    database = Database(f"sqlite:///{tmp_path / 'catalog-search.db'}")
    database.create_schema()
    with database.session_factory() as session:
        seed_catalog(session)
    return database


def search(catalog_db: Database, query: str, **filters: object) -> list[dict[str, object]]:
    with catalog_db.session_factory() as session:
        result = search_catalog(
            session,
            SearchCatalogArgs(query=query, limit=10, **filters),
        )
    return result["products"]  # type: ignore[return-value]


def names(products: list[dict[str, object]]) -> list[str]:
    return [str(product["name"]) for product in products]


def test_natural_price_limit_finds_bedsheets_under_300(catalog_db: Database) -> None:
    results = search(catalog_db, "bedsheet under 300")

    assert set(names(results)) == {"Indigo Floral Bedsheet Set", "Berry Floral Bedsheet Set"}
    assert all(int(product["price_paise"]) <= 30_000 for product in results)


def test_product_type_in_category_field_is_recovered_deterministically(
    catalog_db: Database,
) -> None:
    results = search(
        catalog_db,
        "blue",
        category="bedsheet",
        max_price_paise=30_000,
    )

    assert names(results) == ["Indigo Floral Bedsheet Set"]


def test_unknown_broad_category_does_not_hide_a_grounded_match(
    catalog_db: Database,
) -> None:
    results = search(
        catalog_db,
        "green kurti",
        category="clothing",
        max_price_paise=40_000,
    )

    assert names(results) == ["Emerald Chikankari Kurta"]


def test_colour_alias_and_hex_search_catalogue_fields(catalog_db: Database) -> None:
    blue = search(catalog_db, "blue bedsheet in any range")
    by_hex = search(catalog_db, "bedsheet #4657A7")

    assert names(blue) == ["Indigo Floral Bedsheet Set"]
    assert names(by_hex)[0] == "Indigo Floral Bedsheet Set"
    assert "specifications" in by_hex[0]["matched_fields"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("machine washable bedhseet", "Berry Floral Bedsheet Set"),
        ("housewarming bedsheet", "Indigo Floral Bedsheet Set"),
        ("dishwasher safe cookware", "Berry Stainless Steel Cookware Set"),
        ("5 piece set cookware", "Berry Stainless Steel Cookware Set"),
        ("size XL cotton kurta", "Maroon Floral Cotton Kurta"),
        ("chest 103 kurta", "Maroon Floral Cotton Kurta"),
    ],
)
def test_searches_specs_size_chart_care_and_tolerates_typos(
    catalog_db: Database,
    query: str,
    expected: str,
) -> None:
    assert expected in names(search(catalog_db, query))


def test_explicit_price_range_is_enforced(catalog_db: Database) -> None:
    results = search(
        catalog_db,
        "bedsheet",
        min_price_paise=20_000,
        max_price_paise=30_000,
    )

    assert names(results) == ["Indigo Floral Bedsheet Set"]


def test_exact_product_name_wins_over_colour_aliases(catalog_db: Database) -> None:
    results = search(catalog_db, "Maroon Floral Cotton Kurta")

    assert names(results) == ["Maroon Floral Cotton Kurta"]


def test_catalogue_uses_product_family_materials() -> None:
    products = {item["name"]: item for item in load_catalog()}
    bedsheet = products["Indigo Floral Bedsheet Set"]
    cookware = products["Indigo Stainless Steel Cookware Set"]

    assert bedsheet["material"] == "Cotton"
    assert bedsheet["specs"]["primary_material"] == "Cotton"
    assert "stainless steel" not in bedsheet["description"].lower()
    assert cookware["material"] == "Stainless Steel"
