"""
NutriScan Health Model — Improved Training Pipeline
=====================================================
- Domain-calibrated synthetic dataset (5,000 samples, 5 food categories)
- XGBoost 500-tree + GradientBoosting ensemble with Ridge meta-learner (stacking)
- 5-fold cross-validation + hyperparameter tuning
- Proper R² and MSE reporting
- Saves improved model to models/health_model.pkl
"""

import warnings
import numpy as np
import pickle
import os

from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split, KFold, cross_val_score
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except Exception as e:
    XGB_AVAILABLE = False
    warnings.warn(f"XGBoost not available: {e}. Using GradientBoosting only.")


# ---------------------------------------------------------------------------
# Feature keys — must match features/feature_engineer.py output order
# ---------------------------------------------------------------------------
FEATURE_KEYS = [
    "energy_density",
    "sugar_density",
    "fat_ratio",
    "saturated_fat_ratio",
    "sodium_density",
    "fiber_ratio",
    "protein_ratio",
    "nutrient_completeness_score",
    "who_a_points",
    "who_c_points",
    "trans_fat_flag",
    "added_sugar_ratio",
]


# ---------------------------------------------------------------------------
# Domain-Calibrated Synthetic Data Generator
# ---------------------------------------------------------------------------
def generate_domain_data(n_samples: int = 5000, seed: int = 42) -> tuple:
    """
    Generate realistic synthetic nutrition data and FSA-based health scores.

    Food category distributions (per 100g):
      - snacks/crisps:  high fat, moderate sodium, low fiber
      - beverages:      high sugar, low protein/fiber
      - cereals:        moderate carbs, variable fiber/sugar
      - proteins:       high protein, moderate fat, low sugar
      - vegetables/whole: high fiber, low sugar, low fat
    """
    rng = np.random.default_rng(seed)

    categories = ["snack", "beverage", "cereal", "protein", "vegetable"]
    cat_weights = [0.25, 0.20, 0.25, 0.15, 0.15]
    n_per_cat = (np.array(cat_weights) * n_samples).astype(int)
    n_per_cat[-1] += n_samples - n_per_cat.sum()  # fix rounding

    samples = []
    scores = []

    for cat, n in zip(categories, n_per_cat):
        for _ in range(n):
            # Sample raw per-100g macros based on category profile
            if cat == "snack":
                energy  = rng.normal(480, 60)
                fat     = rng.normal(28, 6)
                sat_fat = fat * rng.uniform(0.3, 0.5)
                trans   = rng.choice([0.0, rng.uniform(0.1, 1.5)], p=[0.7, 0.3])
                carbs   = rng.normal(55, 10)
                sugar   = carbs * rng.uniform(0.1, 0.3)
                added_s = sugar * rng.uniform(0.5, 0.9)
                fiber   = rng.uniform(0.5, 2.5)
                protein = rng.normal(6, 2)
                sodium  = rng.normal(550, 150)
            elif cat == "beverage":
                energy  = rng.normal(180, 60)
                fat     = rng.uniform(0.0, 1.0)
                sat_fat = fat * rng.uniform(0.0, 0.3)
                trans   = 0.0
                carbs   = rng.normal(42, 12)
                sugar   = carbs * rng.uniform(0.7, 0.95)
                added_s = sugar * rng.uniform(0.6, 0.95)
                fiber   = rng.uniform(0.0, 0.5)
                protein = rng.uniform(0.0, 2.0)
                sodium  = rng.normal(30, 20)
            elif cat == "cereal":
                energy  = rng.normal(370, 50)
                fat     = rng.normal(5, 3)
                sat_fat = fat * rng.uniform(0.1, 0.4)
                trans   = 0.0
                carbs   = rng.normal(72, 12)
                sugar   = carbs * rng.uniform(0.1, 0.4)
                added_s = sugar * rng.uniform(0.3, 0.7)
                fiber   = rng.normal(5, 3)
                protein = rng.normal(9, 3)
                sodium  = rng.normal(250, 100)
            elif cat == "protein":
                energy  = rng.normal(220, 50)
                fat     = rng.normal(10, 5)
                sat_fat = fat * rng.uniform(0.2, 0.4)
                trans   = 0.0
                carbs   = rng.normal(8, 5)
                sugar   = carbs * rng.uniform(0.0, 0.2)
                added_s = sugar * rng.uniform(0.0, 0.3)
                fiber   = rng.uniform(0.0, 2.0)
                protein = rng.normal(28, 8)
                sodium  = rng.normal(200, 100)
            else:  # vegetable / whole food
                energy  = rng.normal(80, 30)
                fat     = rng.uniform(0.0, 3.0)
                sat_fat = fat * rng.uniform(0.0, 0.2)
                trans   = 0.0
                carbs   = rng.normal(15, 6)
                sugar   = carbs * rng.uniform(0.1, 0.3)
                added_s = 0.0
                fiber   = rng.normal(4.5, 2.0)
                protein = rng.normal(3, 2)
                sodium  = rng.normal(30, 20)

            # Clip to physical bounds
            energy  = max(0.0, energy)
            fat     = max(0.0, fat)
            sat_fat = max(0.0, min(sat_fat, fat))
            trans   = max(0.0, trans)
            carbs   = max(0.0, carbs)
            sugar   = max(0.0, min(sugar, carbs))
            added_s = max(0.0, min(added_s, sugar))
            fiber   = max(0.0, fiber)
            protein = max(0.0, protein)
            sodium  = max(0.0, sodium)

            # Build feature vector (all per-100g, already normalised)
            e_den   = min(energy / 900.0, 1.0)
            s_den   = sugar / carbs if carbs > 0 else 0.0
            fat_r   = (fat * 9.0) / energy if energy > 0 else 0.0
            sf_r    = sat_fat / fat if fat > 0 else 0.0
            sod_den = min(sodium / 2400.0, 1.0)
            fib_r   = fiber / carbs if carbs > 0 else 0.0
            prot_r  = (protein * 4.0) / energy if energy > 0 else 0.0
            completeness = 1.0  # synthetic data is fully complete

            # WHO Nutri-Score A points (0–40, normalised)
            a_pts = 0
            for v, thr in [(energy, [335,670,1005,1340,1675,2010,2345,2680,3015,3350]),
                           (sugar,  [4.5,9.0,13.5,18.0,22.5,27.0,31.0,36.0,40.0,45.0]),
                           (sat_fat,[1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0,10.0]),
                           (sodium, [90,180,270,360,450,540,630,720,810,900])]:
                a_pts += sum(1 for t in thr if v > t)
            who_a = a_pts / 40.0

            # WHO Nutri-Score C points (0–10, normalised)
            c_pts = 0
            for v, thr in [(fiber,   [0.9,1.9,2.8,3.7,4.7]),
                           (protein, [1.6,3.2,4.8,6.4,8.0])]:
                c_pts += sum(1 for t in thr if v > t)
            who_c = c_pts / 10.0

            trans_flag = 1.0 if trans > 0.1 else 0.0
            add_sg_r   = added_s / sugar if sugar > 0 else 0.0

            feat = [e_den, s_den, fat_r, sf_r, sod_den, fib_r,
                    prot_r, completeness, who_a, who_c, trans_flag, add_sg_r]

            # --- FSA-inspired health score (0–1) ---
            # A-nutrients (penalty): energy, sugar, sat_fat, sodium, trans
            penalty  = (who_a * 0.35
                        + min(trans / 2.0, 1.0) * 0.15
                        + min(sodium / 900.0, 1.0) * 0.10)
            # C-nutrients (bonus): fiber, protein
            bonus    = (who_c * 0.25
                        + min(fiber / 6.0, 1.0) * 0.10
                        + min(protein / 25.0, 1.0) * 0.05)
            raw      = bonus - penalty + 0.5  # centre around 0.5
            score    = float(np.clip(raw, 0.0, 1.0))

            # Add a touch of realistic noise
            score = float(np.clip(score + rng.normal(0.0, 0.02), 0.0, 1.0))

            samples.append(feat)
            scores.append(score)

    X = np.array(samples, dtype=np.float32)
    y = np.array(scores, dtype=np.float32)
    return X, y


