import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import recipe_scraper  # noqa: E402
import merge_recipe_databases  # noqa: E402


class RecipeScraperTests(unittest.TestCase):
    def test_current_site_recipe_html_parses_servings_and_categories(self):
        html = """
        <html>
          <head>
            <title>Casio in pastelletto</title>
            <meta name="keywords" content="cheese,italian,breakfast">
          </head>
          <body>
            <article>
              <p><img src="/pix/casio.webp" alt="Casio"></p>
              <p>A short source description.</p>
              <ul>
                <li>Prep time: 1 min</li>
                <li>Servings: 6-8</li>
              </ul>
              <h2 id="ingredients">Ingredients</h2>
              <ul>
                <li>2 slice cheese</li>
                <li>butter</li>
              </ul>
              <h2 id="directions">Directions</h2>
              <ol>
                <li>Cook the cheese.</li>
                <li>Serve warm.</li>
              </ol>
              <h2>Related</h2>
              <p class="taglist"><span><a href="/tags/medieval/">Medieval</a></span></p>
            </article>
          </body>
        </html>
        """

        recipe = recipe_scraper.parse_current_site_recipe_html(
            "https://publicdomainrecipes.com/casio-in-pastelletto/",
            html,
            listing_tags=["easy", "Italian"],
        )

        self.assertEqual(recipe["servings"], "6-8")
        self.assertEqual(recipe["yield"], "6-8 servings")
        self.assertIn("breakfast", recipe["category"])
        self.assertIn("Medieval", recipe["category"])
        self.assertEqual(recipe["ingredients"][0]["name"], "cheese")

    def test_current_site_recipe_html_rejects_missing_source_servings(self):
        html = """
        <html><head><title>No Yield</title></head><body><article>
          <h2 id="ingredients">Ingredients</h2>
          <ul><li>beef</li><li>salt</li></ul>
          <h2 id="directions">Directions</h2>
          <ol><li>Cook.</li></ol>
        </article></body></html>
        """

        with self.assertRaisesRegex(RuntimeError, "serving data"):
            recipe_scraper.parse_current_site_recipe_html(
                "https://publicdomainrecipes.com/no-yield/",
                html,
            )

    def test_merge_normalizes_source_servings_and_rejects_missing_servings(self):
        recipe = merge_recipe_databases.normalize_recipe(
            {
                "name": "Test",
                "source_url": "https://example.test/r",
                "public_domain": True,
                "yield": "Serves 4",
                "category": ["Dinner"],
                "tags": ["Italian", "Dinner"],
                "ingredients": [],
                "instructions": [],
            }
        )

        self.assertEqual(recipe["servings"], 4)
        self.assertEqual(recipe["category"], ["Dinner", "Italian"])

        muffins = merge_recipe_databases.normalize_recipe(
            {
                "name": "Muffins",
                "source_url": "https://example.test/m",
                "public_domain": True,
                "yield": "6 Muffins",
                "serving_size": "1 muffin",
                "ingredients": [],
                "instructions": [],
            }
        )
        self.assertEqual(muffins["servings"], 6)
        self.assertEqual(muffins["servings_source"], "yield_and_serving_size")

        with self.assertRaisesRegex(ValueError, "servings"):
            merge_recipe_databases.normalize_recipe({"name": "No servings"})


if __name__ == "__main__":
    unittest.main()
