import cv2
import numpy as np
from ultralytics import YOLO
import os

class PanelDetector:
    def __init__(self, model_path="yolov8n.pt"):
        """
        Initializes the YOLOv8 model for panel detection.
        Downloads weights automatically if not present.
        """
        self.model = YOLO(model_path)

    def detect_and_crop(self, image: np.ndarray) -> np.ndarray:
        """
        Detects the nutrition facts panel and crops it.
        If no panel is detected with high confidence, returns the original image.
        """
        # Run inference
        results = self.model(image, conf=0.25, verbose=False)
        
        # We look for the most "panel-like" box
        # In a real scenario, we'd use a model specifically trained for nutrition facts.
        # Here we use the base model and some heuristics.
        best_box = None
        max_area = 0
        
        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy()
            for box in boxes:
                x1, y1, x2, y2 = box
                area = (x2 - x1) * (y2 - y1)
                
                # Heuristic: The nutrition facts panel is usually a significant 
                # vertical or horizontal rectangle.
                if area > max_area:
                    max_area = area
                    best_box = [int(x1), int(y1), int(x2), int(y2)]
        
        if best_box:
            x1, y1, x2, y2 = best_box
            # Add some padding
            h, w = image.shape[:2]
            pad = 40 # Increased safety padding
            x1 = max(0, x1 - pad)
            y1 = max(0, y1 - pad)
            x2 = min(w, x2 + pad)
            y2 = min(h, y2 + pad)
            
            crop = image[y1:y2, x1:x2]
            
            # --- HIGH ACCURACY UPGRADE: Super-Resolution & Enhancement ---
            # 1. Detect if it's a dark label and invert if necessary
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            avg_brightness = np.mean(gray)
            if avg_brightness < 100: # Threshold for dark labels
                crop = cv2.bitwise_not(crop)
                # Boost contrast for white-on-dark labels
                alpha = 1.5 # Contrast
                beta = 0    # Brightness
                crop = cv2.convertScaleAbs(crop, alpha=alpha, beta=beta)

            # 2. Upscale 3x to make small text much larger
            crop = cv2.resize(crop, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
            
            # 3. Subtle sharpening in color
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            crop = cv2.filter2D(crop, -1, kernel)
            
            return crop
        
        return image

def find_panel_heuristic(image: np.ndarray) -> np.ndarray:
    """
    OpenCV-based fallback to find the most likely nutrition facts area
    based on contour density and rectangularity.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (7,7), 0)
    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    # Find contours
    cnts = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = cnts[0] if len(cnts) == 2 else cnts[1]

    h, w = image.shape[:2]
    min_area = (h * w) * 0.1 # At least 10% of image
    
    best_rect = None
    for c in cnts:
        x, y, w_c, h_c = cv2.boundingRect(c)
        area = w_c * h_c
        if area > min_area:
            # Check aspect ratio (nutrition facts are usually vertical or square)
            aspect = h_c / w_c
            if 0.5 < aspect < 3.0:
                if best_rect is None or area > (best_rect[2] * best_rect[3]):
                    best_rect = (x, y, w_c, h_c)

    if best_rect:
        x, y, w_c, h_c = best_rect
        return image[y:y+h_c, x:x+w_c]
    
    return image
