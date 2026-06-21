import re

try:
    import Levenshtein
except ImportError:
    Levenshtein = None

# Stage 8: Ordered mapping to check specific keywords before generic keywords
NUTRITION_MAPPING_ORDER = [
    ("added_sugars_g", ["added sugars", "added sugar", "includes added sugars", "include added sugars", "added"]),
    ("sugars_g", ["total sugars", "total sugar", "sugars", "sugar", "sucre", "sucres"]),
    ("saturated_fat_g", ["saturated fat", "sat fat", "sat. fat", "saturates", "saturated fats", "saturated"]),
    ("trans_fat_g", ["trans fat", "trans fats", "trans", "trans fatty acids"]),
    ("fat_g", ["total fat", "fat", "lipid", "lipids", "matiere grasse"]),
    ("energy_kcal", ["calories", "energy", "calorie", "kcal", "kcalories", "cal"]),
    ("protein_g", ["protein", "proteins", "protien", "proteine"]),
    ("carbohydrates_g", ["total carbohydrate", "carbohydrate", "carbohydrates", "total carb", "total carbs", "carb", "carbs"]),
    ("fiber_g", ["dietary fiber", "dietary fibre", "fiber", "fibre", "fibers", "fibres"]),
    ("sodium_mg", ["sodium", "natrium", "salt", "salz", "sel"]),
    ("cholesterol_mg", ["cholesterol", "cholesteral", "chol", "cholest"]),
    ("serving_size", ["serving size", "serv size", "serving"]),
]

WHO_LIMITS = {
    "energy_kcal": 2000.0,
    "protein_g": 50.0,
    "carbohydrates_g": 260.0,
    "sugars_g": 50.0,
    "added_sugars_g": 50.0,
    "fat_g": 70.0,
    "saturated_fat_g": 20.0,
    "trans_fat_g": 2.2,
    "fiber_g": 25.0,
    "sodium_mg": 2000.0,
    "cholesterol_mg": 300.0,
    "calories": 2000.0,
    "protein": 50.0,
    "total_carbohydrates": 260.0,
    "total_sugars": 50.0,
    "added_sugars": 50.0,
    "total_fat": 70.0,
    "saturated_fat": 20.0,
    "trans_fat": 2.2,
    "dietary_fiber": 25.0,
    "sodium": 2000.0,
    "cholesterol": 300.0
}

DEFAULT_UNITS = {
    "serving_size": "g",
    "energy_kcal": "kcal",
    "protein_g": "g",
    "carbohydrates_g": "g",
    "sugars_g": "g",
    "added_sugars_g": "g",
    "fat_g": "g",
    "saturated_fat_g": "g",
    "trans_fat_g": "g",
    "fiber_g": "g",
    "sodium_mg": "mg",
    "cholesterol_mg": "mg",
}

def _clean_numeric_typos(raw_val_str: str) -> str:
    """
    Cleans up common OCR typos in numbers (e.g. 'O' or 'o' instead of '0', ',' instead of '.').
    """
    cleaned = raw_val_str.replace('O', '0').replace('o', '0').replace(',', '.')
    # Remove any non-numeric and non-dot characters
    cleaned = re.sub(r'[^\d.]', '', cleaned)
    return cleaned

def _strip_percent_dv(line: str) -> str:
    """
    Remove percentage markers and daily value columns to prevent extracting DV percentage.
    """
    # Remove items like "10%" or "5 %"
    line = re.sub(r'\d+\s*%\s*', ' ', line)
    # Remove trailing digits that look like daily value percentage (e.g. "Total Fat 1.5g 2" -> "Total Fat 1.5g")
    line = re.sub(r'(\d+[a-zA-Z]*)\s+\d+\s*$', r'\1', line)
    return line.strip()

def _extract_value_and_unit(line: str, default_unit: str, field_key: str):
    """
    Parse numerical value and units from the text line.
    """
    # Strip percent daily value first
    line = _strip_percent_dv(line)
    
    # Regex to find numbers followed by potential units
    pattern = re.compile(
        r'([O0-9]+(?:[.,][O0-9]+)?)\s*(mg|mcg|µg|ug|kcal|kj|cal|g|ml|oz)?\b',
        re.IGNORECASE
    )
    
    matches = list(pattern.finditer(line))
    if not matches:
        return None, None
        
    for m in matches:
        raw_num = m.group(1)
        raw_unit = m.group(2)
        
        # Clean number
        cleaned_num_str = _clean_numeric_typos(raw_num)
        try:
            val = float(cleaned_num_str)
        except ValueError:
            continue
            
        unit = raw_unit.lower() if raw_unit else default_unit
        
        # Normalize units
        if unit in ('µg', 'ug'):
            unit = 'mcg'
            
        # Apply standard "9-as-g" / "g-as-9" check if it ends with 9 and has no unit
        if raw_unit is None and default_unit == 'g' and raw_num.endswith('9') and len(raw_num) > 1:
            val = float(_clean_numeric_typos(raw_num[:-1]))
            
        return val, unit
        
    return None, None

