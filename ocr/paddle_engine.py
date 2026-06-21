import numpy as np
import cv2
import os

# ── Suppress every known OneDNN / PIR-related executor path ──────────────────
# Must be set BEFORE importing paddleocr / paddle
os.environ['FLAGS_use_onednn']          = '0'
os.environ['FLAGS_use_mkldnn']          = '0'
os.environ['FLAGS_enable_pir_api']      = '0'
os.environ['FLAGS_pir_apply_inplace_pass'] = '0'
os.environ['PADDLE_WITH_MKLDNN']        = 'OFF'
os.environ['KMP_DUPLICATE_LIB_OK']      = 'True'
os.environ['GLOG_minloglevel']          = '3'   # suppress paddle C++ INFO spam

from paddleocr import PaddleOCR


class PaddleEngine:
    def __init__(self):
        """
        Initializes PaddleOCR for English text.
        use_textline_orientation replaces the deprecated use_angle_cls.
        """
        self.ocr = PaddleOCR(use_textline_orientation=True, lang='en')

    def extract_text(self, image: np.ndarray) -> dict:
        """
        Extracts text using PaddleOCR.

        Returns:
            {
                "best_text": str,
                "primary_engine": "paddleocr",
                "lines": list[str],
                "detections": list[{"text": str, "bbox": list, "confidence": float}]
            }

        Raises:
            RuntimeError: if PaddleOCR inference fails (caller should fall back).
        """
        try:
            result = self.ocr.predict(image)
        except Exception as e:
            raise RuntimeError(f"PaddleOCR inference failed: {e}") from e

        extracted_lines = []
        detections = []

        # predict() returns a list of page results; each page result is a dict.
        if result:
            for page in result:
                rec_texts  = page.get("rec_text",  []) or []
                rec_scores = page.get("rec_score", []) or []
                dt_polys   = page.get("dt_polys",  []) or []

                for text, score, poly in zip(rec_texts, rec_scores, dt_polys):
                    text = str(text).strip()
                    if not text:
                        continue
                    # Normalise polygon to list-of-lists [[x,y], ...]
                    bbox = [[int(pt[0]), int(pt[1])] for pt in poly] if poly is not None else []
                    conf = float(score)

                    extracted_lines.append(text)
                    detections.append({
                        "text":       text,
                        "bbox":       bbox,
                        "confidence": conf
                    })

        full_text = "\n".join(extracted_lines)

        return {
            "best_text":      full_text,
            "primary_engine": "paddleocr",
            "lines":          extracted_lines,
            "detections":     detections
        }
