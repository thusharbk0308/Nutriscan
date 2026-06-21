# 🥗 NutriScan — Smart Nutrition Label Analyzer (v3.0 Stable)

NutriScan is a full-stack, AI-powered food safety and personalized nutrition analytics assistant. Designed to be accessible, beautiful, and highly functional, it allows users to scan food label images, extract raw nutritional details, evaluate healthiness using a hybrid Rule/ML engine, and log daily consumption with custom target limits matching their health profile.

---

## 🚀 Key Features

*   **Senior-Friendly UI & Organic Aesthetic**: A welcoming, high-contrast light theme built with clean typography (**Outfit & Inter** fonts) and fresh health-focused colors.
*   **Rotating Background Slideshow**: Smoothly cycles through 3 project-related high-quality nutrition backgrounds (fruits, meal bowls, grocery shopping) with a soft 18% opacity and zoom animations.
*   **11-Stage Processing Pipeline**: Orchestrates image preprocessing, text-detection (PaddleOCR/Tesseract fallback), crop recovery, Levenshtein fuzzy synonym parsing, bounds check validation, and hybrid scoring.
*   **Gemini AI Fast-Path & OCR Recovery**: Leverages Google Gemini APIs to bypass local OCR bottlenecks when online, or crop difficult regions for isolated token recovery.
*   **Daily Log Book (Meal Tracker)**: An interactive progress tracker showing:
    *   Today's consumed Calories, Sugar, Sodium, and Saturated Fat.
    *   Progress bars that transition from green to orange (80% warning) and red (100% exceeded).
    *   Dietitian Recommendations suggesting what food categories to avoid next.
    *   List of logged meals with removal tools.
*   **Consumption-Aware Scoring**: Automatically reduces the health rating of newly scanned foods if they contain nutrients that will push the user over their remaining daily allowance.
*   **Dietary Profiles**: Instantly customizes allowance levels for health goals (Diabetic, Hypertension, Weight Loss, Vegan, Heart-Healthy).

---

## 🛠️ Tech Stack

*   **Frontend**: HTML5, Vanilla JavaScript, CSS3
*   **Backend Server**: FastAPI, Uvicorn, Python 3.10+
*   **Computer Vision (OCR)**: OpenCV, PaddleOCR, Tesseract OCR
*   **Machine Learning**: Scikit-Learn (Stacked Random Forest and Gradient Boosting Classifier), XGBoost
*   **Generative AI**: Google Gemini API
*   **Database**: SQLite3
*   **Identity Provider**: Firebase Auth (Google OAuth 2.0)

---

## 📂 Project Structure

```
nutriscan_project/
│
├── api/
│   └── server.py           # FastAPI server with profile, auth, analyze, and logbook endpoints
│
├── frontend/
│   ├── index.html          # Dashboard, log book, diagnostic pages
│   ├── style.css           # Custom green/orange color tokens, progress bars, slideshow CSS
│   ├── app.js              # State handlers, canvas loaders, API consumers, animations
│   ├── firebase_config.js  # Client-side Firebase credentials
│   └── assets/             # Slide images (bg_fruits, bg_meal, bg_label)
│
├── models/
│   ├── health_model.pkl    # Ensemble ML model binary for scoring
│   ├── db.py               # SQLite initialization, user profile updates, daily log book CRUD
│   └── train.py            # ML pipeline training script
│
├── scoring/
│   ├── hybrid_scorer.py    # Blends 60% ML + 40% rules, implements personalization & log-budget penalties
│   └── rule_scorer.py      # Base WHO limits checks
│
├── main.py                 # Core 11-Stage pipeline orchestrator
├── requirements.txt        # Backend dependencies
├── .gitignore              # Ignores large cache weights, uploads, and keys
└── PROJECT_TECHNICAL_REPORT.md  # Architectural details and mathematical pipeline spec
```

---

## ⚙️ Installation & Setup

Follow these steps to run NutriScan locally on your machine.

### Prerequisite Checklist
- **Python**: Ensure Python 3.10 or 3.11 is installed.
- **Tesseract**: Install Tesseract OCR binary on your OS and add it to your system PATH variables.

### 1. Clone & Set Up Directory
Navigate to your project folder:
```bash
cd c:\Users\nanda\Downloads\nutriscan_project (3)\nutriscan_project
```

### 2. Configure Environment Variables
Create a file named `.env` in the root directory (copy from `.env.example`):
```env
GEMINI_API_KEY=your_gemini_api_key_here
PORT=8000
HOST=0.0.0.0
```
*(Optionally include Firebase credentials if customizing Google Sign-In).*

### 3. Initialize Virtual Environment & Dependencies
Create a virtual environment, activate it, and install required libraries:
```powershell
# Create environment
python -m venv venv

# Activate on Windows
venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 4. Run the Backend API Server
Start the Uvicorn FastAPI server:
```powershell
venv\Scripts\python.exe -m uvicorn api.server:app --host 0.0.0.0 --port 8000
```
The server will boot up at **`http://localhost:8000`**.

---

## 🧪 Running Tests
To verify system integrity, run the backend suite:
```powershell
venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

---

## 💡 How to Use the App

1.  **Open the App**: Navigate to [http://localhost:8000/](http://localhost:8000/) in your browser.
2.  **Log In**: Click **Developer Demo Mode (Quick Entry)** to bypass Firebase and enter directly, or log in via Google.
3.  **Set Profile**: Open **My Diet Profile**, check your specific health needs (e.g. *Diabetic* or *Hypertension*), and save.
4.  **Scan Food**: Drop a food packaging label image into the dashboard zone and click **Initialize Scan**.
5.  **Log Consumption**: Look over your analysis report, click **Log Consumption**, and watch the **Log Book** display your updated nutritional allowances and progress bars!
