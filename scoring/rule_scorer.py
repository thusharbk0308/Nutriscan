"""
Rule Scorer — NutriScan
========================
Stage 10: Health Score Engine   (rule-based component)
Stage 11: Insight Generator     (AI-enhanced with Gemini fallback)

Uses FSA Nutrient Profiling Model-inspired thresholds (per 100g).
Provides rich, actionable insight messages and optional Gemini AI insights.
"""

import os
import json
import base64
import requests


# ---------------------------------------------------------------------------
# FSA / WHO Threshold tables (all per 100g)
# ---------------------------------------------------------------------------
# Sugar thresholds: high > 22.5g, moderate > 10g
# Saturated fat:   high > 5.0g,  moderate > 2.5g
# Sodium:          high > 600mg, moderate > 300mg
# Trans fat:       any > 0.1g is flagged
# Protein:         good > 10g,   moderate > 5g
# Fiber:           good > 6g,    moderate > 3g
# Calories:        high > 500 kcal/100g (energy-dense)


def _per100g(nutrition_data: dict, key: str) -> float:
    """Return value normalised to per-100g using serving_size."""
    val = nutrition_data.get(key)
    if val is None:
        return 0.0
    serving = nutrition_data.get("serving_size")
    if serving and serving > 0:
        return (val / serving) * 100.0
    return float(val)


def calculate_health_score(nutrition_data: dict) -> dict:
    """
    Stage 10 & 11: Calculate rule-based health score (0–100) and generate insights.

    Scoring uses FSA Nutrient Profiling Model-inspired thresholds (per 100g):
      - A-nutrients (penalise): energy, sugar, saturated fat, sodium, trans fat
      - C-nutrients (reward):   protein, fiber
    """
    sugar    = _per100g(nutrition_data, "sugars_g")
    added_sg = _per100g(nutrition_data, "added_sugars_g")
    sat_fat  = _per100g(nutrition_data, "saturated_fat_g")
    sodium   = _per100g(nutrition_data, "sodium_mg")
    trans    = _per100g(nutrition_data, "trans_fat_g")
    protein  = _per100g(nutrition_data, "protein_g")
    fiber    = _per100g(nutrition_data, "fiber_g")
    carbs    = _per100g(nutrition_data, "carbohydrates_g")
    energy   = _per100g(nutrition_data, "energy_kcal")
    chol     = _per100g(nutrition_data, "cholesterol_mg")

    base_score = 70.0  # Neutral FSA-aligned starting point

    # ---- A-nutrient penalties ----
    # 1. Total sugars
    if sugar > 22.5:
        base_score -= 22
    elif sugar > 10.0:
        base_score -= 10

    # 2. Added sugars (extra penalty on top of total sugar)
    if added_sg > 10.0:
        base_score -= 12
    elif added_sg > 5.0:
        base_score -= 6

    # 3. Saturated fat
    if sat_fat > 5.0:
        base_score -= 15
    elif sat_fat > 2.5:
        base_score -= 7

    # 4. Sodium
    if sodium > 600.0:
        base_score -= 18
    elif sodium > 300.0:
        base_score -= 8

    # 5. Trans fat (hard penalty — any detectable amount)
    if trans > 1.0:
        base_score -= 25
    elif trans > 0.5:
        base_score -= 18
    elif trans > 0.1:
        base_score -= 10

    # 6. High caloric density
    if energy > 500:
        base_score -= 8
    elif energy > 350:
        base_score -= 4

    # 7. Cholesterol
    if chol > 100:
        base_score -= 8
    elif chol > 50:
        base_score -= 4

    # ---- C-nutrient bonuses ----
    # 1. Protein
    if protein > 15.0:
        base_score += 15
    elif protein > 10.0:
        base_score += 10
    elif protein > 5.0:
        base_score += 5

    # 2. Dietary fiber
    if fiber > 6.0:
        base_score += 15
    elif fiber > 3.0:
        base_score += 8
    elif fiber > 1.5:
        base_score += 3

    # Clamp
    score = int(max(0, min(100, round(base_score))))

    # ---- Rating ----
    if score >= 80:
        rating = "Excellent"
    elif score >= 60:
        rating = "Good"
    elif score >= 40:
        rating = "Moderate"
    else:
        rating = "Poor"

    # ---- Stage 11: Insight Generation ----
    insights = _generate_insights(
        score=score,
        sugar=sugar, added_sg=added_sg, sat_fat=sat_fat,
        sodium=sodium, trans=trans, protein=protein,
        fiber=fiber, carbs=carbs, energy=energy, chol=chol,
        nutrition_data=nutrition_data,
    )

    return {
        "health_score": score,
        "rating":       rating,
        "insights":     insights,
    }