def _identify_field_fuzzy(line_lower: str) -> str | None:
    """
    Stage 8 Fuzzy Synonym Parser.
    Checks ordered triggers, returns the first field key matching with >= 90% confidence.
    """
    # Helper to check exclusions
    def is_excluded(key, line):
        if key == "serving_size" and re.search(r'servings?\s+per', line):
            return True
        if key == "fat_g" and re.search(r'cal\w*\s+(?:from\s+)?fat', line):
            return True
        return False

    # 1. Word boundary check (exact matches have 100% confidence)
    for field_key, triggers in NUTRITION_MAPPING_ORDER:
        if is_excluded(field_key, line_lower):
            continue
            
        for trigger in triggers:
            # Check for word boundary
            if re.search(r'\b' + re.escape(trigger) + r'\b', line_lower):
                return field_key

    # 2. Fuzzy sequence similarity checking (>= 90%)
    words = line_lower.split()
    for field_key, triggers in NUTRITION_MAPPING_ORDER:
        if is_excluded(field_key, line_lower):
            continue
            
        for trigger in triggers:
            trigger_len = len(trigger.split())
            if trigger_len == 0 or len(words) < trigger_len:
                continue
                
            for i in range(len(words) - trigger_len + 1):
                sub_phrase = " ".join(words[i:i+trigger_len])
                sub_clean = re.sub(r'[^\w\s]', '', sub_phrase).strip()
                trigger_clean = re.sub(r'[^\w\s]', '', trigger).strip()
                
                if not sub_clean or not trigger_clean:
                    continue
                    
                if Levenshtein:
                    ratio = Levenshtein.ratio(sub_clean, trigger_clean)
                else:
                    from difflib import SequenceMatcher
                    ratio = SequenceMatcher(None, sub_clean, trigger_clean).ratio()
                    
                if ratio >= 0.90:
                    return field_key

    return None

def extract_nutrition(raw_text: str) -> dict:
    """
    Stage 7 & Stage 8: Parse text and output structured flat JSON mapping.
    All missing fields are set to null.
    """
    # Target schema initialized to null
    data = {
        "serving_size": None,
        "energy_kcal": None,
        "protein_g": None,
        "carbohydrates_g": None,
        "sugars_g": None,
        "added_sugars_g": None,
        "fat_g": None,
        "saturated_fat_g": None,
        "trans_fat_g": None,
        "fiber_g": None,
        "sodium_mg": None,
        "cholesterol_mg": None,
        "_units": {}
    }
    
    lines = raw_text.split('\n')
    
    # Process line-by-line
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
            
        line_lower = line.lower()
        
        # Skip headers or common layout notes
        if re.search(r'%\s*daily\s*value', line_lower):
            continue
        if 'not a significant source' in line_lower:
            continue
            
        # Match field
        field_key = _identify_field_fuzzy(line_lower)
        if not field_key:
            continue
            
        # Skip duplicate extractions
        if data[field_key] is not None:
            continue
            
        default_unit = DEFAULT_UNITS.get(field_key, 'g')
        val, unit = _extract_value_and_unit(line, default_unit, field_key)
        
        if val is None:
            continue
            
        # Standardize and normalize units (e.g. kJ -> kcal, mg -> g, etc.)
        if field_key == "energy_kcal":
            if unit == "kj":
                val = round(val / 4.184, 1)
        elif field_key == "sodium_mg" and "salt" in line_lower:
            # Special salt to sodium conversion: 1g salt = 400mg sodium
            if unit == "g":
                val = val * 400
            elif unit == "mg":
                val = val * 0.4
        elif field_key in ("sodium_mg", "cholesterol_mg"):
            if unit == "g":
                val = val * 1000
        elif field_key in ("protein_g", "carbohydrates_g", "sugars_g", "added_sugars_g", "fat_g", "saturated_fat_g", "trans_fat_g", "fiber_g"):
            if unit == "mg":
                val = round(val / 1000, 3)
                
        data[field_key] = float(val)
        data["_units"][field_key] = unit
        
    # If serving size is still missing, attempt regex fallback in first 15 lines
    if data["serving_size"] is None:
        serving_block = "\n".join(lines[:15])
        bracket = re.search(
            r'serv\w*\s+size[^0-9]*?(\d+(?:[.,]\d+)?)\s*(g|ml|oz)',
            serving_block, re.IGNORECASE
        )
        if not bracket:
            bracket = re.search(
                r'\((\d+(?:[.,]\d+)?)\s*(g|ml|oz)\)',
                serving_block, re.IGNORECASE
            )
        if bracket:
            data["serving_size"] = float(bracket.group(1).replace(',', '.'))
            data["_units"]["serving_size"] = bracket.group(2).lower()
            
    return data
