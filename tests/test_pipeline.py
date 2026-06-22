import unittest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.nutrient_parser import extract_nutrition
from validator.bounds_validator import validate_bounds
from scoring.rule_scorer import calculate_health_score
from scoring.hybrid_scorer import NutriScorer

class TestNutriScanPipeline(unittest.TestCase):
    def test_synonym_and_unit_parsing(self):
        # Sample raw text simulating OCR output
        raw_ocr = (
            "Nutrition Facts\n"
            "Serving Size 55 g\n"
            "Calories 250 kcal\n"
            "Protien 12 g\n"
            "Total Sugar 14 g\n"
            "Saturated Fat 6 g\n"
            "Sodium 800 mg\n"
            "Trans Fat 0 g\n"
        )
        data = extract_nutrition(raw_ocr)
        
        self.assertEqual(data["serving_size"], 55.0)
        self.assertEqual(data["energy_kcal"], 250.0)
        self.assertEqual(data["protein_g"], 12.0)
        self.assertEqual(data["sugars_g"], 14.0)
        self.assertEqual(data["saturated_fat_g"], 6.0)
        self.assertEqual(data["sodium_mg"], 800.0)
        self.assertEqual(data["trans_fat_g"], 0.0)
        self.assertIsNone(data["cholesterol_mg"]) # Missing should be null

    def test_unit_conversion(self):
        # Test sodium salt conversion and kJ conversion
        raw_ocr = (
            "Energy 1000 kJ\n"
            "Salt 2 g\n"
            "Cholesterol 0.05 g\n"
        )
        data = extract_nutrition(raw_ocr)
        # 1000 kJ / 4.184 = 239.0 kcal
        self.assertAlmostEqual(data["energy_kcal"], 239.0, places=1)
        # 2g salt = 800mg sodium (1g salt = 400mg sodium)
        self.assertEqual(data["sodium_mg"], 800.0)
        # 0.05g cholesterol = 50mg cholesterol
        self.assertEqual(data["cholesterol_mg"], 50.0)

    def test_bounds_validation(self):
        # Valid data
        valid_data = {
            "protein_g": 12.0,
            "fat_g": 8.0,
            "energy_kcal": 250.0
        }
        res_valid = validate_bounds(valid_data)
        self.assertTrue(res_valid["is_valid"])
        self.assertEqual(len(res_valid["flags"]), 0)

        # Invalid data (out of bounds)
        invalid_data = {
            "protein_g": 400.0, # limit is 200g
            "energy_kcal": 3000.0 # limit is 2500 kcal
        }
        res_invalid = validate_bounds(invalid_data)
        self.assertFalse(res_invalid["is_valid"])
        self.assertEqual(len(res_invalid["flags"]), 2)
        flagged_fields = [f["field"] for f in res_invalid["flags"]]
        self.assertIn("energy_kcal", flagged_fields)
        self.assertIn("protein_g", flagged_fields)
        for flag in res_invalid["flags"]:
            self.assertEqual(flag["issue"], "out_of_range")

    def test_health_scoring_and_insights(self):
        # Healthy product
        healthy_data = {
            "serving_size": 100.0,
            "protein_g": 15.0,
            "fiber_g": 8.0,
            "sugars_g": 2.0,
            "saturated_fat_g": 1.0,
            "sodium_mg": 100.0
        }
        score_res = calculate_health_score(healthy_data)
        self.assertGreaterEqual(score_res["health_score"], 80)
        self.assertEqual(score_res["rating"], "Excellent")
        self.assertTrue(any("protein" in ins.lower() for ins in score_res["insights"]))

        # Unhealthy product
        unhealthy_data = {
            "serving_size": 100.0,
            "sugars_g": 35.0,
            "saturated_fat_g": 12.0,
            "sodium_mg": 900.0,
            "protein_g": 1.0,
            "fiber_g": 0.0
        }
        score_res = calculate_health_score(unhealthy_data)
        self.assertLessEqual(score_res["health_score"], 40)
        self.assertIn(score_res["rating"], ["Poor", "Moderate"])
        self.assertTrue(any("sugar" in ins.lower() for ins in score_res["insights"]))
        self.assertTrue(any("sodium" in ins.lower() for ins in score_res["insights"]))

    def test_age_based_scoring_scaling(self):
        # A toddler has much lower sugar tolerance than an adult.
        # Let's test a product with 12g sugar per 100g.
        # For adults, 12g sugar is moderate (penalty is lower).
        # For toddlers, 12g sugar (toddler limit is 25g vs adult 50g, ratio is 0.5)
        # 12g is > 10 * 0.5 (5g), so it triggers high or moderate sugar penalties.
        # Let's verify that the health score is lower for a toddler compared to an adult.
        sugar_data = {
            "serving_size": 100.0,
            "sugars_g": 12.0
        }
        adult_res = calculate_health_score(sugar_data, user_profile={"age": 30})
        toddler_res = calculate_health_score(sugar_data, user_profile={"age": 2})
        self.assertGreater(adult_res["health_score"], toddler_res["health_score"])

    def test_personalization_diabetic(self):
        # Diabetic profile gets penalized if sugars_g > 10g/100g
        sweet_data = {
            "serving_size": 100.0,
            "sugars_g": 15.0
        }
        scorer = NutriScorer()
        normal_score = scorer.get_final_score(sweet_data, user_profile={"is_diabetic": False})["health_score"]
        diabetic_score = scorer.get_final_score(sweet_data, user_profile={"is_diabetic": True})["health_score"]
        # Diabetic penalty should be applied
        self.assertGreater(normal_score, diabetic_score)

    def test_personalization_high_bp(self):
        # High BP profile gets penalized if sodium_mg > 300mg/100g
        salty_data = {
            "serving_size": 100.0,
            "sodium_mg": 400.0
        }
        scorer = NutriScorer()
        normal_score = scorer.get_final_score(salty_data, user_profile={"has_high_bp": False})["health_score"]
        high_bp_score = scorer.get_final_score(salty_data, user_profile={"has_high_bp": True})["health_score"]
        self.assertGreater(normal_score, high_bp_score)

    def test_personalization_heart_condition(self):
        # Heart condition profile gets penalized for high saturated fat / cholesterol
        heart_data = {
            "serving_size": 100.0,
            "saturated_fat_g": 4.0,
            "cholesterol_mg": 60.0
        }
        scorer = NutriScorer()
        normal_score = scorer.get_final_score(heart_data, user_profile={"heart_condition": False})["health_score"]
        heart_score = scorer.get_final_score(heart_data, user_profile={"heart_condition": True})["health_score"]
        self.assertGreater(normal_score, heart_score)

    def test_personalization_weight_loss(self):
        # Weight loss profile gets penalized for high calories (>250 kcal/100g)
        caloric_data = {
            "serving_size": 100.0,
            "energy_kcal": 300.0
        }
        scorer = NutriScorer()
        normal_score = scorer.get_final_score(caloric_data, user_profile={"weight_loss_goal": False})["health_score"]
        weight_loss_score = scorer.get_final_score(caloric_data, user_profile={"weight_loss_goal": True})["health_score"]
        self.assertGreater(normal_score, weight_loss_score)

    def test_personalization_vegan(self):
        # Vegan profile gets penalized for presence of cholesterol (>0 mg)
        non_vegan_data = {
            "serving_size": 100.0,
            "cholesterol_mg": 10.0
        }
        scorer = NutriScorer()
        normal_score = scorer.get_final_score(non_vegan_data, user_profile={"is_vegan": False})["health_score"]
        vegan_score = scorer.get_final_score(non_vegan_data, user_profile={"is_vegan": True})["health_score"]
        self.assertGreater(normal_score, vegan_score)

    def test_daily_budget_penalties_and_warnings(self):
        # Test daily totals warnings and penalties
        nutrition_data = {
            "serving_size": 100.0,
            "sugars_g": 10.0
        }
        scorer = NutriScorer()
        
        # Scenario A: Daily intake of sugar is below limit
        res_ok = scorer.get_final_score(
            nutrition_data,
            user_profile={"age": 30},
            daily_totals={"sugars_g": 5.0}
        )
        
        # Scenario B: Daily intake of sugar already exceeds limit (50g for adult)
        res_exceeded = scorer.get_final_score(
            nutrition_data,
            user_profile={"age": 30},
            daily_totals={"sugars_g": 60.0}
        )
        
        self.assertGreater(res_ok["health_score"], res_exceeded["health_score"])
        self.assertTrue(any("Limit Exceeded" in item["message"] for item in res_exceeded["flags"]))

if __name__ == "__main__":
    unittest.main()
