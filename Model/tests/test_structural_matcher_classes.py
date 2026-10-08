"""General structural rules plus assistant-review diagnostic regressions."""
import csv,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from product_ontology import describe,compatibility,IdentityCatalog
from product_compatibility import ProductMatchService
from test_product_compatibility import feature,FakeRetriever
ROOT=Path(__file__).resolve().parents[2]


class StructuralMatcherClassTests(unittest.TestCase):
    def test_component_tokens_never_override_prepared_heads(self):
        for query, product in [('rice','Rice Cereal8 Vitamins'),('apple','Apple Oatmeal'),('ginger','Ginger Bites'),('potato','Potato Breakfast Bakes'),('mozzarella','Mozzarella Cheese Snack'),('banana','Banana Pepper Slices'),('cream','Cream of Coconut'),('peanut butter','Peanut Butter Bread'),('rice','Rice Cakes'),('honeydew','Honeydew Sorbet'),('orange','Orange Yogurt')]:
            for brand in ['','Unseen Brand ']:
                with self.subTest(query=query,product=product,brand=brand):
                    self.assertFalse(compatibility(describe(query),describe(brand+product,product=True)).allowed)

    def test_specificity_is_directional(self):
        for generic,specific,wrong in [('vinegar','rice vinegar','white vinegar'),('vinegar','white wine vinegar','white vinegar'),('oil','olive oil','sesame oil'),('bread','whole wheat bread','cornbread')]:
            with self.subTest(specific=specific):
                self.assertTrue(compatibility(describe(generic),describe(specific,product=True)).allowed)
                self.assertFalse(compatibility(describe(specific),describe(wrong,product=True)).allowed)

    def test_kitchen_cutting_preserves_material_identity(self):
        for query,product in [('pork tenderloin sliced','Boneless Pork Tenderloin'),('hard boiled eggs sliced','Hard Boiled Eggs'),('garlic cloves whole','Garlic'),('water chestnuts diced','Sliced Water Chestnuts'),('bread squares','Bread'),('almonds chopped','Almonds'),('sliced diced pineapple','Sliced Pineapple'),('ground chicken breast','Ground Chicken Breast'),('ground beef','Ground Beef Chuck'),('baby spinach','Baby Leaf Spinach'),('complete pancake mix','Complete Pancake Mix'),('quick cooking oats','1 Minute Oats')]:
            with self.subTest(query=query):self.assertTrue(compatibility(describe(query),describe(product,product=True)).allowed)
        for query,product in [('ground pork','Pork Tenderloin'),('frozen pineapple diced','Pineapple'),('dried thyme','Thyme'),('smoked chicken breast','Chicken Breast'),('smoked chicken breast','Roasted Chicken Breast'),('cured ham','Uncured Ham')]:
            with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe(product,product=True)).allowed)

    def test_explicit_variants_are_preserved(self):
        for query,product in [('rice vinegar','White Vinegar'),('white wine vinegar','White Vinegar'),('ripe bananas','Green Banana'),('diced tomatoes with chiles','Diced Tomatoes'),('plain yogurt','Strawberry Yogurt'),('fat free mozzarella','Part Skim Mozzarella'),('beef broth','Chicken Broth'),('green peas','Pigeon Peas'),('green peas','Chick Peas'),('soy sauce','Sweet Soy Sauce'),('cooked chicken','Honey Roasted Chicken'),('cooking oil spray','Cooking Oil'),('Italian sausage','Plant Based Italian Sausage'),('ground chicken breast','Ground Chicken'),('pork shoulder ground','Ground Pork'),('beef sirloin','Ground Beef Sirloin'),('freshly squeezed lemon juice','Lemon Juice'),('baby spinach','Leaf Spinach'),('complete pancake mix','Buttermilk Pancake Mix'),('instant rice','Rice'),('almond milk','Vanilla Almond Milk'),('coconut milk','Vanilla Coconut Milk')]:
            with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe(product,product=True)).allowed)

    def test_alternative_branches_are_structural_not_token_unions(self):
        query=describe('onion green or red')
        self.assertTrue(compatibility(query,describe('Red Onion',product=True)).allowed)
        self.assertTrue(compatibility(query,describe('Green Onion',product=True)).allowed)
        self.assertFalse(compatibility(query,describe('Yellow Onion',product=True)).allowed)
        self.assertTrue(compatibility(describe('fresh or frozen spinach'),describe('Fresh Spinach',product=True)).allowed)
        # A required shared salt variant cannot disappear on an OR branch.
        self.assertFalse(compatibility(describe('chicken or turkey broth low sodium'),describe('Chicken Broth',product=True)).allowed)
        self.assertTrue(compatibility(describe('Bibb lettuce or other leaf lettuce'),describe('Green Leaf Lettuce',product=True)).allowed)

    def test_requested_purchased_composites_keep_their_own_heads(self):
        for query,product,wrong in [('cake flour','Enriched Cake Flour','Rice Cakes'),('oyster sauce','New Label Oyster Sauce','Oysters'),('biscuit mix','Buttermilk Biscuit Mix','Butter Biscuits'),('cornbread crumbled','Cornbread','Cornbread Stuffing Mix'),('cinnamon graham crackers','Cinnamon Graham Crackers','Honey Graham Crackers'),('spicy Italian sausage','Hot Italian Sausage','Italian Sausage Ravioli'),('pie crust','Pie Crust','Pie Filling')]:
            with self.subTest(query=query):
                self.assertTrue(compatibility(describe(query),describe(product,product=True)).allowed)
                self.assertFalse(compatibility(describe(query),describe(wrong,product=True)).allowed)

    def test_aliases_are_food_tokens_not_recipe_exceptions(self):
        for left,right in [('hoisin sause','Hoisin Sauce'),('Worcesteshire sauce','Worcestershire Sauce'),('unflavored gelatine','Unflavored Gelatin'),('Bay Leafs','Bay Leaves'),('acorn squashes','Acorn Squash')]:
            for quantity in ['','4 tablespoons ','2 cups ']:
                with self.subTest(left=left,quantity=quantity):self.assertTrue(compatibility(describe(quantity+left),describe(right,product=True)).allowed)

    def test_missing_state_fat_salt_and_dietary_evidence_still_abstains(self):
        for query,product in [('canned mandarin oranges','Mandarin Oranges'),('canned pineapple','Pineapple Chunks'),('fresh tomatillos','Tomatillos'),('fat free mozzarella','Mozzarella'),('low sodium broth','Chicken Broth'),('gluten free flour','Flour')]:
            with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe(product,product=True)).allowed)
        self.assertTrue(compatibility(describe('low sodium tomato sauce'),describe('Tomato Sauce No Salt Added',product=True)).allowed)
        self.assertFalse(compatibility(describe('tomato sauce no salt added'),describe('Low Sodium Tomato Sauce',product=True)).allowed)

    def test_near_tied_material_identity_abstains_not_package_ties(self):
        svc=ProductMatchService(retriever=FakeRetriever([feature('rice','Rice Vinegar'),feature('white','White Vinegar')]))
        result=svc.match_recipe_ingredient('vinegar')
        self.assertIsNone(result.selected_match)
        self.assertIn('ambiguous_material_identity_margin',result.reason_codes)
        self.assertEqual(result.diagnostics['material_top1_top2_margin'],0)
        safe=ProductMatchService(retriever=FakeRetriever([feature('one','White Vinegar'),feature('two','White Vinegar')])).match_recipe_ingredient('white vinegar')
        self.assertIsNotNone(safe.selected_match)

    def test_all_material_review_regression_examples(self):
        for line in (ROOT/'Model/evaluation/structural_review_regressions.jsonl').read_text().splitlines():
            row=json.loads(line)
            with self.subTest(case=row['case_id'],cause=row['root_cause']):
                self.assertEqual(compatibility(describe(row['ingredient']),describe(row['product_name'],feature=row['product_feature'],product=True)).allowed,row['expected_allowed'])

    def test_all_reviewed_wrong_pairs_are_rejected_with_unseen_brands(self):
        import io
        rows=csv.DictReader(io.StringIO((ROOT/'data/matcher_validation/review_assistant_issues.csv').read_text()))
        fs=json.loads((ROOT/'Model/morton_williams_product_features.json').read_text())['features']
        byname={f['original_product_name']:f for f in fs}
        for row in rows:
            if row['review_label']!='WRONG':continue
            for prefix in ['','Unseen Market ']:
                with self.subTest(case=row['case_id'],prefix=prefix):
                    original=byname.get(row['selected_product'],{})
                    self.assertFalse(compatibility(describe(row['ingredient_query']),describe(prefix+row['selected_product'],feature=original,product=True)).allowed)
