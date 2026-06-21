"""
Feature Engineering — NutriScan ML Pipeline
Converts flat nutrition dict (pipeline schema) into ML feature vector.
Fixed to match pipeline schema keys: energy_kcal, fat_g, protein_g, etc.
"""


# WHO Nutri-Score A-nutrient limits (per 100g)
# Higher → more penalty
WHO_A_THRESHOLDS = {
    "energy_kcal": [335, 670, 1005, 1340, 1675, 2010, 2345, 2680, 3015, 3350],
    "sugars_g":    [4.5, 9.0, 13.5, 18.0, 22.5, 27.0, 31.0, 36.0, 40.0, 45.0],
    "saturated_fat_g": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
    "sodium_mg":   [90, 180, 270, 360, 450, 540, 630, 720, 810, 900],
}

# WHO Nutri-Score C-nutrient limits (per 100g)
# Higher → more benefit
WHO_C_THRESHOLDS = {
    "fiber_g":    [0.9, 1.9, 2.8, 3.7, 4.7],
    "protein_g":  [1.6, 3.2, 4.8, 6.4, 8.0],
}


def _score_nutrient(value: float, thresholds: list) -> int:
    """Returns number of thresholds exceeded (0 = best, len = worst)."""
    score = 0
    for t in thresholds:
        if value > t:
            score += 1
    return score


def calculate_features(nutrition_data: dict) -> dict:
    """
    Compute ML feature vector from the pipeline's flat nutrition dict.
    All values are normalized per-100g using serving_size where available.

    Returns a dict with 12 features ready for the ML model.
    """
    serving = nutrition_data.get("serving_size") or 100.0

    def per100g(key: str) -> float:
        val = nutrition_data.get(key)
        if val is None:
            return 0.0
        return (val / serving) * 100.0

    # --- Raw per-100g values ---
    energy   = per100g("energy_kcal")
    fat      = per100g("fat_g")
    sat_fat  = per100g("saturated_fat_g")
    trans_fat= per100g("trans_fat_g")
    carbs    = per100g("carbohydrates_g")
    sugar    = per100g("sugars_g")
    added_sg = per100g("added_sugars_g")
    fiber    = per100g("fiber_g")
    protein  = per100g("protein_g")
    sodium   = per100g("sodium_mg")

    features = {}

    # 1. Energy density (kcal per 100g, normalised to 0–1 over max 900 kcal)
    features["energy_density"] = min(energy / 900.0, 1.0)

    # 2. Sugar density (sugar / carbs ratio) — penalises sugary carbs
    features["sugar_density"] = round(sugar / carbs, 4) if carbs > 0 else 0.0

    # 3. Fat ratio (fat calories / total calories)
    fat_kcal = fat * 9.0
    features["fat_ratio"] = round(fat_kcal / energy, 4) if energy > 0 else 0.0

    # 4. Saturated fat ratio (sat fat / total fat)
    features["saturated_fat_ratio"] = round(sat_fat / fat, 4) if fat > 0 else 0.0

    # 5. Sodium density (normalised, per 100g, max 2400 mg)
    features["sodium_density"] = min(sodium / 2400.0, 1.0)

    # 6. Fiber ratio (fiber / carbs) — rewards fiber-rich carbs
    features["fiber_ratio"] = round(fiber / carbs, 4) if carbs > 0 else 0.0

    # 7. Protein ratio (protein calories / total calories)
    protein_kcal = protein * 4.0
    features["protein_ratio"] = round(protein_kcal / energy, 4) if energy > 0 else 0.0

    # 8. Nutrient completeness (fraction of 8 key nutrients present)
    key_nutrients = [
        "energy_kcal", "fat_g", "saturated_fat_g", "sodium_mg",
        "carbohydrates_g", "fiber_g", "sugars_g", "protein_g"
    ]
    present = sum(1 for k in key_nutrients if nutrition_data.get(k) is not None)
    features["nutrient_completeness_score"] = round(present / len(key_nutrients), 2)

    # 9. WHO Nutri-Score A points (0–40, higher = worse)
    a_pts = (
        _score_nutrient(energy,  WHO_A_THRESHOLDS["energy_kcal"])
        + _score_nutrient(sugar, WHO_A_THRESHOLDS["sugars_g"])
        + _score_nutrient(sat_fat, WHO_A_THRESHOLDS["saturated_fat_g"])
        + _score_nutrient(sodium, WHO_A_THRESHOLDS["sodium_mg"])
    )
    features["who_a_points"] = a_pts / 40.0  # normalised 0–1

    # 10. WHO Nutri-Score C points (0–10, higher = better)
    c_pts = (
        _score_nutrient(fiber,   WHO_C_THRESHOLDS["fiber_g"])
        + _score_nutrient(protein, WHO_C_THRESHOLDS["protein_g"])
    )
    features["who_c_points"] = c_pts / 10.0  # normalised 0–1

    # 11. Trans fat flag (binary: 0 or 1)
    features["trans_fat_flag"] = 1.0 if trans_fat > 0.1 else 0.0

    # 12. Added-sugar ratio (added_sugar / total_sugar)
    features["added_sugar_ratio"] = round(added_sg / sugar, 4) if sugar > 0 else 0.0

    return features
