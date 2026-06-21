"""
Bounds Validator — NutriScan
=============================
Stage 9: Validates nutrition data against:
  1. Physical per-serving bounds
  2. Semantic cross-field consistency checks
  3. Energy macro consistency (computed vs stated kcal)
  4. Auto-correction of obvious extraction errors
"""


# Per-serving plausible bounds (not per-100g — servings vary widely)
_BOUNDS = {
    "energy_kcal":      (0.0,  2500.0),
    "protein_g":        (0.0,   200.0),
    "carbohydrates_g":  (0.0,   300.0),
    "sugars_g":         (0.0,   200.0),
    "added_sugars_g":   (0.0,   200.0),
    "fat_g":            (0.0,   200.0),
    "saturated_fat_g":  (0.0,   150.0),
    "trans_fat_g":      (0.0,    50.0),
    "fiber_g":          (0.0,   100.0),
    "sodium_mg":        (0.0, 15000.0),
    "cholesterol_mg":   (0.0,  3000.0),
    "serving_size":     (1.0,  1500.0),
}


def validate_bounds(nutrition_data: dict) -> dict:
    """
    Stage 9: Validate flat nutrition dict.

    Returns:
        {
            "is_valid":   bool,
            "flags":      list[dict],   # validation warnings
            "corrected":  dict,         # auto-corrected values (subset of nutrition_data)
        }
    """
    flags     = []
    corrected = {}

    # ------------------------------------------------------------------
    # 1. Physical per-serving bounds
    # ------------------------------------------------------------------
    for key, (lo, hi) in _BOUNDS.items():
        val = nutrition_data.get(key)
        if val is None:
            continue
        if not (lo <= val <= hi):
            flags.append({
                "field":  key,
                "issue":  "out_of_range",
                "reason": f"Value {val} outside plausible range ({lo}–{hi})"
            })

    # ------------------------------------------------------------------
    # 2. Semantic cross-field consistency
    # ------------------------------------------------------------------
    fat      = nutrition_data.get("fat_g")
    sat_fat  = nutrition_data.get("saturated_fat_g")
    trans    = nutrition_data.get("trans_fat_g")
    carbs    = nutrition_data.get("carbohydrates_g")
    sugar    = nutrition_data.get("sugars_g")
    added_sg = nutrition_data.get("added_sugars_g")
    fiber    = nutrition_data.get("fiber_g")

    # Saturated fat must not exceed total fat
    if sat_fat is not None and fat is not None:
        if sat_fat > fat * 1.05:          # 5% tolerance for rounding
            # Auto-correct: cap sat_fat at fat
            corrected["saturated_fat_g"] = round(fat, 2)
            flags.append({
                "field":  "saturated_fat_g",
                "issue":  "exceeds_parent",
                "reason": (
                    f"Saturated fat ({sat_fat}g) > Total fat ({fat}g). "
                    f"Auto-corrected to {fat}g."
                )
            })

    # Trans fat must not exceed total fat
    if trans is not None and fat is not None:
        if trans > fat * 1.05:
            corrected["trans_fat_g"] = round(fat, 2)
            flags.append({
                "field":  "trans_fat_g",
                "issue":  "exceeds_parent",
                "reason": (
                    f"Trans fat ({trans}g) > Total fat ({fat}g). "
                    f"Auto-corrected to {fat}g."
                )
            })

    # Sugars must not exceed total carbohydrates
    if sugar is not None and carbs is not None:
        if sugar > carbs * 1.05:
            corrected["sugars_g"] = round(carbs, 2)
            flags.append({
                "field":  "sugars_g",
                "issue":  "exceeds_parent",
                "reason": (
                    f"Sugars ({sugar}g) > Total carbohydrates ({carbs}g). "
                    f"Auto-corrected to {carbs}g."
                )
            })

    # Added sugars must not exceed total sugars
    if added_sg is not None and sugar is not None:
        if added_sg > sugar * 1.05:
            corrected["added_sugars_g"] = round(sugar, 2)
            flags.append({
                "field":  "added_sugars_g",
                "issue":  "exceeds_parent",
                "reason": (
                    f"Added sugars ({added_sg}g) > Total sugars ({sugar}g). "
                    f"Auto-corrected to {sugar}g."
                )
            })

    # Fiber should not exceed total carbohydrates
    if fiber is not None and carbs is not None:
        if fiber > carbs * 1.05:
            corrected["fiber_g"] = round(carbs, 2)
            flags.append({
                "field":  "fiber_g",
                "issue":  "exceeds_parent",
                "reason": (
                    f"Fiber ({fiber}g) > Carbohydrates ({carbs}g). "
                    f"Auto-corrected to {carbs}g."
                )
            })

    # ------------------------------------------------------------------
    # 3. Energy macro consistency check (4-4-9 rule)
    #    Computed kcal = protein×4 + carbs×4 + fat×9
    #    If stated energy differs by >30% → flag as likely OCR error
    # ------------------------------------------------------------------
    stated_kcal = nutrition_data.get("energy_kcal")
    protein_g   = nutrition_data.get("protein_g")

    if stated_kcal and protein_g is not None and carbs is not None and fat is not None:
        computed_kcal = (protein_g * 4.0) + (carbs * 4.0) + (fat * 9.0)
        if computed_kcal > 0:
            pct_diff = abs(stated_kcal - computed_kcal) / computed_kcal
            if pct_diff > 0.30:
                flags.append({
                    "field":  "energy_kcal",
                    "issue":  "macro_inconsistency",
                    "reason": (
                        f"Stated energy ({stated_kcal:.0f} kcal) differs from "
                        f"macro-computed energy ({computed_kcal:.0f} kcal) by "
                        f"{pct_diff*100:.0f}%. Possible OCR error or fibre adjustment."
                    )
                })

    # ------------------------------------------------------------------
    # 4. Apply auto-corrections back into a clean dict
    # ------------------------------------------------------------------
    validated_data = dict(nutrition_data)
    validated_data.update(corrected)

    return {
        "is_valid":  len(flags) == 0,
        "flags":     flags,
        "corrected": corrected,
        # Return the auto-corrected data so the pipeline can use it
        "data":      validated_data,
    }
