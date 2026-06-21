import base64
import json
import requests
import os

class GeminiEngine:
    MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def extract_nutrition_from_image(self, image_path: str) -> dict:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")

        # Read and base64-encode the image
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")

        # Determine mime type from extension
        _, ext = os.path.splitext(image_path.lower())
        mime_type = "image/jpeg"
        if ext == ".png":
            mime_type = "image/png"
        elif ext == ".webp":
            mime_type = "image/webp"

        # Schema of expected output
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "serving_size": {
                    "type": "OBJECT",
                    "properties": {
                        "value": {"type": "NUMBER"},
                        "unit": {"type": "STRING"}
                    }
                },
                "calories": {
                    "type": "OBJECT",
                    "properties": {
                        "value": {"type": "NUMBER"},
                        "unit": {"type": "STRING"}
                    }
                },
                "total_fat": {
                    "type": "OBJECT",
                    "properties": {
                        "value": {"type": "NUMBER"},
                        "unit": {"type": "STRING"}
                    }
                },
                "saturated_fat": {
                    "type": "OBJECT",
                    "properties": {
                        "value": {"type": "NUMBER"},
                        "unit": {"type": "STRING"}
                    }
                },
                "trans_fat": {
                    "type": "OBJECT",
                    "properties": {
                        "value": {"type": "NUMBER"},
                        "unit": {"type": "STRING"}
                    }
                },
                "cholesterol": {
                    "type": "OBJECT",
                    "properties": {
                        "value": {"type": "NUMBER"},
                        "unit": {"type": "STRING"}
                    }
                },
                "sodium": {
                    "type": "OBJECT",
                    "properties": {
                        "value": {"type": "NUMBER"},
                        "unit": {"type": "STRING"}
                    }
                },
                "total_carbohydrates": {
                    "type": "OBJECT",
                    "properties": {
                        "value": {"type": "NUMBER"},
                        "unit": {"type": "STRING"}
                    }
                },
                "dietary_fiber": {
                    "type": "OBJECT",
                    "properties": {
                        "value": {"type": "NUMBER"},
                        "unit": {"type": "STRING"}
                    }
                },
                "total_sugars": {
                    "type": "OBJECT",
                    "properties": {
                        "value": {"type": "NUMBER"},
                        "unit": {"type": "STRING"}
                    }
                },
                "added_sugars": {
                    "type": "OBJECT",
                    "properties": {
                        "value": {"type": "NUMBER"},
                        "unit": {"type": "STRING"}
                    }
                },
                "protein": {
                    "type": "OBJECT",
                    "properties": {
                        "value": {"type": "NUMBER"},
                        "unit": {"type": "STRING"}
                    }
                }
            }
        }

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Analyze this nutrition facts label image. Extract all matching nutritional fields. Return the numeric value and the units (e.g. 'g', 'mg', 'kcal'). If a field is not present in the label, omit it or set it to null."
                        },
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": image_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": response_schema
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        response = None
        last_exception = None
        for model in self.MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            try:
                print(f"      [AI Primary] Attempting Gemini extraction with model: {model}...")
                response = requests.post(url, json=payload, headers=headers, timeout=20)
                if response.status_code == 429:
                    print(f"      [Warning] Model {model} rate limited (429). Trying next...")
                    continue
                if response.status_code != 200:
                    print(f"      [Warning] Model {model} failed with status {response.status_code}: {response.text}. Trying next...")
                    continue
                break
            except Exception as e:
                print(f"      [Warning] Gemini extraction failed for {model}: {e}. Trying next...")
                last_exception = e
                continue

        if response is None or response.status_code != 200:
            if last_exception:
                raise last_exception
            err_msg = response.text if response else "No response received"
            raise Exception(f"All Gemini models failed. Last response: {err_msg}")

        res_json = response.json()
        
        # Extract response text
        try:
            candidates = res_json.get("candidates", [])
            if not candidates:
                raise Exception("No candidates returned from Gemini API.")
            
            text_content = candidates[0]["content"]["parts"][0]["text"]
            raw_data = json.loads(text_content)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise Exception(f"Failed to parse Gemini API response: {e}. Raw response: {response.text}")

        # Map Gemini keys to pipeline schema
        key_mapping = {
            "serving_size": "serving_size",
            "calories": "energy_kcal",
            "total_fat": "fat_g",
            "saturated_fat": "saturated_fat_g",
            "trans_fat": "trans_fat_g",
            "cholesterol": "cholesterol_mg",
            "sodium": "sodium_mg",
            "total_carbohydrates": "carbohydrates_g",
            "dietary_fiber": "fiber_g",
            "total_sugars": "sugars_g",
            "added_sugars": "added_sugars_g",
            "protein": "protein_g"
        }
        
        pipeline_data = {
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

        for gemini_key, val_obj in raw_data.items():
            if val_obj is None or not isinstance(val_obj, dict):
                continue
                
            val = val_obj.get("value")
            unit = val_obj.get("unit")
            
            if val is None:
                continue
                
            pipe_key = key_mapping.get(gemini_key)
            if pipe_key:
                pipeline_data[pipe_key] = float(val)
                if unit:
                    pipeline_data["_units"][pipe_key] = str(unit).lower().strip()
                    
        return pipeline_data
