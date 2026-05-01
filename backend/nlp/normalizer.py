def normalize_to_100g(nutrition_data):
    """
    Converts all nutrients to per 100g basis
    """

    if "serving_size_g" not in nutrition_data:
        # If no serving size, assume already per 100g
        return nutrition_data

    serving_size = nutrition_data["serving_size_g"]

    if serving_size == 0:
        return nutrition_data

    normalized = {}

    for key, value in nutrition_data.items():
        if key == "serving_size_g":
            continue

        if isinstance(value, (int, float)):
            normalized[key] = round((value / serving_size) * 100, 2)

    normalized["basis"] = "per_100g"

    return normalized