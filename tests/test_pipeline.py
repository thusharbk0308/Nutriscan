import unittest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.nutrient_parser import extract_nutrition
from validator.bounds_validator import validate_bounds
from scoring.rule_scorer import calculate_health_score

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

if __name__ == "__main__":
    unittest.main()
