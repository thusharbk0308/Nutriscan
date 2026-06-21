"""
Integration tests for the NutriScan FastAPI /analyze endpoint.

Creates a realistic-size synthetic nutrition label (600×800 px, 1.5pt text)
that EasyOCR can reliably detect, then validates the exact response schema
specified in the master prompt.
"""
import os
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api.server import app

DUMMY_PATH = "tests/temp_dummy.jpg"


def _make_label_image(path: str) -> None:
    """
    Create a white 600×800 nutrition-label image with large, clear text
    so that the OCR engine (EasyOCR fallback) can detect every field.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img   = np.full((800, 600, 3), 255, dtype=np.uint8)
    font  = cv2.FONT_HERSHEY_SIMPLEX
    black = (0, 0, 0)

    lines = [
        ("Nutrition Facts",     (60, 60),  1.2, 2),
        ("Serving Size 100 g",  (60, 130), 1.0, 2),
        ("Calories 250 kcal",   (60, 210), 1.0, 2),
        ("Total Fat 8 g",       (60, 290), 1.0, 2),
        ("Saturated Fat 3 g",   (60, 370), 1.0, 2),
        ("Sodium 400 mg",       (60, 450), 1.0, 2),
        ("Total Carbohydrate 30 g", (60, 530), 1.0, 2),
        ("Dietary Fiber 4 g",   (60, 610), 1.0, 2),
        ("Total Sugars 12 g",   (60, 690), 1.0, 2),
        ("Protein 15 g",        (60, 770), 1.0, 2),
    ]
    for text, org, scale, thickness in lines:
        cv2.putText(img, text, org, font, scale, black, thickness, cv2.LINE_AA)

    cv2.imwrite(path, img)


class TestAPIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _make_label_image(DUMMY_PATH)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(DUMMY_PATH):
            os.remove(DUMMY_PATH)

    def test_analyze_returns_200(self):
        with open(DUMMY_PATH, "rb") as f:
            response = self.client.post(
                "/analyze",
                files={"file": ("temp_dummy.jpg", f, "image/jpeg")}
            )
        self.assertEqual(response.status_code, 200)

    def test_response_has_required_keys(self):
        """Verify the strict master-prompt response schema."""
        with open(DUMMY_PATH, "rb") as f:
            data = self.client.post(
                "/analyze",
                files={"file": ("temp_dummy.jpg", f, "image/jpeg")}
            ).json()

        for key in ("image_id", "ocr_confidence", "nutrition_data",
                    "health_score", "rating", "warnings", "insights"):
            self.assertIn(key, data, f"Missing required key: '{key}'")

    def test_nutrition_data_schema(self):
        """All 12 nutrition_data keys must be present (value may be null)."""
        with open(DUMMY_PATH, "rb") as f:
            data = self.client.post(
                "/analyze",
                files={"file": ("temp_dummy.jpg", f, "image/jpeg")}
            ).json()

        expected_keys = [
            "serving_size", "energy_kcal", "protein_g", "carbohydrates_g",
            "sugars_g", "added_sugars_g", "fat_g", "saturated_fat_g",
            "trans_fat_g", "fiber_g", "sodium_mg", "cholesterol_mg",
        ]
        nutrition = data["nutrition_data"]
        for k in expected_keys:
            self.assertIn(k, nutrition, f"Missing nutrition key: '{k}'")

    def test_frontend_compat_keys(self):
        """Legacy frontend keys must still be present for the dashboard."""
        with open(DUMMY_PATH, "rb") as f:
            data = self.client.post(
                "/analyze",
                files={"file": ("temp_dummy.jpg", f, "image/jpeg")}
            ).json()

        self.assertEqual(data["status"], "success")
        self.assertIn("raw_nutrition", data)
        self.assertIn("final_result", data)

    def test_ocr_detects_calories(self):
        """At minimum, the OCR should detect the clearly-printed Calories line."""
        with open(DUMMY_PATH, "rb") as f:
            data = self.client.post(
                "/analyze",
                files={"file": ("temp_dummy.jpg", f, "image/jpeg")}
            ).json()

        energy = data["nutrition_data"].get("energy_kcal")
        self.assertIsNotNone(
            energy,
            "OCR failed to detect Calories — image or pipeline may be broken."
        )
        self.assertEqual(energy, 250.0)

    def test_health_score_range(self):
        """Health score must be an integer in [0, 100]."""
        with open(DUMMY_PATH, "rb") as f:
            data = self.client.post(
                "/analyze",
                files={"file": ("temp_dummy.jpg", f, "image/jpeg")}
            ).json()

        score = data["health_score"]
        self.assertIsInstance(score, int)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_rating_is_valid(self):
        """Rating must be one of the four defined classes."""
        with open(DUMMY_PATH, "rb") as f:
            data = self.client.post(
                "/analyze",
                files={"file": ("temp_dummy.jpg", f, "image/jpeg")}
            ).json()

        self.assertIn(
            data["rating"],
            ("Excellent", "Good", "Moderate", "Poor")
        )


if __name__ == "__main__":
    unittest.main()
