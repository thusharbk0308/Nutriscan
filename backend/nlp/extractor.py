import re

def extract_nutrition(text):
    data = {}

    # Calories
    calories = re.search(r'Calories\s*(\d+)', text, re.IGNORECASE)
    if calories:
        data['calories'] = int(calories.group(1))

    # Total Fat
    fat = re.search(r'Total Fat\s*(\d+)g', text, re.IGNORECASE)
    if fat:
        data['fat_g'] = int(fat.group(1))

    # Saturated Fat
    sat_fat = re.search(r'Saturated Fat\s*(\d+)g', text, re.IGNORECASE)
    if sat_fat:
        data['saturated_fat_g'] = int(sat_fat.group(1))

    # Sugar (handles "Total Sugars")
    sugar = re.search(r'(Total )?Sugars\s*(\d+)g', text, re.IGNORECASE)
    if sugar:
        data['sugar_g'] = int(sugar.group(2))

    # Protein
    protein = re.search(r'Protein\s*(\d+)g', text, re.IGNORECASE)
    if protein:
        data['protein_g'] = int(protein.group(1))

    # Sodium
    sodium = re.search(r'Sodium\s*(\d+)[oO]?mg', text, re.IGNORECASE)
    if sodium:
        data['sodium_mg'] = int(sodium.group(1))

    # Carbohydrates
    carbs = re.search(r'Total Carbohydrate\s*(\d+)g', text, re.IGNORECASE)
    if carbs:
        data['carbs_g'] = int(carbs.group(1))
    
    #serving size
    serving = re.search(r'\((\d+)\s*g\)', text, re.IGNORECASE)
    if serving:
        data['serving_size_g'] = int(serving.group(1))

    return data