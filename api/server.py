from fastapi import FastAPI, UploadFile, File, Form, Body
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import shutil
import logging
import json
from datetime import datetime, timezone

# Import the pipeline from our main.py
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import run_pipeline
from parser.nutrient_parser import DEFAULT_UNITS, WHO_LIMITS
from models.db import (
    init_db, get_user, create_or_update_user,
    log_intake, get_daily_intake, delete_intake_item, get_daily_totals
)

app = FastAPI(title="NutriScan API")

# Initialize SQLite database
init_db()

# Configure structured JSON logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("NutriScanServer")

def log_api_call(endpoint: str, status: str, details: dict):
    log_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "status": status,
        "details": details
    }
    logger.info(f"API_LOG: {json.dumps(log_record)}")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend directory statically
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
def read_index():
    return FileResponse("frontend/index.html")

class LoginRequest(BaseModel):
    email: str
    name: str

@app.post("/auth/login")
def login(req: LoginRequest):
    is_new = create_or_update_user(req.email, req.name)
    user = get_user(req.email)
    return {"status": "success", "is_new_user": is_new, "user": user}

class ProfileUpdate(BaseModel):
    email: str
    is_diabetic: bool = False
    has_high_bp: bool = False
    heart_condition: bool = False
    weight_loss_goal: bool = False
    is_vegan: bool = False

@app.post("/auth/profile")
def update_profile(req: ProfileUpdate):
    create_or_update_user(req.email, "", profile_data=req.dict())
    return {"status": "success"}

@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...), email: str = Form(None)):
    log_api_call("/analyze", "started", {"filename": file.filename})
    
    # Fetch profile and daily totals from DB if email provided
    user_profile = {}
    daily_totals = {}
    if email:
        db_user = get_user(email)
        if db_user:
            user_profile = {
                "is_diabetic": bool(db_user.get("is_diabetic")),
                "has_high_bp": bool(db_user.get("has_high_bp")),
                "heart_condition": bool(db_user.get("heart_condition")),
                "weight_loss_goal": bool(db_user.get("weight_loss_goal")),
                "is_vegan": bool(db_user.get("is_vegan"))
            }
        today_str = datetime.now().strftime("%Y-%m-%d")
        daily_totals = get_daily_totals(email, today_str)

    # Create upload directory if it doesn't exist
    upload_dir = "data/uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir, exist_ok=True)
        
    # Save the uploaded file temporarily
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # Run the updated 11-stage pipeline with profile and daily totals
        result = run_pipeline(file_path, user_profile=user_profile, daily_totals=daily_totals)
        
        # Build the backward-compatibility layer for the frontend
        units_map = result["nutrition_data"].pop("_units", {})
        raw_nutrition_compat = {}
        for k, val in result["nutrition_data"].items():
            if val is not None and k != "_units":
                unit = units_map.get(k) or DEFAULT_UNITS.get(k, "g")
                who_limit = WHO_LIMITS.get(k)
                pct = round((val / who_limit) * 100, 1) if who_limit else None
                raw_nutrition_compat[k] = {
                    "value": val,
                    "unit": unit,
                    "who_limit": who_limit,
                    "percent_daily": pct
                }
                
        compat_flags = []
        for ins in result["insights"]:
            compat_flags.append({
                "type": "info",
                "message": ins
            })
        for warn in result["warnings"]:
            compat_flags.append({
                "type": "risk",
                "message": f"Validation Warning for {warn['field']}: {warn['reason']}"
            })
            
        compat_final_result = {
            "final_health_score": float(result["health_score"]) / 100.0,
            "risk_level": "Low" if result["rating"] in ("Excellent", "Good") else ("Moderate" if result["rating"] == "Moderate" else "High"),
            "rating": result["rating"],
            "flags": compat_flags
        }
        
        # Combine the strict response keys with compatibility keys
        full_response = {
            # Strict compliance keys
            "image_id": result["image_id"],
            "ocr_confidence": result["ocr_confidence"],
            "nutrition_data": result["nutrition_data"],
            "health_score": result["health_score"],
            "rating": result["rating"],
            "warnings": result["warnings"],
            "insights": result["insights"],
            
            # Compatibility keys for frontend
            "status": "success",
            "raw_nutrition": raw_nutrition_compat,
            "final_result": compat_final_result
        }
        
        log_api_call("/analyze", "success", {
            "image_id": result["image_id"],
            "health_score": result["health_score"]
        })
        
        return JSONResponse(content=full_response)
        
    except Exception as e:
        log_api_call("/analyze", "failed", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Pipeline processing failed: {str(e)}"}
        )

