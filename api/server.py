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
from models.db import init_db, get_user, create_or_update_user

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
    
    # Fetch profile from DB if email provided
    user_profile = {}
    if email:
        db_user = get_user(email)
        if db_user:
            # We must map the DB booleans safely to integers if needed, 
            # SQLite returns 1/0 for true/false which is fine for python boolean checks.
            user_profile = {
                "is_diabetic": bool(db_user.get("is_diabetic")),
                "has_high_bp": bool(db_user.get("has_high_bp")),
                "heart_condition": bool(db_user.get("heart_condition")),
                "weight_loss_goal": bool(db_user.get("weight_loss_goal")),
                "is_vegan": bool(db_user.get("is_vegan"))
            }

    # Create upload directory if it doesn't exist
    upload_dir = "data/uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir, exist_ok=True)
        
    # Save the uploaded file temporarily
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # Run the updated 11-stage pipeline with profile
        result = run_pipeline(file_path, user_profile=user_profile)
        
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
