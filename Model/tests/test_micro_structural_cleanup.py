"""Adversarial semantic heads, required attributes and directional preparation."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'Model'))
from product_ontology import describe,compatibility

class MicroStructuralCleanupTests(unittest.TestCase):
    def test_generated_derivative_matrix_is_not_a_component_match(self):
        for base in ('strawberries','eggplant','pork liver','marshmallows','brown sugar','rice'):
            for head in ('sauce','soup','cereal','bread','snack','drink','seasoning','spread','pastry','entree'):
                with self.subTest(base=base,head=head):
                    self.assertFalse(compatibility(describe(base),describe('Unseen Brand '+base+' '+head,product=True)).allowed)

    def test_nonfood_name_and_metadata_signals_precede_food_heads(self):
        for name in ('Metal Care Copper Cream','Silver Polish Cream','Face Cream','Lemon Cleaner','Chicken Dog Food','Strawberry Shampoo','Vitamin Supplements'):
            for query in ('cream','lemon','chicken breast','strawberries'):
                with self.subTest(query=query,product=name):self.assertFalse(compatibility(describe(query),describe(name,product=True)).allowed)
        for category in ('household','cleaning','cosmetics','personal care','supplements'):
            with self.subTest(category=category):self.assertEqual(describe('Cream',feature={'category':category},product=True).family,'nonfood')

    def test_compound_heads_and_baking_cream_identity_are_distinct(self):
        names=('cream','cream of tartar','heavy cream','sour cream','cream cheese','cream of coconut')
        self.assertEqual(len({(describe(x).family,describe(x).subfamily) for x in names}),6)
        for query,product in [('spaghetti','Spaghetti Squash'),('snow peas','Garden Peas'),('Brazil nuts','Breadfruit Nuts'),('olive oil','Olives'),('banana','Banana Peppers'),('orange peel','Orange Flavored Prunes'),('marshmallows','Marshmallow Fluff')]:
            with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe(product,product=True)).allowed)

    def test_explicit_purchase_variants_require_product_evidence(self):
        for query,product in [('sweet paprika','Smoked Paprika'),('extra virgin olive oil','Refined Olive Oil'),('instant whole grain rice','Instant Rice'),('fat reduced mayonnaise','Mayonnaise'),('flavored gelatin','Unflavored Gelatin'),('candied cherries','Dried Cherries'),('black peppercorns','Ground Black Pepper'),('microwavable mixed vegetables','Canned Mixed Vegetables'),('bacon','Canadian Bacon'),('tuna','Tuna With Red Peppers'),('tomato concentrate','Strained Tomatoes')]:
            with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe(product,product=True)).allowed)
        for query,product in [('extra virgin olive oil','Extra Virgin Olive Oil'),('candied cherries','Candied Cherries'),('black peppercorns','Whole Black Peppercorns'),('cream of tartar','Cream of Tartar')]:
            with self.subTest(query=query):self.assertTrue(compatibility(describe(query),describe(product,product=True)).allowed)

    def test_kitchen_preparation_preserves_species_cuts_and_purchase_state(self):
        for query,product in [('cooked chicken breast diced','Raw Chicken Breast'),('cooked kidney beans','Kidney Beans'),('ham minced or ground fine','Ham'),('coconut shredded or flaked','Shredded Coconut')]:
            with self.subTest(query=query):self.assertTrue(compatibility(describe(query),describe(product,product=True)).allowed)
        for query,product in [('cooked chicken breast','Raw Chicken Thighs'),('ground pork','Pork Tenderloin'),('smoked chicken breast','Raw Chicken Breast'),('frozen strawberries','Strawberries')]:
            with self.subTest(query=query):self.assertFalse(compatibility(describe(query),describe(product,product=True)).allowed)

    def test_prepared_products_are_legitimate_when_their_identity_is_requested(self):
        for name in ('salami','frankfurters','sauerkraut','potato chips','ginger snaps','salad dressing','matzo meal','Andouille sausage'):
            with self.subTest(name=name):self.assertTrue(compatibility(describe(name),describe('Unseen Brand '+name,product=True)).allowed)

    def test_exact_and_substitute_modes_remain_distinct(self):
        query=describe('tamari');product=describe('Soy Sauce',product=True)
        self.assertFalse(compatibility(query,product).allowed)
        self.assertEqual(compatibility(query,product,'substitute').match_type,'substitute')
        self.assertFalse(compatibility(describe('Yukon Gold potatoes'),describe('Russet Potatoes',product=True)).allowed)
        self.assertTrue(compatibility(describe('heavy cream'),describe('Double Cream',product=True)).allowed)
        self.assertFalse(compatibility(describe('parmesan'),describe('Mozzarella',product=True)).allowed)

    def test_material_review_regressions(self):
        rows=[json.loads(l) for l in (ROOT/'Model/evaluation/micro_holdout_regressions.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows),71)
        for row in rows:
            with self.subTest(case=row['case_id'],cause=row['root_cause']):
                self.assertTrue(row['general_rule'])
                self.assertEqual(compatibility(describe(row['ingredient']),describe(row['product_name'],feature=row['product_feature'],product=True)).allowed,row['expected_allowed'])

if __name__=='__main__':unittest.main()
