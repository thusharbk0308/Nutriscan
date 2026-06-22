"""
Hybrid Scorer — NutriScan
=========================
Blends rule-based score (40%) + ML model score (60%) for the final health score.
Loads health_model.pkl once at class instantiation; gracefully falls back to
rules-only if the model file is missing or corrupt.
"""

import os
import pickle
import numpy as np

from scoring.rule_scorer import calculate_health_score
from features.feature_engineer import calculate_features
from parser.nutrient_parser import get_limits_for_age


# ---------------------------------------------------------------------------
# Feature keys — must stay in sync with models/train.py::FEATURE_KEYS
# ---------------------------------------------------------------------------
_FEATURE_KEYS = [
    "energy_density",
    "sugar_density",
    "fat_ratio",
    "saturated_fat_ratio",
    "sodium_density",
    "fiber_ratio",
    "protein_ratio",
    "nutrient_completeness_score",
    "who_a_points",
    "who_c_points",
    "trans_fat_flag",
    "added_sugar_ratio",
]

_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models", "health_model.pkl"
)


class NutriScorer:
    """
    Singleton-friendly scorer that loads the ML model once and reuses it.
    Falls back to pure rule-based scoring when the model is unavailable.
    """

    def __init__(self, model_path: str = _MODEL_PATH):
        self._model_data = None
        self._load_model(model_path)

    # ------------------------------------------------------------------
    def _load_model(self, path: str):
        try:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    self._model_data = pickle.load(f)
                print(f"[NutriScorer] ML model loaded from {path}")
            else:
                print(f"[NutriScorer] Model not found at {path}. Using rules only.")
        except Exception as e:
            print(f"[NutriScorer] Could not load ML model: {e}. Using rules only.")
            self._model_data = None

    # ------------------------------------------------------------------
    def _ml_predict(self, nutrition_data: dict) -> float | None:
        """
        Compute ML health score (0–1) from nutrition_data.
        Returns None when model is unavailable.
        """
        if self._model_data is None:
            return None

        try:
            features = calculate_features(nutrition_data)
            xgb_m  = self._model_data.get("xgb")
            gb_m   = self._model_data.get("gb")
            rf_m   = self._model_data.get("rf")
            meta_m = self._model_data.get("meta")
            scaler = self._model_data.get("scaler")

            if gb_m is None or meta_m is None or scaler is None:
                return None

            x = np.array([[features.get(k, 0.0) for k in _FEATURE_KEYS]], dtype=np.float32)
            x_s = scaler.transform(x)

            xgb_p = float(xgb_m.predict(x_s)[0]) if xgb_m is not None else 0.0
            gb_p  = float(gb_m.predict(x_s)[0])
            rf_p  = float(rf_m.predict(x_s)[0]) if rf_m is not None else gb_p

            meta_x = np.array([[xgb_p, gb_p, rf_p]])
            score  = float(meta_m.predict(meta_x)[0])
            return float(np.clip(score, 0.0, 1.0))

        except Exception as e:
            print(f"[NutriScorer] ML prediction error: {e}. Falling back to rules.")
            return None

    # ------------------------------------------------------------------
    def get_final_score(
        self,
        nutrition_data: dict,
        features: dict = None,
        user_profile: dict = None,
        daily_totals: dict = None,
    ) -> dict:
        """
        Compute final blended health score.

        Blend: 40% rule-based + 60% ML model (falls back to 100% rules if ML unavailable).

        Returns a dict compatible with the existing API layer:
          final_health_score, risk_level, rating, insights, components, flags
        """
        # --- Rule-based score (0–100) ---
        rule_result = calculate_health_score(nutrition_data, user_profile=user_profile)
        rule_score_01 = rule_result["health_score"] / 100.0

        # --- ML score (0–1) ---
        ml_score_01 = self._ml_predict(nutrition_data)

        if ml_score_01 is not None:
            # 40% rules + 60% ML
            blended = 0.40 * rule_score_01 + 0.60 * ml_score_01
            ml_used = True
        else:
            blended = rule_score_01
            ml_used = False

        blended = float(np.clip(blended, 0.0, 1.0))
        final_score_100 = int(round(blended * 100))

        # --- Rating ---
        if final_score_100 >= 80:
            rating = "Excellent"
        elif final_score_100 >= 60:
            rating = "Good"
        elif final_score_100 >= 40:
            rating = "Moderate"
        else:
            rating = "Poor"

        # --- Risk level ---
        if rating in ("Excellent", "Good"):
            risk_level = "Low"
        elif rating == "Moderate":
            risk_level = "Moderate"
        else:
            risk_level = "High"

        # --- Apply personalization if profile provided ---
        if user_profile:
            blended = _apply_personalization(blended, nutrition_data, user_profile)
            blended = float(np.clip(blended, 0.0, 1.0))
            final_score_100 = int(round(blended * 100))

        insights = list(rule_result.get("insights", []))

        # --- Apply daily limit penalties and warnings if daily totals provided ---
        if daily_totals:
            blended, daily_insights = _apply_daily_limit_penalties(
                blended, nutrition_data, user_profile or {}, daily_totals
            )
            blended = float(np.clip(blended, 0.0, 1.0))
            final_score_100 = int(round(blended * 100))
            insights.extend(daily_insights)

            # Re-evaluate rating and risk level based on the updated score
            if final_score_100 >= 80:
                rating = "Excellent"
            elif final_score_100 >= 60:
                rating = "Good"
            elif final_score_100 >= 40:
                rating = "Moderate"
            else:
                rating = "Poor"

            if rating in ("Excellent", "Good"):
                risk_level = "Low"
            elif rating == "Moderate":
                risk_level = "Moderate"
            else:
                risk_level = "High"

        return {
            "final_health_score": blended,
            "health_score":       final_score_100,
            "risk_level":         risk_level,
            "rating":             rating,
            "insights":           insights,
            "components": {
                "rule_score": round(rule_score_01, 4),
                "ml_score":   round(ml_score_01, 4) if ml_score_01 is not None else None,
                "ml_used":    ml_used,
                "blended":    round(blended, 4),
            },
            "flags": [{"type": "risk" if ins.startswith("⚠️") else "info", "message": ins} for ins in insights],
        }