class LogIntakeRequest(BaseModel):
    email: str
    product_name: str
    energy_kcal: float = 0.0
    sugars_g: float = 0.0
    sodium_mg: float = 0.0
    saturated_fat_g: float = 0.0
    protein_g: float = 0.0
    carbohydrates_g: float = 0.0
    fat_g: float = 0.0

@app.post("/intake/log")
def api_log_intake(req: LogIntakeRequest):
    today_str = datetime.now().strftime("%Y-%m-%d")
    nutrients = {
        "energy_kcal": req.energy_kcal,
        "sugars_g": req.sugars_g,
        "sodium_mg": req.sodium_mg,
        "saturated_fat_g": req.saturated_fat_g,
        "protein_g": req.protein_g,
        "carbohydrates_g": req.carbohydrates_g,
        "fat_g": req.fat_g,
    }
    log_intake(req.email, today_str, req.product_name, nutrients)
    return {"status": "success"}

@app.get("/intake/daily")
def api_get_daily(email: str):
    today_str = datetime.now().strftime("%Y-%m-%d")
    items = get_daily_intake(email, today_str)
    totals = get_daily_totals(email, today_str)
    
    # Determine limits based on profile
    db_user = get_user(email) or {}
    limits = {
        "energy_kcal": 2000.0,
        "sugars_g": 50.0,
        "sodium_mg": 2000.0,
        "saturated_fat_g": 20.0,
        "protein_g": 50.0,
        "carbohydrates_g": 260.0,
        "fat_g": 70.0,
    }
    if db_user.get("is_diabetic"):
        limits["sugars_g"] = 25.0
    if db_user.get("has_high_bp") or db_user.get("heart_condition"):
        limits["sodium_mg"] = 1500.0
    if db_user.get("heart_condition"):
        limits["saturated_fat_g"] = 13.0
    if db_user.get("weight_loss_goal"):
        limits["energy_kcal"] = 1600.0
        
    # Calculate percentages
    percentages = {}
    for key in limits:
        limit_val = limits[key]
        consumed_val = totals.get(key, 0.0)
        percentages[key] = min(100.0, round((consumed_val / limit_val) * 100.0, 1))
        
    # Generate dynamic suggestions of what not to consume
    suggestions = []
    if percentages.get("sugars_g", 0.0) >= 80.0:
        suggestions.append("⚠️ Sugar limit almost reached or exceeded. Avoid juices, sodas, chocolates, and sweets.")
    elif percentages.get("sugars_g", 0.0) >= 50.0:
        suggestions.append("💡 Sugar level moderate. Limit dessert portions and choose sugar-free snacks.")
        
    if percentages.get("sodium_mg", 0.0) >= 80.0:
        suggestions.append("⚠️ Sodium limit almost reached or exceeded. Avoid salty chips, soy sauce, processed meats, and canned soups.")
    elif percentages.get("sodium_mg", 0.0) >= 50.0:
        suggestions.append("💡 Sodium level moderate. Avoid adding extra table salt to your meals.")
        
    if percentages.get("saturated_fat_g", 0.0) >= 80.0:
        suggestions.append("⚠️ Saturated Fat limit almost reached or exceeded. Avoid fried foods, heavy cream, butter, and red meat.")
    elif percentages.get("saturated_fat_g", 0.0) >= 50.0:
        suggestions.append("💡 Saturated fat level moderate. Opt for lean protein sources like chicken or fish.")
        
    if percentages.get("energy_kcal", 0.0) >= 90.0:
        suggestions.append("⚠️ Calorie limit almost reached. Focus on light salads or low-calorie snacks if you need to eat.")
        
    if not suggestions:
        suggestions.append("✅ Nutrient levels healthy! Keep choosing balanced whole foods.")
        
    return {
        "status": "success",
        "items": items,
        "totals": totals,
        "limits": limits,
        "percentages": percentages,
        "suggestions": suggestions
    }

@app.delete("/intake/delete/{item_id}")
def api_delete_item(item_id: int, email: str):
    delete_intake_item(item_id, email)
    return {"status": "success"}

