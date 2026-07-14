import json
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parent
ALL_RECIPES_PATH = MODEL_DIR / "all_recipes.json"
SEARCH_DB_PATH = MODEL_DIR / "all_recipes_search.sqlite"

STOPWORDS = {
    "and",
    "for",
    "with",
    "the",
    "recipe",
    "recipes",
    "meal",
    "meals",
    "easy",
    "quick",
    "healthy",
}


def normalize_text(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def tokens(value):
    result = []
    for token in normalize_text(value).split():
        if len(token) <= 2 or token in STOPWORDS:
            continue
        if token.endswith("s") and len(token) > 3:
            token = token[:-1]
        result.append(token)
    return result


def joined(values):
    return " ".join(str(value or "") for value in values if value)


def recipe_text_parts(recipe):
    categories = recipe.get("category") or []
    food_groups = [
        group.get("label", "")
        for group in recipe.get("food_groups") or []
        if isinstance(group, dict)
    ]
    ingredients = [
        joined((ingredient.get("name"), ingredient.get("raw"), ingredient.get("note")))
        for ingredient in recipe.get("ingredients") or []
        if isinstance(ingredient, dict)
    ]
    return {
        "name": recipe.get("name") or "",
        "category": joined([*categories, *food_groups]),
        "ingredients": joined(ingredients),
        "description": recipe.get("description") or "",
        "source": recipe.get("source") or "",
    }


def build_database(recipes, output_path):
    temp = tempfile.NamedTemporaryFile(suffix=".sqlite", dir=output_path.parent, delete=False)
    temp.close()
    temp_path = Path(temp.name)
    conn = sqlite3.connect(temp_path)
    try:
        conn.execute("pragma journal_mode=OFF")
        conn.execute("pragma synchronous=OFF")
        conn.execute("pragma temp_store=MEMORY")
        conn.execute(
            """
            create table recipes (
              id text primary key,
              name text not null,
              source text,
              payload text not null
            )
            """
        )
        conn.execute("create table tokens (token text primary key)")
        conn.execute(
            """
            create virtual table recipe_fts using fts5(
              recipe_id unindexed,
              name,
              category,
              ingredients,
              description,
              source,
              tokenize = 'unicode61 remove_diacritics 2'
            )
            """
        )

        token_set = set()
        recipe_count = 0
        for recipe in recipes:
            recipe_id = str(recipe.get("id") or "").strip()
            name = str(recipe.get("name") or "").strip()
            if not recipe_id or not name:
                continue
            parts = recipe_text_parts(recipe)
            conn.execute(
                "insert into recipes (id, name, source, payload) values (?, ?, ?, ?)",
                (
                    recipe_id,
                    name,
                    recipe.get("source") or "",
                    json.dumps(recipe, separators=(",", ":"), sort_keys=True),
                ),
            )
            conn.execute(
                """
                insert into recipe_fts
                  (recipe_id, name, category, ingredients, description, source)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    recipe_id,
                    parts["name"],
                    parts["category"],
                    parts["ingredients"],
                    parts["description"],
                    parts["source"],
                ),
            )
            token_set.update(tokens(" ".join(parts.values())))
            recipe_count += 1

        conn.executemany(
            "insert into tokens (token) values (?)",
            [(token,) for token in sorted(token_set)],
        )
        conn.execute(
            "create table metadata (key text primary key, value text not null)"
        )
        metadata = {
            "source": "SNAPP all_recipes SQLite FTS search database",
            "source_file": "all_recipes.json",
            "recipe_count": str(recipe_count),
            "token_count": str(len(token_set)),
            "built_at": datetime.now(timezone.utc).isoformat(),
        }
        conn.executemany(
            "insert into metadata (key, value) values (?, ?)",
            sorted(metadata.items()),
        )
        conn.commit()
        conn.execute("vacuum")
    finally:
        conn.close()

    temp_path.replace(output_path)
    return recipe_count, len(token_set)


def main():
    data = json.loads(ALL_RECIPES_PATH.read_text(encoding="utf-8"))
    recipes = data.get("recipes") or []
    recipe_count, token_count = build_database(recipes, SEARCH_DB_PATH)
    print(f"Wrote {recipe_count} recipes and {token_count} tokens to {SEARCH_DB_PATH}.")


if __name__ == "__main__":
    main()
