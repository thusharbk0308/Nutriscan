import easyocr
import pytesseract
import cv2
import numpy as np

# Initialize EasyOCR once
reader = easyocr.Reader(['en'])

def extract_text(image: np.ndarray) -> dict:
    """
    Extract text using both EasyOCR and Tesseract with detailed bboxes and confidences.
    Takes a preprocessed image array as input.
    """
    img_bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    # 1. EasyOCR
    easyocr_raw = reader.readtext(img_bgr, detail=1)
    easyocr_detections = []
    easyocr_lines = []
    for bbox, text, conf in easyocr_raw:
        easyocr_lines.append(text)
        # Convert bbox points to native list of lists
        easyocr_detections.append({
            "text": text,
            "bbox": [list(map(float, pt)) for pt in bbox],
            "confidence": float(conf)
        })
    easyocr_text = "\n".join(easyocr_lines)

    # 2. Tesseract
    tesseract_detections = []
    tesseract_lines = []
    try:
        tesseract_dict = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        n_boxes = len(tesseract_dict['text'])
        
        # Group tesseract words by line_num, block_num to form logical lines
        line_map = {}
        for i in range(n_boxes):
            text_word = tesseract_dict['text'][i].strip()
            conf = float(tesseract_dict['conf'][i])
            if text_word and conf > 0:
                l, t, w, h = tesseract_dict['left'][i], tesseract_dict['top'][i], tesseract_dict['width'][i], tesseract_dict['height'][i]
                bbox = [[l, t], [l+w, t], [l+w, t+h], [l, t+h]]
                
                tesseract_detections.append({
                    "text": text_word,
                    "bbox": bbox,
                    "confidence": conf / 100.0
                })
                
                # Group for lines
                line_id = f"{tesseract_dict['block_num'][i]}_{tesseract_dict['line_num'][i]}"
                if line_id not in line_map:
                    line_map[line_id] = []
                line_map[line_id].append(text_word)
                
        for line_id, words in line_map.items():
            tesseract_lines.append(" ".join(words))
            
    except Exception as e:
        print(f"   [Warning] Tesseract not found or failed, falling back to EasyOCR only: {e}")
        tesseract_lines = []

    tesseract_text = "\n".join(tesseract_lines)

    # Compare and choose the best one (basic heuristic: length of extracted text)
    if len(easyocr_text.strip()) > len(tesseract_text.strip()):
        best_text = easyocr_text
        primary_engine = "easyocr"
        detections = easyocr_detections
        lines = easyocr_lines
    else:
        best_text = tesseract_text
        primary_engine = "tesseract"
        detections = tesseract_detections
        lines = tesseract_lines

    return {
        "best_text": best_text,
        "primary_engine": primary_engine,
        "lines": lines,
        "detections": detections,
        "raw_easyocr": easyocr_text,
        "raw_tesseract": tesseract_text
    }

