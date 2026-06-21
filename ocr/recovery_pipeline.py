import cv2
import numpy as np
import os
import json
import base64
import requests
from ocr.gemini_engine import GeminiEngine
from ocr.paddle_engine import PaddleEngine

class RecoveryPipeline:
    MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.gemini_engine = GeminiEngine(api_key=self.api_key) if self.api_key else None
        self._paddle_engine = None
        self.rate_limit_triggered = False

    @property
    def paddle_engine(self):
        if self._paddle_engine is None:
            # Initialize PaddleOCR engine lazily
            self._paddle_engine = PaddleEngine()
        return self._paddle_engine

    def evaluate_confidence(self, detections: list) -> float:
        """
        Stage 4: Compute average confidence score across all detections.
        """
        if not detections:
            return 0.0
        confidences = [d.get("confidence", 0.0) for d in detections]
        return float(np.mean(confidences))

    def crop_and_enhance(self, image: np.ndarray, bbox: list) -> np.ndarray:
        """
        Crop a subregion from the image and apply extra sharpening/contrast enhancement.
        bbox format: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
        """
        h_img, w_img = image.shape[:2]
        
        # Get outer coordinates
        xs = [pt[0] for pt in bbox]
        ys = [pt[1] for pt in bbox]
        
        x1 = max(0, int(min(xs) - 10))
        y1 = max(0, int(min(ys) - 10))
        x2 = min(w_img, int(max(xs) + 10))
        y2 = min(h_img, int(max(ys) + 10))
        
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return crop
            
        # Enhance crop
        # 1. Resize/Upscale (2x)
        crop = cv2.resize(crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        
        # 2. Denoise and enhance contrast (CLAHE)
        if len(crop.shape) == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop
            
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4,4))
        enhanced_gray = clahe.apply(gray)
        
        # Unsharp mask sharpening
        blurred = cv2.GaussianBlur(enhanced_gray, (3, 3), 0)
        sharpened = cv2.addWeighted(enhanced_gray, 1.5, blurred, -0.5, 0)
        
        return sharpened

    def query_vision_llm_for_crop(self, crop: np.ndarray) -> str:
        """
        Stage 5 Fallback: Query Vision LLM to transcribe text from a cropped region.
        """
        if not self.api_key:
            print("      [Warning] GEMINI_API_KEY is not set. Skipping Vision LLM fallback.")
            return ""
            
        if self.rate_limit_triggered:
            print("      [Recovery] API rate limit triggered in this pipeline run. Skipping crop LLM recovery.")
            return ""
            
        # Encode crop as base64 JPEG
        _, buffer = cv2.imencode(".jpg", crop)
        image_data = base64.b64encode(buffer).decode("utf-8")
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are reading a nutrition label. "
                                "Return only the exact text visible. "
                                "Do not infer missing values. "
                                "Preserve numbers, units, and spelling."
                            )
                        },
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": image_data
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1
            }
        }
        
        headers = {"Content-Type": "application/json"}
        
        all_429s = True
        for model in self.MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=15)
                if response.status_code == 429:
                    print(f"      [Warning] Model {model} rate limited (429) for crop. Trying next...")
                    continue
                
                all_429s = False
                if response.status_code == 200:
                    res_json = response.json()
                    text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return text
                else:
                    print(f"      [Warning] Gemini Vision LLM {model} error ({response.status_code}): {response.text}")
            except Exception as e:
                print(f"      [Warning] Vision LLM recovery crop check failed for {model}: {e}")
                
        if all_429s:
            print("      [Warning] All models rate-limited (429). Triggering rate limit flag.")
            self.rate_limit_triggered = True
            
        return ""

    # Shared structured response schema for nutrition extraction
    NUTRITION_RESPONSE_SCHEMA = {
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

    # Key mapping from Gemini schema keys to pipeline schema keys
    GEMINI_KEY_MAPPING = {
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

    def _build_structured_payload(self, image_data: str, mime_type: str = "image/jpeg") -> dict:
        """Build a Gemini API payload that returns structured nutrition JSON directly from an image."""
        return {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Analyze this nutrition facts label image. "
                                "Extract all matching nutritional fields. "
                                "Return the numeric value and the units (e.g. 'g', 'mg', 'kcal'). "
                                "If a field is not present in the label, omit it or set it to null."
                            )
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
                "responseSchema": self.NUTRITION_RESPONSE_SCHEMA
            }
        }

    def _map_gemini_response_to_pipeline(self, raw_data: dict) -> dict:
        """Convert Gemini's structured response to the pipeline's internal schema."""
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
            pipe_key = self.GEMINI_KEY_MAPPING.get(gemini_key)
            if pipe_key:
                pipeline_data[pipe_key] = float(val)
                if unit:
                    pipeline_data["_units"][pipe_key] = str(unit).lower().strip()
        return pipeline_data

    def query_vision_llm_for_full_image(self, image: np.ndarray) -> dict | None:
        """
        Stage 5 Primary AI Action: Send the full image directly to Gemini and get
        structured nutrition data back (no OCR text, no regex parsing).
        Returns a pipeline-schema dict on success, or None on failure.
        """
        if not self.api_key:
            return None

        if self.rate_limit_triggered:
            return None

        _, buffer = cv2.imencode(".jpg", image)
        image_data = base64.b64encode(buffer).decode("utf-8")

        payload = self._build_structured_payload(image_data, mime_type="image/jpeg")
        headers = {"Content-Type": "application/json"}

        all_429s = True
        for model in self.MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            try:
                print(f"      [AI Recovery] Sending image directly to {model} for structured extraction...")
                response = requests.post(url, json=payload, headers=headers, timeout=20)
                if response.status_code == 429:
                    print(f"      [Warning] Model {model} rate limited (429) for full-image. Trying next...")
                    continue

                all_429s = False
                if response.status_code == 200:
                    res_json = response.json()
                    text_content = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    raw_data = json.loads(text_content)
                    return self._map_gemini_response_to_pipeline(raw_data)
                else:
                    print(f"      [Warning] Gemini Vision LLM {model} error ({response.status_code}): {response.text}")
            except Exception as e:
                print(f"      [Warning] Vision LLM full-image recovery failed for {model}: {e}")

        if all_429s:
            print("      [Warning] All models rate-limited (429) for full-image. Triggering rate limit flag.")
            self.rate_limit_triggered = True

        return None

    def query_structured_nutrition_from_image_path(self, image_path: str) -> dict | None:
        """
        Send an image file directly to Gemini and get structured nutrition data back.
        Used as a fallback in the main pipeline when OCR + regex parsing fails.
        Returns a pipeline-schema dict on success, or None on failure.
        """
        if not self.api_key:
            return None

        if self.rate_limit_triggered:
            return None

        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            _, ext = os.path.splitext(image_path.lower())
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                        ".png": "image/png", ".webp": "image/webp"}
            mime_type = mime_map.get(ext, "image/jpeg")
        except Exception as e:
            print(f"      [Warning] Could not read image file for Gemini: {e}")
            return None

        payload = self._build_structured_payload(image_data, mime_type=mime_type)
        headers = {"Content-Type": "application/json"}

        all_429s = True
        for model in self.MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            try:
                print(f"      [AI Fallback] Sending image directly to {model} for structured extraction...")
                response = requests.post(url, json=payload, headers=headers, timeout=20)
                if response.status_code == 429:
                    print(f"      [Warning] Model {model} rate limited (429). Trying next...")
                    continue

                all_429s = False
                if response.status_code == 200:
                    res_json = response.json()
                    text_content = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    raw_data = json.loads(text_content)
                    return self._map_gemini_response_to_pipeline(raw_data)
                else:
                    print(f"      [Warning] Gemini {model} error ({response.status_code}): {response.text}")
            except Exception as e:
                print(f"      [Warning] Gemini image extraction failed for {model}: {e}")

        if all_429s:
            print("      [Warning] All models rate-limited (429). Triggering rate limit flag.")
            self.rate_limit_triggered = True

        return None

    def run_recovery(self, image: np.ndarray, detections: list) -> tuple[list, float, list[dict]]:
        """
        Stage 4 & Stage 5 Recovery Pipeline.
        Evaluates the average confidence:
        - If >= 0.90: Accept OCR directly.
        - If 0.70 - 0.90: Retry OCR on cropped regions (for detections < 0.90).
        - If < 0.70: Trigger full Recovery Pipeline (crop, re-enhance, retry OCR. If still low, use Vision LLM).
        """
        avg_conf = self.evaluate_confidence(detections)
        recovery_logs = []
        
        if avg_conf >= 0.95:
            print(f"[OCR Confidence] High average confidence ({avg_conf:.2f} >= 0.95). Accepting OCR.")
            return detections, avg_conf, recovery_logs
            
        print(f"[OCR Confidence] Moderate/Low confidence ({avg_conf:.2f} < 0.95). Giving weightage to AI model full-image recovery...")
        
        # Give priority to AI full-image recovery — send the image directly to Gemini
        if self.api_key:
            structured_data = self.query_vision_llm_for_full_image(image)
            if structured_data is not None:
                recovery_logs.append({
                    "ocr_text": "full_image_direct",
                    "vision_text": "[structured JSON from Gemini — image sent directly]",
                    "final_text": "[structured JSON from Gemini — image sent directly]"
                })
                print("      [Recovery] Gemini returned structured nutrition data directly from image.")
                # Return a sentinel detection list so main.py knows to skip regex parsing
                h, w = image.shape[:2]
                final_detections = [{
                    "text": "__STRUCTURED_GEMINI__",
                    "bbox": [[0, 0], [w, 0], [w, h], [0, h]],
                    "confidence": 0.99,
                    "_structured_nutrition": structured_data
                }]
                return final_detections, 0.99, recovery_logs
        
        print("      [Recovery] Falling back to individual crop recovery...")
        final_detections = []
        for d in detections:
            text = d.get("text", "")
            conf = d.get("confidence", 0.0)
            bbox = d.get("bbox")
            
            # If the individual detection has confidence < 0.90, we recover
            if conf < 0.90 and bbox:
                # 1. Crop region and 2. Re-enhance crop
                crop = self.crop_and_enhance(image, bbox)
                if crop.size == 0:
                    final_detections.append(d)
                    continue
                    
                # 3. Re-run PaddleOCR
                crop_ocr_res = None
                crop_best_text = ""
                crop_conf = 0.0
                try:
                    # Convert to BGR format for PaddleOCR
                    crop_bgr = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
                    crop_ocr_res = self.paddle_engine.extract_text(crop_bgr)
                    crop_best_text = crop_ocr_res.get("best_text", "").strip()
                    crop_dets = crop_ocr_res.get("detections", [])
                    crop_conf = np.mean([det["confidence"] for det in crop_dets]) if crop_dets else 0.0
                except Exception as e:
                    print(f"      [Recovery] Local OCR retry failed: {e}")
                
                # If confidence still low (< 0.70) and avg_conf was low (< 0.70), send to Vision LLM fallback
                if avg_conf < 0.70 and crop_conf < 0.70:
                    print(f"      [Recovery] OCR confidence still low ({crop_conf:.2f}). Triggering Vision LLM fallback...")
                    vision_text = self.query_vision_llm_for_crop(crop)
                    
                    # Store comparison logs
                    recovery_logs.append({
                        "ocr_text": text,
                        "vision_text": vision_text,
                        "final_text": vision_text if vision_text else (crop_best_text if crop_best_text else text)
                    })
                    
                    if vision_text:
                        final_detections.append({
                            "text": vision_text,
                            "bbox": bbox,
                            "confidence": 0.95  # High confidence for LLM verified text
                        })
                        continue
                
                # If crop-retry improved the OCR, update the detection
                if crop_best_text and crop_conf > conf:
                    print(f"      [Recovery] Improved via crop OCR: '{text}' ({conf:.2f}) -> '{crop_best_text}' ({crop_conf:.2f})")
                    final_detections.append({
                        "text": crop_best_text,
                        "bbox": bbox,
                        "confidence": float(crop_conf)
                    })
                else:
                    final_detections.append(d)
            else:
                final_detections.append(d)
                
        # Compute final average confidence
        final_avg_conf = self.evaluate_confidence(final_detections)
        return final_detections, final_avg_conf, recovery_logs

    def merge_text_layout(self, detections: list) -> str:
        """
        Stage 6: Text Merging.
        Sorts detections vertically and clusters horizontally (rows) based on spatial overlay.
        Preserves row order.
        """
        if not detections:
            return ""
            
        rows = []
        for d in detections:
            bbox = d["bbox"]
            text = d["text"]
            
            # Calculate vertical boundaries and centroid
            ys = [pt[1] for pt in bbox]
            min_y = min(ys)
            max_y = max(ys)
            h = max_y - min_y
            center_y = min_y + h / 2.0
            
            xs = [pt[0] for pt in bbox]
            min_x = min(xs)
            
            rows.append({
                "text": text,
                "min_y": min_y,
                "max_y": max_y,
                "center_y": center_y,
                "min_x": min_x,
                "height": h
            })
            
        # Cluster rows based on vertical overlap
        rows.sort(key=lambda r: r["center_y"])
        
        clustered_rows = []
        for r in rows:
            placed = False
            for cluster in clustered_rows:
                avg_h = np.mean([item["height"] for item in cluster])
                avg_y = np.mean([item["center_y"] for item in cluster])
                
                # If vertical distance is within 60% of average height, merge into the same line row
                if abs(r["center_y"] - avg_y) < (avg_h * 0.6):
                    cluster.append(r)
                    placed = True
                    break
                    
            if not placed:
                clustered_rows.append([r])
                
        # Sort each line cluster horizontally and construct line strings
        merged_lines = []
        for cluster in clustered_rows:
            cluster.sort(key=lambda item: item["min_x"])
            line_text = " ".join([item["text"] for item in cluster])
            avg_y = np.mean([item["center_y"] for item in cluster])
            merged_lines.append((avg_y, line_text))
            
        # Sort lines vertically to preserve top-to-bottom row order
        merged_lines.sort(key=lambda item: item[0])
        final_text = "\n".join([item[1] for item in merged_lines])
        
        return final_text