# ---------------------------------------------------------------------------
# Personalization helper (moved from personalization/adjustments.py)
# ---------------------------------------------------------------------------
def _apply_personalization(
    base_score: float,
    nutrition_data: dict,
    user_profile: dict,
) -> float:
    """
    Adjusts blended score (0–1) based on user health conditions.
    Each condition can apply up to -0.15 additional penalty.
    """
    serving = nutrition_data.get("serving_size") or 100.0
    def per100g(key):
        v = nutrition_data.get(key)
        return (v / serving) * 100.0 if v is not None else 0.0

    sugar    = per100g("sugars_g")
    sodium   = per100g("sodium_mg")
    sat_fat  = per100g("saturated_fat_g")
    chol     = per100g("cholesterol_mg")
    energy   = per100g("energy_kcal")
    trans    = per100g("trans_fat_g")

    penalty = 0.0

    # Diabetic — sugar critical
    if user_profile.get("is_diabetic"):
        if sugar > 22.5:
            penalty += 0.15
        elif sugar > 10.0:
            penalty += 0.08

    # High BP — sodium critical
    if user_profile.get("has_high_bp"):
        if sodium > 600:
            penalty += 0.15
        elif sodium > 300:
            penalty += 0.08

    # Heart condition — sat fat + cholesterol critical
    if user_profile.get("heart_condition"):
        if sat_fat > 5.0 or chol > 100:
            penalty += 0.15
        elif sat_fat > 2.5 or chol > 50:
            penalty += 0.08
        if trans > 0.1:
            penalty += 0.10

    # Weight loss goal — caloric density penalty
    if user_profile.get("weight_loss_goal"):
        if energy > 400:
            penalty += 0.10
        elif energy > 250:
            penalty += 0.05

    # Vegan — flag cholesterol presence
    if user_profile.get("is_vegan") and chol > 0:
        penalty += 0.05

    return base_score - penalty

def _apply_daily_limit_penalties(
    base_score: float,
    nutrition_data: dict,
    user_profile: dict,
    daily_totals: dict,
) -> tuple[float, list[str]]:
    """
    Adjusts the score and generates dynamic warnings if the user's daily consumption
    exceeds or approaches their profile-based limits.
    """
    age_limits = get_limits_for_age(user_profile.get("age"))
    limits = {
        "energy_kcal": age_limits.get("energy_kcal", 2000.0),
        "sugars_g": age_limits.get("sugars_g", 50.0),
        "sodium_mg": age_limits.get("sodium_mg", 2000.0),
        "saturated_fat_g": age_limits.get("saturated_fat_g", 20.0),
    }
    # Customize limits based on health conditions
    if user_profile.get("is_diabetic"):
        limits["sugars_g"] = 25.0
    if user_profile.get("has_high_bp") or user_profile.get("heart_condition"):
        limits["sodium_mg"] = 1500.0
    if user_profile.get("heart_condition"):
        limits["saturated_fat_g"] = 13.0
    if user_profile.get("weight_loss_goal"):
        limits["energy_kcal"] = 1600.0

    penalty = 0.0
    insights = []

    nutrient_labels = {
        "energy_kcal": ("Calories", "kcal"),
        "sugars_g": ("Sugar", "g"),
        "sodium_mg": ("Sodium", "mg"),
        "saturated_fat_g": ("Saturated Fat", "g")
    }

    for key, (label, unit) in nutrient_labels.items():
        val_new = nutrition_data.get(key)
        if val_new is None or val_new <= 0:
            continue
        
        current_today = daily_totals.get(key, 0.0) or 0.0
        limit = limits[key]
        future_total = current_today + val_new

        if current_today >= limit:
            # Already exceeded limit
            penalty += 0.15
            insights.append(
                f"⚠️ Limit Exceeded: You have already eaten {current_today:.0f}{unit} of {label} today, exceeding your daily limit of {limit:.0f}{unit}. Consuming this is highly discouraged."
            )
        elif future_total > limit:
            # Consuming this will exceed limit
            penalty += 0.10
            insights.append(
                f"⚠️ Budget Exceeded: Eating this will push your daily {label} to {future_total:.0f}{unit}, exceeding your limit of {limit:.0f}{unit}."
            )
        elif future_total > 0.8 * limit:
            # Consuming this will approach limit (above 80%)
            penalty += 0.05
            pct = (future_total / limit) * 100
            insights.append(
                f"⚠️ High Intake: Consuming this will bring you close to your daily {label} limit ({pct:.0f}% of limit used)."
            )

    return base_score - penalty, insights