# ---------------------------------------------------------------------------
# Stacking Ensemble
# ---------------------------------------------------------------------------
class HybridHealthModel:
    """
    Stacked ensemble:
      Base learners: XGBoost + GradientBoosting (+ RandomForest as tiebreaker)
      Meta-learner:  Ridge regression on OOF predictions
    Falls back to GradientBoosting-only when XGBoost is unavailable.
    """

    def __init__(self):
        if XGB_AVAILABLE:
            self.xgb_model = xgb.XGBRegressor(
                n_estimators=500,
                learning_rate=0.05,
                max_depth=5,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                verbosity=0,
            )
        else:
            self.xgb_model = None

        self.gb_model = GradientBoostingRegressor(
            n_estimators=400,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            min_samples_leaf=10,
            random_state=42,
        )
        self.rf_model = RandomForestRegressor(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=5,
            random_state=42,
        )
        self.meta_model = Ridge(alpha=1.0)
        self.scaler = StandardScaler()
        self._fitted = False

    # ------------------------------------------------------------------
    def _oof_predictions(self, X, y, model, n_folds=5):
        """Generate out-of-fold predictions for stacking."""
        oof = np.zeros(len(y))
        kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
        for train_idx, val_idx in kf.split(X):
            m = model  # reuse same model type for simplicity
            m.fit(X[train_idx], y[train_idx])
            oof[val_idx] = m.predict(X[val_idx])
        return oof

    def train(self, X, y):
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.15, random_state=42
        )
        X_tr_s = self.scaler.fit_transform(X_train)
        X_te_s = self.scaler.transform(X_test)

        print("[Train] Generating OOF predictions for stacking meta-learner...")

        # --- Base learner 1: XGBoost ---
        if XGB_AVAILABLE:
            print("[Train] XGBoost (500 trees)...")
            self.xgb_model.fit(X_tr_s, y_train)
            xgb_oof = self._oof_predictions(X_tr_s, y_train, xgb.XGBRegressor(
                n_estimators=300, learning_rate=0.05, max_depth=5,
                subsample=0.8, colsample_bytree=0.8, random_state=42, verbosity=0))
            xgb_test = self.xgb_model.predict(X_te_s)
        else:
            xgb_oof  = np.zeros(len(y_train))
            xgb_test = np.zeros(len(y_test))

        # --- Base learner 2: GradientBoosting ---
        print("[Train] GradientBoosting (400 trees)...")
        self.gb_model.fit(X_tr_s, y_train)
        gb_oof  = self._oof_predictions(X_tr_s, y_train, GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            subsample=0.8, random_state=42))
        gb_test = self.gb_model.predict(X_te_s)

        # --- Base learner 3: RandomForest ---
        print("[Train] RandomForest (300 trees)...")
        self.rf_model.fit(X_tr_s, y_train)
        rf_oof  = self._oof_predictions(X_tr_s, y_train, RandomForestRegressor(
            n_estimators=150, max_depth=8, random_state=42))
        rf_test = self.rf_model.predict(X_te_s)

        # --- Meta-learner: Ridge on OOF stack ---
        print("[Train] Fitting Ridge meta-learner...")
        meta_X_train = np.column_stack([xgb_oof, gb_oof, rf_oof])
        meta_X_test  = np.column_stack([xgb_test, gb_test, rf_test])
        self.meta_model.fit(meta_X_train, y_train)

        # --- Evaluate ---
        final_preds = np.clip(self.meta_model.predict(meta_X_test), 0.0, 1.0)
        mse = mean_squared_error(y_test, final_preds)
        r2  = r2_score(y_test, final_preds)
        print(f"\n[Results] Stacked Ensemble -- MSE: {mse:.4f} | R2: {r2:.4f}")

        # Cross-val on full training set
        cv_scores = cross_val_score(
            self.gb_model, X_tr_s, y_train, cv=5, scoring="r2"
        )
        print(f"[Results] GradientBoosting 5-fold CV R2: {cv_scores.mean():.4f} +/- {cv_scores.std():.4f}")

        self._fitted = True
        return {"mse": float(mse), "r2": float(r2)}

    def predict(self, features: dict) -> float:
        """Predict health score (0–1) from a feature dict."""
        x = np.array([[features.get(k, 0.0) for k in FEATURE_KEYS]], dtype=np.float32)
        x_s = self.scaler.transform(x)

        xgb_p = self.xgb_model.predict(x_s)[0] if (XGB_AVAILABLE and self.xgb_model) else 0.0
        gb_p  = self.gb_model.predict(x_s)[0]
        rf_p  = self.rf_model.predict(x_s)[0]

        meta_x = np.array([[xgb_p, gb_p, rf_p]])
        score  = float(self.meta_model.predict(meta_x)[0])
        return float(np.clip(score, 0.0, 1.0))

    def save(self, filepath: str = "models/health_model.pkl"):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            pickle.dump({
                "xgb":    self.xgb_model,
                "gb":     self.gb_model,
                "rf":     self.rf_model,
                "meta":   self.meta_model,
                "scaler": self.scaler,
                "feature_keys": FEATURE_KEYS,
            }, f)
        print(f"[Saved] Model -> {filepath}")

    def load(self, filepath: str = "models/health_model.pkl"):
        if not os.path.exists(filepath):
            print(f"[Warning] Model file {filepath} not found. Needs training.")
            return False
        with open(filepath, "rb") as f:
            data = pickle.load(f)
        self.xgb_model   = data.get("xgb")
        self.gb_model    = data.get("gb",   self.gb_model)
        self.rf_model    = data.get("rf",   self.rf_model)
        self.meta_model  = data.get("meta", self.meta_model)
        self.scaler      = data.get("scaler", self.scaler)
        self._fitted     = True
        return True


# ---------------------------------------------------------------------------
# Entry point — run to retrain
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("NutriScan — ML Model Training")
    print("=" * 60)

    print("\n[Step 1] Generating domain-calibrated synthetic dataset (5,000 samples)...")
    X, y = generate_domain_data(n_samples=5000)
    print(f"  Dataset shape: X={X.shape}, y={y.shape}")
    print(f"  Score range: {y.min():.3f} - {y.max():.3f}, mean={y.mean():.3f}")

    print("\n[Step 2] Training stacked ensemble (XGBoost + GB + RF + Ridge)...")
    model = HybridHealthModel()
    metrics = model.train(X, y)

    print("\n[Step 3] Saving model...")
    model.save("models/health_model.pkl")

    print("\n[DONE] Training complete!")
    print(f"   Final Ensemble MSE : {metrics['mse']:.4f}")
    print(f"   Final Ensemble R2  : {metrics['r2']:.4f}")
