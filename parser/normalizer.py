def normalize_to_100g(nutrition_data: dict) -> dict:
    """
    Converts all extracted nutrients to a standard per 100g/ml basis.
    Requires a valid serving size in grams or ml.
    Accepts flat nutrition dictionary {key: value_float_or_null}.
    """
    normalized = {}

    serving_size_val = nutrition_data.get("serving_size")
    if not serving_size_val or serving_size_val <= 0:
        # If no serving size is found, we cannot normalize. Return original as is.
        for key, val in nutrition_data.items():
            if key != "serving_size":
                normalized[key] = val
        return {
            "data": normalized,
            "basis": "unknown",
            "message": "Serving size missing or invalid. Could not normalize."
        }

    # If already 100g/ml, just copy over
    if serving_size_val == 100.0:
        for key, val in nutrition_data.items():
            if key != "serving_size":
                normalized[key] = val
        return {
            "data": normalized,
            "basis": "per_100g",
            "message": "Data is already per 100g/ml."
        }

    # Normalize values
    for key, val in nutrition_data.items():
        if key == "serving_size":
            continue

        if val is None:
            normalized[key] = None
        else:
            # Convert to per 100g basis
            normalized[key] = round((val / serving_size_val) * 100, 2)

    return {
        "data": normalized,
        "basis": "per_100g",
        "message": f"Normalized from {serving_size_val}g to 100g basis."
    }