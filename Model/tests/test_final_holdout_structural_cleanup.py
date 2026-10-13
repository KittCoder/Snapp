"""Assistant-QA material examples plus independent general-rule witnesses."""
import csv,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'Model'))
from product_ontology import describe,compatibility

class FinalHoldoutStructuralCleanupTests(unittest.TestCase):
    def test_every_material_holdout_case_has_documented_structural_expectation(self):
        rows=[json.loads(line) for line in (ROOT/'Model/evaluation/final_holdout_regressions.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows),68)
        for row in rows:
            with self.subTest(case_id=row['case_id'],cause=row['root_cause']):
                self.assertTrue(row['general_rule'])
                self.assertEqual(compatibility(describe(row['ingredient']),describe(row['product_name'],feature=row['product_feature'],product=True)).allowed,row['expected_allowed'])

    def test_composite_heads_dominate_component_tokens_with_unseen_brands(self):
        for query,product in [('strawberries','Strawberry Shortcake'),('aubergine','Eggplant Bruschetta'),('bacon','Bacon Baked Beans'),('gelatin','Orange Refrigerated Gelatin'),('chicken cooked','Chicken Dinner'),('cream','Cream of Tartar'),('bacon fat','Canadian Bacon'),('mushroom sauce','Mushrooms'),('tomato salsa','Tomatoes'),('pudding mix','Vanilla Extract')]:
            with self.subTest(query=query):
                self.assertFalse(compatibility(describe(query),describe('Unseen Market '+product,product=True)).allowed)

    def test_prepared_grocery_identity_is_valid_in_both_directions(self):
        for query,product in [('frankfurters','Beef Frankfurters'),('salami','Hard Salami'),('ginger snap cookies crushed','Ginger Snaps Cookies'),('seasoned salt','Seasoned Salt'),('black tea','Black Tea'),('matzo meal','Matzo Meal'),('pizza sauce','Pizza Sauce'),('salad dressing','Balsamic Vinaigrette Dressing and Marinade'),('nuts chopped','Almonds'),('cream of tartar','Cream of Tartar')]:
            with self.subTest(query=query):
                self.assertTrue(compatibility(describe(query),describe('Unseen Market '+product,product=True)).allowed)

    def test_variants_species_and_derivative_forms_remain_authoritative(self):
        for query,product in [('wine vinegar','White Vinegar'),('wild rice','Rice'),('seasoned black beans','Black Beans'),('ranch salad dressing','Balsamic Vinaigrette'),('lemon poppy seed dressing','Russian Salad Dressing'),('wheat cereal squares','Whole Wheat Cereal'),('beef frankfurters','Turkey Frankfurters'),('frankfurters','Plant Based Frankfurters'),('cherries','Cherry Tomatoes'),('chopped nuts','Lychee Nuts'),('canned artichoke hearts','Artichoke Hearts')]:
            with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe(product,product=True)).allowed)

    def test_shared_heads_and_states_survive_explicit_alternatives(self):
        for query,product,expected in [('rice or wheat cereal','Rice',False),('rice or wheat cereal','Wheat Cereal',True),('pudding mix lemon or vanilla','Vanilla Extract',False),('seasoned red or black beans','Black Beans',False),('frozen broccoli or cauliflower or mixed vegetables chopped','Frozen Broccoli',True),('apple or cantaloupe','Apple',True)]:
            with self.subTest(query=query):self.assertEqual(compatibility(describe(query),describe(product,product=True)).allowed,expected)

    def test_cooked_meat_needs_verified_simple_product_head(self):
        query=describe('cooked chicken breast')
        self.assertTrue(compatibility(query,describe('Unseen Brand Roasted Chicken Breast',feature={'brand':'Unseen Brand'},product=True)).allowed)
        self.assertFalse(compatibility(query,describe('Unexplained Mealbrand Roasted Chicken Breast',product=True)).allowed)
        self.assertFalse(compatibility(query,describe('Roasted Chicken Breast Dinner',product=True)).allowed)

    def test_cheese_holdout_accepted_pairs_remain_compatible(self):
        # Preserve exact historical pair evidence independently of the active catalog.
        features=json.loads((Path(__file__).parent/'fixtures/recipe_catalog_regression.json').read_text())['historical_cheese_features'];byname={f['original_product_name']:f for f in features}
        rows=list(csv.DictReader((ROOT/'Model/tests/fixtures/release/structural_holdout_assistant_labeled.csv').open()))
        for row in rows:
            if row['sample_group']=='hard: cheese' and row['current_matcher_decision']=='accepted':
                with self.subTest(case=row['case_id']):
                    self.assertTrue(compatibility(describe(row['ingredient_query']),describe(row['selected_product'],feature=byname[row['selected_product']],product=True)).allowed)

if __name__=='__main__':unittest.main()
