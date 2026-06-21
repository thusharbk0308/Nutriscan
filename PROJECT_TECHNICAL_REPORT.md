# Project Report: NutriScan Neural Core v2.0
## High-Accuracy Nutritional Diagnostic System

### 1. Executive Summary
NutriScan is an AI-powered diagnostic platform designed to bridge the gap between complex nutrition labels and actionable health insights. By leveraging computer vision (OCR) and machine learning (ML), the system extracts raw nutritional data from images and evaluates them against World Health Organization (WHO) safety standards.

---

### 2. Technical Architecture
The system is built on a **Modular Micro-Pipeline** architecture:

#### A. Input Layer (Frontend)
- **Tech**: HTML5, CSS3 (Cyber-Grid System), Vanilla JavaScript.
- **Key Feature**: **Neural Terminal v2.0**. A real-time WebSocket-simulated log that provides transparency into the AI's internal reasoning.
- **UI/UX**: Dark-mode diagnostic dashboard with active scan-line animations.

#### B. Processing Layer (Backend)
- **Tech**: Python 3.10, FastAPI, Uvicorn.
- **Modules**:
    1. **Panel Detector**: Uses YOLOv8 to locate the nutrition table in a crowded image.
    2. **Image Enhancer**: Applies 3x Super-Resolution upscaling and Gaussian sharpening to handle low-light or blurry inputs.
    3. **OCR Engine**: A multi-engine hybrid (PaddleOCR + Tesseract fallback) configured for high-recall text extraction.

#### C. Intelligence Layer (Analysis)
- **Fuzzy Parser**: Implements Levenshtein string similarity to recover data from OCR typos (e.g., correcting "279" to "27g").
- **Health Scorer**: A hybrid model combining:
    - **Rule-Based Engine**: Strict adherence to WHO/FDA daily limits.
    - **ML Model**: Scikit-learn Linear Regression for multidimensional health prediction.

---

### 3. Key Methodologies & Algorithms

#### 1. The "9-as-g" Correction Algorithm
To solve a common OCR failure where 'g' is read as '9', the system uses a heuristic check:
```python
if value > 100 and nutrient_type == "solid":
    if str(value).endswith('9'):
        value = value // 10  # Correct 279g to 27g
```

#### 2. WHO Limit Cross-Referencing
The system maintains a database of Daily Reference Values (DRV):
- **Sodium**: 2000mg Max
- **Total Sugar**: 50g Max
- **Saturated Fat**: 20g Max
It calculates the `% of Daily Budget` consumed by a single serving in real-time.

---

### 4. Features & Accomplishments
*   **Actionable Advice**: Generates personalized verdicts (e.g., `DIABETIC_PROTOCOL_REACHED`).
*   **Side-by-Side Comparison**: Direct comparison of product contents vs. WHO safety limits in the UI.
*   **3x Super-Resolution**: Allows the use of standard smartphone cameras without specialized lighting.
*   **Personalization**: Supports health profiles (Diabetic, Hypertension) to tailor warnings.

---

### 5. Future Scope
1. **Multi-Language Support**: Expanding the OCR to recognize non-English nutrition labels.
2. **Barcode Integration**: Using OpenFoodFacts API to supplement OCR data where available.
3. **Historical Analytics**: Adding a database layer (SQLite) to track a user's nutritional intake over time.

---
**Report Status: Final // NutriScan Core Stable**
**Author: Antigravity AI Engineering**
