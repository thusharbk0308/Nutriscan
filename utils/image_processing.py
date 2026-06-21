"""
Stage 2 — OpenCV Preprocessing Pipeline
========================================
Applies the following transformations in order:
  1. Deskew       – Hough-line-based rotation correction (target ≤ 1°)
  2. Dewarp       – Cylindrical coordinate un-warping
  3. Denoise      – Bilateral filter + Fast Non-Local Means
  4. Sharpen      – Unsharp masking
  5. CLAHE        – Contrast Limited Adaptive Histogram Equalisation
  6. Threshold    – Gaussian adaptive binarisation
  7. Super-Res    – FSRCNN x2 via cv2.dnn_superres (if model found in
                    models/FSRCNN_x2.pb); falls back to LANCZOS4 ×2 otherwise.
"""

import cv2
import numpy as np
import os


# ── Helpers ───────────────────────────────────────────────────────────────────

def _models_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")


# ── Stage 2 functions ─────────────────────────────────────────────────────────

def deskew_image(image: np.ndarray) -> np.ndarray:
    """
    Detect dominant text-line angle via Hough Lines and rotate to align.
    Falls back to contour minAreaRect when too few lines are found.
    Target: ≤ 1° residual alignment error.
    """
    gray  = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    lines = cv2.HoughLinesP(edges, 1, np.pi / 180,
                            threshold=100, minLineLength=100, maxLineGap=10)
    angles = []
    if lines is not None:
        for line in sorted(lines,
                           key=lambda l: np.hypot(l[0][2]-l[0][0], l[0][3]-l[0][1]),
                           reverse=True):
            x1, y1, x2, y2 = line[0]
            a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if   a >  45: a -= 90
            elif a < -45: a += 90
            angles.append(a)

    # Fallback to contour method when Hough yields too little data
    if len(angles) < 3:
        pts = np.column_stack(np.where(edges > 0))
        if len(pts) > 0:
            a = cv2.minAreaRect(pts)[-1]
            angles = [-(90 + a) if a < -45 else -a]

    if angles:
        median_angle = float(np.median(angles))
        if 0.1 < abs(median_angle) < 45:
            h, w = image.shape[:2]
            M = cv2.getRotationMatrix2D((w // 2, h // 2), median_angle, 1.0)
            image = cv2.warpAffine(image, M, (w, h),
                                   flags=cv2.INTER_CUBIC,
                                   borderMode=cv2.BORDER_REPLICATE)
            print(f"[Deskew] Corrected rotation: {median_angle:.2f}°")

    return image


def dewarp_image(image: np.ndarray) -> np.ndarray:
    """
    Flatten curved nutrition labels (bottles / cans) using a cylindrical
    coordinate remap.  R ≈ 1.25 × image width.
    """
    h, w = image.shape[:2]
    R    = w * 1.25
    x_c  = w / 2.0

    map_x = np.zeros((h, w), dtype=np.float32)
    map_y = np.zeros((h, w), dtype=np.float32)

    for y in range(h):
        for x in range(w):
            theta       = (x - x_c) / R
            map_x[y, x] = x_c + R * np.sin(theta)
            map_y[y, x] = y

    return cv2.remap(image, map_x, map_y,
                     cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def denoise_image(image: np.ndarray) -> np.ndarray:
    """
    Bilateral filter (edge-preserving) followed by Fast Non-Local Means.
    Works on both colour and grayscale inputs.
    """
    bilateral = cv2.bilateralFilter(image, 9, 75, 75)
    if len(image.shape) == 3:
        return cv2.fastNlMeansDenoisingColored(bilateral, None, 10, 10, 7, 21)
    return cv2.fastNlMeansDenoising(bilateral, None, 10, 7, 21)


def sharpen_image(image: np.ndarray) -> np.ndarray:
    """Unsharp masking: sharpened = original + (original − blurred)."""
    blurred  = cv2.GaussianBlur(image, (5, 5), 0)
    return cv2.addWeighted(image, 1.5, blurred, -0.5, 0)


def enhance_contrast_clahe(image: np.ndarray) -> np.ndarray:
    """
    CLAHE on the L-channel of LAB space for colour images,
    or directly on grayscale.
    """
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    if len(image.shape) == 3:
        lab        = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b    = cv2.split(lab)
        limg       = cv2.merge((clahe.apply(l), a, b))
        return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    return clahe.apply(image)


def adaptive_threshold_image(image: np.ndarray) -> np.ndarray:
    """Convert to grayscale and produce an OCR-friendly binary image."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        21, 11
    )


def super_resolve_image(image: np.ndarray, scale: int = 2) -> np.ndarray:
    """
    Upscale the image to improve small-text readability.

    Strategy (in order):
      1. FSRCNN ×{scale} via cv2.dnn_superres – requires
         models/FSRCNN_x{scale}.pb to be present locally.
         Download from: https://github.com/fannymonori/TF-FSRCNN
      2. LANCZOS4 interpolation – always available, visually better
         than INTER_CUBIC for text.
    """
    model_path = os.path.join(_models_dir(), f"FSRCNN_x{scale}.pb")

    if os.path.isfile(model_path):
        try:
            sr = cv2.dnn_superres.DnnSuperResImpl_create()
            sr.readModel(model_path)
            sr.setModel("fsrcnn", scale)
            upscaled = sr.upsample(image)
            print(f"[Super Resolution] FSRCNN {scale}× applied.")
            return upscaled
        except Exception as e:
            print(f"[Super Resolution] FSRCNN failed ({e}); using LANCZOS4.")
    else:
        print(
            f"[Super Resolution] models/FSRCNN_x{scale}.pb not found. "
            f"Using LANCZOS4 ×{scale}. "
            f"To enable FSRCNN, download the model from "
            f"https://github.com/fannymonori/TF-FSRCNN and place it in models/."
        )

    h, w = image.shape[:2]
    return cv2.resize(image, (w * scale, h * scale),
                      interpolation=cv2.INTER_LANCZOS4)


# ── Public orchestrator ───────────────────────────────────────────────────────

def preprocess_for_ocr(image_path: str) -> np.ndarray:
    """
    Run the full Stage-2 preprocessing pipeline and return a binary
    (single-channel) NumPy array ready for OCR.

    Pipeline order (mirrors the master spec):
      Deskew → Dewarp → Denoise → Sharpen → CLAHE → Threshold → Super-Res
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not load image: {image_path}")

    img = deskew_image(img)
    img = dewarp_image(img)
    img = denoise_image(img)
    img = sharpen_image(img)
    img = enhance_contrast_clahe(img)

    binary = adaptive_threshold_image(img)          # → grayscale

    # Super-res expects colour input; convert back then re-extract
    binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    upscaled   = super_resolve_image(binary_bgr, scale=2)

    return cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