def _generate_insights(
    score, sugar, added_sg, sat_fat, sodium, trans,
    protein, fiber, carbs, energy, chol, nutrition_data: dict
) -> list[str]:
    """
    Generate specific, actionable, evidence-based insight strings.
    Tries Gemini AI first; falls back to deterministic rules.
    """
    # Try Gemini-enhanced insights
    gemini_insights = _gemini_insights(nutrition_data, score)
    if gemini_insights:
        return gemini_insights

    # ---- Deterministic rule-based fallback ----
    insights = []

    # Energy density
    if energy > 500:
        insights.append(
            f"Very high energy density ({energy:.0f} kcal/100g). "
            "Limit portion size to manage caloric intake."
        )
    elif energy > 350:
        insights.append(
            f"Moderate-high caloric density ({energy:.0f} kcal/100g). "
            "Be mindful of serving size."
        )

    # Sugars
    if sugar > 22.5:
        insights.append(
            f"High sugar content ({sugar:.1f}g/100g — above 22.5g FSA threshold). "
            "Frequent consumption may contribute to tooth decay and blood sugar spikes."
        )
    elif sugar > 10.0:
        insights.append(f"Moderate sugar level ({sugar:.1f}g/100g). Consume in moderation.")

    # Added sugars
    if added_sg > 10.0:
        insights.append(
            f"High added sugars ({added_sg:.1f}g/100g). "
            "WHO recommends keeping added sugars below 5% of total energy intake."
        )
    elif added_sg > 5.0:
        insights.append(f"Moderate added sugars ({added_sg:.1f}g/100g).")

    # Saturated fat
    if sat_fat > 5.0:
        insights.append(
            f"High saturated fat ({sat_fat:.1f}g/100g). "
            "Elevated saturated fat raises LDL cholesterol — limit to protect heart health."
        )
    elif sat_fat > 2.5:
        insights.append(f"Moderate saturated fat ({sat_fat:.1f}g/100g). Keep daily intake below 20g.")

    # Trans fat
    if trans > 0.5:
        insights.append(
            f"Contains significant trans fat ({trans:.2f}g/100g). "
            "WHO advises zero trans fat intake — linked to heart disease risk."
        )
    elif trans > 0.1:
        insights.append(
            f"Contains trace trans fat ({trans:.2f}g/100g). Limit consumption."
        )

    # Sodium
    if sodium > 600.0:
        insights.append(
            f"Very high sodium ({sodium:.0f}mg/100g). "
            "Exceeds FSA high threshold. May contribute to hypertension if consumed regularly."
        )
    elif sodium > 300.0:
        insights.append(f"Moderate sodium ({sodium:.0f}mg/100g). Keep daily total below 2000mg.")

    # Cholesterol
    if chol > 100:
        insights.append(
            f"High cholesterol content ({chol:.0f}mg/100g). "
            "Limit if managing cardiovascular risk."
        )

    # Protein
    if protein > 15.0:
        insights.append(
            f"Excellent protein source ({protein:.1f}g/100g). "
            "Supports muscle repair, satiety and metabolic health."
        )
    elif protein > 10.0:
        insights.append(f"Good protein content ({protein:.1f}g/100g).")
    elif protein > 5.0:
        insights.append(f"Moderate protein source ({protein:.1f}g/100g).")

    # Fiber
    if fiber > 6.0:
        insights.append(
            f"High dietary fiber ({fiber:.1f}g/100g). "
            "Promotes gut health and sustained energy release."
        )
    elif fiber > 3.0:
        insights.append(f"Good fiber content ({fiber:.1f}g/100g).")
    elif fiber < 1.0 and carbs > 20.0:
        insights.append(
            "Low fiber relative to carbohydrate content. "
            "These carbs may cause rapid blood sugar rises."
        )

    # Post-workout suitability
    if protein > 10.0 and carbs > 15.0 and sugar < 15.0 and trans < 0.1:
        insights.append("Nutritional profile suitable as a post-workout recovery snack.")

    # Overall positive
    if score >= 80 and not insights:
        insights.append("Well-balanced nutritional profile. A healthy everyday choice.")
    elif score >= 60 and not insights:
        insights.append("Reasonably balanced nutrition. Fine for regular consumption.")

    return insights


def _gemini_insights(nutrition_data: dict, score: int) -> list[str]:
    """
    Optional: Ask Gemini to generate 3 specific, actionable insights.
    Returns empty list if API key is absent or call fails.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return []

    # Build a compact nutrition summary to send (no image, just JSON text)
    serving = nutrition_data.get("serving_size", "unknown")
    compact = {k: v for k, v in nutrition_data.items()
               if v is not None and k != "_units"}

    prompt = (
        f"You are a clinical nutritionist. A food product has the following nutrition data "
        f"(per serving of {serving}g): {json.dumps(compact)}. "
        f"Its computed health score is {score}/100. "
        "Generate exactly 3 specific, concise, evidence-based insights for a consumer. "
        "Each insight must be one sentence. Focus on the most important positives and risks. "
        "Return ONLY a JSON array of 3 strings, no explanation."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "ARRAY",
                "items": {"type": "STRING"}
            }
        }
    }

    models = ["gemini-2.5-flash", "gemini-2.0-flash"]
    for model in models:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        try:
            resp = requests.post(url, json=payload,
                                 headers={"Content-Type": "application/json"},
                                 timeout=8)
            if resp.status_code == 200:
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                if isinstance(parsed, list) and len(parsed) >= 1:
                    return [str(s) for s in parsed[:5]]
        except Exception:
            continue

    return []
