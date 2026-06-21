"""
Personalization Engine — NutriScan
=====================================
Adjusts the hybrid health score (0–1) based on the user's specific
health profile stored in the SQLite users DB.

NOTE: The primary entry point for personalization in the live pipeline is
      scoring/hybrid_scorer.py::_apply_personalization(). This module
      provides the same logic as a standalone importable function for
      testing and future extensions.
"""


def apply_personalization(
    base_score: float,
    nutrition_data: dict,
    user_profile: dict,
) -> float:
    """
    Adjust blended health score (0–1) based on user health conditions.

    Args:
        base_score:     Current blended score from hybrid_scorer (0–1).
        nutrition_data: Flat nutrition dict from the pipeline.
        user_profile:   Dict with boolean keys: is_diabetic, has_high_bp,
                        heart_condition, weight_loss_goal, is_vegan.

    Returns:
        Adjusted score, clamped to [0.0, 1.0].
    """
    serving = nutrition_data.get("serving_size") or 100.0

    def per100g(key: str) -> float:
        v = nutrition_data.get(key)
        return (v / serving) * 100.0 if v is not None else 0.0

    sugar   = per100g("sugars_g")
    sodium  = per100g("sodium_mg")
    sat_fat = per100g("saturated_fat_g")
    chol    = per100g("cholesterol_mg")
    energy  = per100g("energy_kcal")
    trans   = per100g("trans_fat_g")

    penalty = 0.0

    # --- Diabetic: sugar is critical ---
    if user_profile.get("is_diabetic"):
        if sugar > 22.5:
            penalty += 0.15
        elif sugar > 10.0:
            penalty += 0.08

    # --- Hypertension: sodium is critical ---
    if user_profile.get("has_high_bp"):
        if sodium > 600:
            penalty += 0.15
        elif sodium > 300:
            penalty += 0.08

    # --- Heart condition: sat fat + cholesterol + trans fat critical ---
    if user_profile.get("heart_condition"):
        if sat_fat > 5.0 or chol > 100:
            penalty += 0.15
        elif sat_fat > 2.5 or chol > 50:
            penalty += 0.08
        if trans > 0.1:
            penalty += 0.10

    # --- Weight loss goal: caloric density penalty ---
    if user_profile.get("weight_loss_goal"):
        if energy > 400:
            penalty += 0.10
        elif energy > 250:
            penalty += 0.05

    # --- Vegan: flag presence of cholesterol (implies animal products) ---
    if user_profile.get("is_vegan") and chol > 0:
        penalty += 0.05

    adjusted = base_score - penalty
    return float(max(0.0, min(1.0, adjusted)))
