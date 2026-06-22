import os
import cv2
import ssl
import numpy as np
import uuid
from datetime import datetime, timezone
import json

# Bypass SSL verification to allow model downloads
ssl._create_default_https_context = ssl._create_unverified_context

# Simple .env loader to fetch local environment variables
def load_dotenv(dotenv_path=".env"):
    if os.path.exists(dotenv_path):
        with open(dotenv_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("=", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip()
                    if val.startswith(('"', "'")) and val.endswith(('"', "'")):
                        val = val[1:-1]
                    os.environ[key] = val

load_dotenv()

# Import pipeline components
from utils.image_processing import preprocess_for_ocr
from ocr.paddle_engine import PaddleEngine
from ocr.ocr_engine import extract_text as legacy_extract_text
from ocr.recovery_pipeline import RecoveryPipeline
from parser.nutrient_parser import extract_nutrition
from validator.bounds_validator import validate_bounds
from scoring.hybrid_scorer import NutriScorer

_PADDLE_ENGINE = None
_NUTRI_SCORER = None

def get_nutri_scorer() -> NutriScorer:
    global _NUTRI_SCORER
    if _NUTRI_SCORER is None:
        _NUTRI_SCORER = NutriScorer()
    return _NUTRI_SCORER

def get_paddle_engine():
    global _PADDLE_ENGINE
    if _PADDLE_ENGINE is None:
        _PADDLE_ENGINE = PaddleEngine()
    return _PADDLE_ENGINE

def log_step(stage: int, stage_name: str, status: str, details: dict):
    """Logs pipeline progress using structured JSON formats."""
    log_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "stage_name": stage_name,
        "status": status,
        "details": details
    }
    print(f"JSON_LOG: {json.dumps(log_record)}")

def run_pipeline(image_path: str, user_profile: dict = None, api_key: str = None, daily_totals: dict = None) -> dict:
    """
    Orchestrates the entire 11-stage NutriScan pipeline.
    """
    # STAGE 1 — IMAGE INPUT
    image_id = str(uuid.uuid4())
    upload_timestamp = datetime.now(timezone.utc).isoformat()
    
    log_step(1, "IMAGE INPUT", "success", {
        "image_id": image_id,
        "upload_timestamp": upload_timestamp,
        "original_image_path": image_path
    })
    
    img = cv2.imread(image_path)
    if img is None:
        log_step(1, "IMAGE INPUT", "failed", {"error": "Could not read image file"})
        raise ValueError(f"Could not read image file at: {image_path}")

    # STAGE 2 — OPENCV PREPROCESSING
    try:
        preprocessed_img = preprocess_for_ocr(image_path)
        log_step(2, "OPENCV PREPROCESSING", "success", {
            "dimensions": preprocessed_img.shape
        })
    except Exception as e:
        log_step(2, "OPENCV PREPROCESSING", "failed", {"error": str(e)})
        # Fallback to simple grayscale
        preprocessed_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # STAGE 2.5 - AI PRIMARY EXTRACTION
    key = api_key or os.environ.get("GEMINI_API_KEY")
    nutrition_data = None
    ocr_confidence = 0.0
    
    if key:
        try:
            from ocr.gemini_engine import GeminiEngine
            gemini = GeminiEngine(api_key=key)
            nutrition_data = gemini.extract_nutrition_from_image(image_path)
            ocr_confidence = 0.99 # AI extraction implies high confidence
            log_step(2.5, "AI PRIMARY EXTRACTION", "success", {
                "extracted_keys": [k for k, v in nutrition_data.items() if v is not None and k != "_units"]
            })
        except Exception as e:
            log_step(2.5, "AI PRIMARY EXTRACTION", "failed", {"error": str(e)})
            nutrition_data = None

    if nutrition_data is None:
        # STAGE 3 — PADDLEOCR
        ocr_result = None
        detections = []
    
        try:
            # Convert preprocessed image to BGR (PaddleOCR model requirements)
            preprocessed_bgr = cv2.cvtColor(preprocessed_img, cv2.COLOR_GRAY2BGR)
            engine = get_paddle_engine()
            ocr_result = engine.extract_text(preprocessed_bgr)
            detections = ocr_result.get("detections", [])
            log_step(3, "PADDLEOCR", "success", {
                "detections_count": len(detections)
            })
        except Exception as e:
            log_step(3, "PADDLEOCR", "failed", {"error": str(e), "message": "Falling back to legacy OCR"})
            # Fallback to easyocr / tesseract legacy engine
            try:
                ocr_result = legacy_extract_text(preprocessed_img)
                detections = ocr_result.get("detections", [])
                log_step(3, "PADDLEOCR_FALLBACK", "success", {
                    "detections_count": len(detections)
                })
            except Exception as ex:
                log_step(3, "PADDLEOCR_FALLBACK", "failed", {"error": str(ex)})
                detections = []

        # STAGE 4 — CONFIDENCE EVALUATION & STAGE 5 — OCR RECOVERY PIPELINE
        key = api_key or os.environ.get("GEMINI_API_KEY")
        recovery = RecoveryPipeline(api_key=key)
        
        # We pass the original image for cropping to avoid binary degradation
        final_detections, ocr_confidence, recovery_logs = recovery.run_recovery(img, detections)
        
        log_step(4, "CONFIDENCE EVALUATION", "success", {
            "average_confidence": ocr_confidence
        })
        
        log_step(5, "OCR RECOVERY PIPELINE", "success", {
            "recovery_runs": len(recovery_logs),
            "recovery_logs": recovery_logs
        })

        # STAGE 6 — TEXT MERGING & STAGE 7/8 — PARSER
        # Check if recovery pipeline already returned structured data directly from Gemini
        structured_from_recovery = None
        if final_detections and final_detections[0].get("text") == "__STRUCTURED_GEMINI__":
            structured_from_recovery = final_detections[0].get("_structured_nutrition")

        if structured_from_recovery is not None:
            nutrition_data = structured_from_recovery
            log_step(6, "TEXT MERGING", "skipped", {
                "reason": "Gemini returned structured JSON directly from image — no text merging needed"
            })
            log_step(7, "JSON NORMALIZATION", "success", {
                "source": "gemini_image_direct",
                "extracted_keys": [k for k, v in nutrition_data.items() if v is not None and k != "_units"]
            })
            log_step(8, "NUTRITION PARSER", "success", {
                "source": "gemini_image_direct",
                "extracted_fields": nutrition_data
            })
        else:
            # STAGE 6 — TEXT MERGING
            merged_text = recovery.merge_text_layout(final_detections)
            log_step(6, "TEXT MERGING", "success", {
                "merged_text_length": len(merged_text)
            })

            # STAGE 7 — JSON NORMALIZATION & STAGE 8 — NUTRITION PARSER
            nutrition_data = extract_nutrition(merged_text)
            log_step(7, "JSON NORMALIZATION", "success", {
                "extracted_keys": [k for k, v in nutrition_data.items() if v is not None and k != "_units"]
            })
            log_step(8, "NUTRITION PARSER", "success", {
                "extracted_fields": nutrition_data
            })

    # STAGE 9-11 extracted to function for reuse
    result = evaluate_nutrition(nutrition_data, user_profile, daily_totals)
    
    # FINAL RESPONSE FORMAT
    response = {
        "image_id":       image_id,
        "ocr_confidence": round(ocr_confidence, 2),
        "nutrition_data": result["nutrition_data"],
        "health_score":   result["score_res"]["health_score"],
        "rating":         result["score_res"]["rating"],
        "warnings":       result["warnings"],
        "insights":       result["score_res"]["insights"],
        "score_components": result["score_res"].get("components", {}),
    }

    return response

def evaluate_nutrition(nutrition_data: dict, user_profile: dict = None, daily_totals: dict = None) -> dict:
    """
    Runs STAGE 9-11 directly from a nutrition dictionary (used for barcode scanning).
    """
    # STAGE 9 — VALIDATION ENGINE
    validation_res = validate_bounds(nutrition_data)
    warnings = validation_res["flags"]
    nutrition_data = validation_res.get("data", nutrition_data)
    log_step(9, "VALIDATION ENGINE", "success", {
        "is_valid":       validation_res["is_valid"],
        "warnings_count": len(warnings),
        "warnings":       warnings,
        "corrections":    list(validation_res.get("corrected", {}).keys()),
    })

    # STAGE 10 — HEALTH SCORE ENGINE (40% rules + 60% ML)
    # STAGE 11 — INSIGHT GENERATOR  (Gemini AI + rule fallback)
    scorer    = get_nutri_scorer()
    score_res = scorer.get_final_score(
        nutrition_data=nutrition_data,
        user_profile=user_profile or {},
        daily_totals=daily_totals,
    )
    log_step(10, "HEALTH SCORE ENGINE", "success", {
        "health_score":  score_res["health_score"],
        "rating":        score_res["rating"],
        "components":    score_res.get("components", {}),
    })
    log_step(11, "INSIGHT GENERATOR", "success", {
        "insights_count": len(score_res["insights"]),
        "insights":       score_res["insights"],
    })

    return {
        "nutrition_data": nutrition_data,
        "warnings": warnings,
        "score_res": score_res
    }

if __name__ == "__main__":
    sample_path = "data/sample_images/nutrition_label2.jpg"
    if not os.path.exists(sample_path):
        print(f"Creating a dummy image at {sample_path} for testing...")
        # Create a blank white image with some text
        img = np.ones((500, 500, 3), dtype=np.uint8) * 255
        cv2.putText(img, 'Nutrition Facts', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
        cv2.putText(img, 'Serving Size 55g', (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,0), 2)
        cv2.putText(img, 'Calories 250', (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,0), 2)
        cv2.putText(img, 'Total Fat 12g', (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,0), 2)
        cv2.putText(img, 'Saturated Fat 6g', (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,0), 2)
        cv2.putText(img, 'Sodium 800mg', (50, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,0), 2)
        cv2.putText(img, 'Total Sugars 25g', (50, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,0), 2)
        cv2.putText(img, 'Protein 5g', (50, 400), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,0), 2)
        os.makedirs(os.path.dirname(sample_path), exist_ok=True)
        cv2.imwrite(sample_path, img)

    result = run_pipeline(sample_path)
    print("\n--- PIPELINE EXECUTION SUCCESSFUL ---")
    print(json.dumps(result, indent=2))